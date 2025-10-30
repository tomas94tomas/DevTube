# DevTube – Mini YouTube with S3, K3s, Terraform & GitHub Actions

DevTube is a compact, production-style demo service that lets you:

- upload a video file (stored in **Amazon S3**) or
- add a **YouTube** link,

.…then watch it through a simple web UI. The app runs locally (Docker), or in Kubernetes (**k3s** on **EC2**) provisioned by **Terraform**, and is delivered via a full **CI/CD pipeline** on **GitHub Actions**.

---

## Table of contents

- [High-level architecture](#high-level-architecture)
- [Features](#features)
- [Repository layout](#repository-layout)
- [Local development](#local-development)
- [Container image](#container-image)
- [Infrastructure (Terraform)](#infrastructure-terraform)
- [Kubernetes deployment](#kubernetes-deployment)
- [App configuration](#app-configuration)
- [CI/CD pipeline](#cicd-pipeline)
- [Testing & code quality](#testing--code-quality)
- [Operations & troubleshooting](#operations--troubleshooting)
- [Security notes](#security-notes)
- [FAQ](#faq)
- [License](#license)

---

## High-level architecture

```
+------------+         HTTP           +---------------------+
|  Browser   |  <-------------------> |   Flask (DevTube)   |
|  (user)    |                         |  - Upload form      |
+------------+                         |  - Watch page       |
        |                              |  - Like counter     |
        |                              +----------+----------+
        |                                         |
        |  presigned URL (S3)                     | SQLite (PVC)
        |                                         v
        |                               +---------------------+
        |                               |   PersistentVolume  |
        |                               |   (videos.db)       |
        |                               +---------------------+
        |
        |  object storage (upload/play)
        v
+-------------------+        +-------------------------------+
|    AWS S3         |<------>| s3_utils (boto3 client)       |
+-------------------+        +-------------------------------+

+------------------------------------------------------------+
|               k3s (single node on EC2)                     |
|  - Deployment/Service (NodePort 30080->80)                 |
|  - PVC for SQLite                                          |
|  - Secret (AWS_*) or IAM role                              |
+------------------------------------------------------------+

CI/CD: GitHub Actions → build (Docker) → push (GHCR) → deploy (SSH→kubectl)
Terraform: EC2 (Ubuntu+k3s), IAM role, S3 bucket, SG, key pair, PVC bootstrap
```

---

## Features

- **Upload MP4/WebM** files → stored in S3 with content type preserved.
- **Add YouTube links** (any common URL – watch, embed, shorts) → normalized to `youtube-nocookie.com/embed/<id>`.
- **Auto-generated presigned URLs** for S3 playback.
- **Like counter + views** saved in a tiny **SQLite** DB (on Kubernetes: PVC).
- **One-click deploy** via GitHub Actions:
  - `flake8` lint + small `pytest` sanity,
  - build Docker and push to **GHCR**,
  - SSH to EC2 and apply **k8s** manifests, then smoke test.

---

## Repository layout

```
.
├── .env.example                 # Local env vars for docker-compose
├── .flake8                      # Linting config
├── .github/workflows/ci-cd.yml  # CI/CD pipeline
├── app/
│   ├── main.py                  # Flask app (routes)
│   ├── models.py                # SQLite helpers
│   ├── s3_utils.py              # boto3 client (upload + presign)
│   ├── requirements.txt
│   ├── static/                  # CSS
│   └── templates/               # Jinja templates
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── k8s/
│   ├── deployment.yaml          # App + PVC mount
│   ├── service.yaml             # NodePort -> 30080
│   └── ingress.yaml             # (optional, not used by default)
└── terraform/
    ├── main.tf                  # S3, IAM role, EC2, SG, keypair
    ├── variables.tf
    ├── outputs.tf
    └── user_data.sh             # Install k3s; create namespace+PVC
```

---

## Local development

### Prereqs

- Docker / Docker Desktop
- (Optional) Python 3.12 if you want to run without containers

### Run with Docker Compose

1) Copy `.env.example` to `.env` and fill:

```ini
AWS_REGION=eu-central-1
AWS_S3_BUCKET=your-bucket-name
```

> For local testing without AWS you can still run the UI. Uploads to S3 will fail unless you inject valid credentials into the container (see **App configuration**).

2) Start:

```bash
cd docker
docker compose up --build
```

App: http://localhost:5000

### Run with Python directly

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
export FLASK_ENV=development
python app/main.py
```

---

## Container image

- Built from `docker/Dockerfile` (Python 3.12 slim).
- App files are copied into `/app`, default entrypoint runs `python main.py`.
- Images are published to **GitHub Container Registry**:

```
ghcr.io/tomas94tomas/devtube:<git-sha> and :latest
```

---

## Infrastructure (Terraform)

**What it creates**

- **S3 bucket** for video objects (randomized name).
- **IAM role** for EC2; inline policy to access the S3 bucket (scoped).
- **EC2** (Ubuntu 22.04) with:
  - security group (22, 80 open),
  - user-data script that installs **k3s** and creates a **PVC**,
  - optional key pair (either your provided key or generated).
- **Instance profile** bound to EC2 role.

**How to run**

```bash
cd terraform
terraform init
terraform apply -auto-approve
```

Outputs:

- `bucket_name` – use this value for `AWS_S3_BUCKET`
- `instance_public_ip` – public IP of the EC2 host
- `generated_private_key_pem` – optional (only when Terraform generated a key)

**Clean up**

```bash
terraform destroy
```

> Costs: this stack uses a **t3.micro** and an S3 bucket (with `force_destroy`). Remember to destroy to avoid charges.

---

## Kubernetes deployment

The app uses:

- **Deployment** with one container:
  - mounts a PVC at `/data`
  - sets `DB_PATH=/data/videos.db`
  - reads AWS vars either from a Secret or relies on the EC2 IAM role
- **PVC** (1Gi)
- **Service** type **NodePort** (port `30080`), mapped to HTTP `80` via iptables in `user_data.sh`.

### Secrets / AWS credentials

You have two supported options:

**Option A – EC2 IAM Role (recommended)**  
No credentials inside the pod. Ensure:
- EC2 instance profile has S3 permissions (Terraform already does),
- IMDSv2 is **enabled** (set “Optional/Required” and hop limit ≥ 2),
- The bucket name and region are provided as env vars.

**Option B – Kubernetes Secret**  
Inject static keys (use only for demo):

```bash
kubectl -n devtube create secret generic devtube-secrets   --from-literal=AWS_REGION=eu-central-1   --from-literal=AWS_S3_BUCKET=<your-bucket>   --from-literal=AWS_ACCESS_KEY_ID=<id>   --from-literal=AWS_SECRET_ACCESS_KEY=<secret>
```

`k8s/deployment.yaml` already wires `AWS_REGION` and `AWS_S3_BUCKET`.  
If you use static keys, extend the manifest with the two extra `env:` entries or mount the secret as a file and read it in the container.

### Apply manifests (manually)

```bash
kubectl create ns devtube || true
kubectl -n devtube apply -f k8s/deployment.yaml
kubectl -n devtube apply -f k8s/service.yaml
kubectl -n devtube rollout status deploy/devtube --timeout=90s
```

Service will be reachable at the EC2 public IP on port **80** (iptables translates to NodePort 30080).

---

## App configuration

### Environment variables

| Variable            | Default            | Purpose                                    |
|---------------------|--------------------|--------------------------------------------|
| `AWS_REGION`        | `eu-central-1`     | S3 region                                  |
| `AWS_S3_BUCKET`     | (required)         | S3 bucket name                             |
| `DB_PATH`           | `videos.db`        | SQLite file (K8s sets `/data/videos.db`)   |
| `FLASK_ENV`         | `production`       | Flask environment                          |

### HTTP endpoints

- `GET /` – list videos with `Watch` link.
- `GET/POST /upload` – upload MP4/WebM to S3 or add a YouTube URL.
- `GET /watch/<id>` – play the selected item (presigned video or embedded YouTube).
- `POST /like/<id>` – increment likes.

> We intentionally removed a dedicated `/healthz` route; the pipeline smoke-tests `/` instead.

---

## CI/CD pipeline

Defined in **`.github/workflows/ci-cd.yml`**, triggered on pushes to `main`.

### Jobs

**1) `test`**
- `flake8` against `app/` (config in `.flake8`)
- `pytest` sanity test(s), e.g. `app/tests/test_sanity.py`

**2) `build-and-push`**
- `docker build` from `docker/Dockerfile`
- Push to **GHCR** with tags `latest` and the commit SHA

**3) `deploy`**
- SSH to EC2 (`webfactory/ssh-agent` uses `EC2_SSH_KEY` secret)
- Copies `k8s/` and sets image tag
- `kubectl apply` + rollout wait
- Smoke test via `curl http://127.0.0.1:30080/` (expects 200)

### Required GitHub secrets

| Secret          | What it is                                                |
|-----------------|-----------------------------------------------------------|
| `EC2_HOST`      | EC2 public IP or DNS                                      |
| `EC2_SSH_KEY`   | Private key for `ubuntu@EC2_HOST` (PEM, no passphrase)    |

> The pipeline logs show each step (useful for demos: tests → image digest → rollout).

---

## Testing & code quality

- **flake8**: lightweight gate for basic style issues. Configured in `.flake8` (e.g., line-break rules, selected ignores).
- **pytest**: “sanity” level checks to ensure the app imports and routes respond.

Run locally:

```bash
# Lint
flake8 app

# Tests
PYTHONPATH=$(pwd) python -m pytest -q app/tests/test_sanity.py
```

---

## Operations & troubleshooting

### “Upload works locally but fails in CI/K8s”
- Check that `AWS_REGION` and `AWS_S3_BUCKET` are set in the pod:
  ```bash
  kubectl -n devtube exec deploy/devtube -- printenv | egrep 'AWS_|DB_PATH'
  ```
- If using IAM role, ensure **IMDSv2** hop limit ≥ 2 in EC2 metadata options.
- If using static keys, verify the secret is present and envs are wired.

### “Deploy job fails with `curl ... 404`”
- The smoke test hits `/`. If you change the route, update the CI script.
- Confirm rollout succeeded:
  ```bash
  kubectl -n devtube get deploy,po,svc,pvc
  ```

### “Cannot apt-get inside the container during tests”
- Use debian-based images that include IPv4 networking or configure CI to avoid network-bound installs in the pod during tests. For our pipeline, all deps are installed **outside** the container on the runner.

### Access the app on EC2
- Security group opens **80**; the user-data script NATs 80 → NodePort 30080.
- Visit: `http://<EC2_PUBLIC_IP>/`

---

## Security notes

- Prefer **IAM roles** for pods via the node (Option A) instead of storing static AWS keys.
- Bucket policy is scoped to the generated bucket only.
- The SQLite DB is for demo purposes; for multi-replica or production, use RDS/Postgres.
- Uploaded content is publicly inaccessible by default; streaming uses **presigned URLs**.

---

## FAQ

**Why SQLite?**  
It keeps the demo small and self-contained. The PVC survives restarts. Swap to Postgres for scale.

**How big can uploads be?**  
By default the app limits to `512 MB` (`MAX_CONTENT_LENGTH`). Adjust in `main.py`.

**Can I use NGINX Ingress instead of NodePort?**  
Yes. Install an ingress controller and apply `k8s/ingress.yaml`, then set a DNS record.

**How do I change the container image used by K8s?**  
The CI replaces the image reference on every deploy. If you roll manually:
```bash
kubectl -n devtube set image deploy/devtube web=ghcr.io/<you>/devtube:<tag>
```

---

## License

MIT (see `LICENSE` if added). Use at your own risk; this is a teaching/demo project.

---

### Credits

Built as a compact, end-to-end DevOps showcase:
**Flask + S3 + Docker + GHCR + Terraform + k3s + GitHub Actions**.
