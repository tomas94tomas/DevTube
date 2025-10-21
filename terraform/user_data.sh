#!/bin/bash
set -e
# Basics
apt-get update -y
apt-get install -y curl docker.io
systemctl enable --now docker

# Install k3s (single-node)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--write-kubeconfig-mode 644 --disable traefik" sh -

# Install kubectl symlink
ln -s /usr/local/bin/kubectl /usr/bin/kubectl || true

# Expose NodePort 30080 via iptables to port 80
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 30080

# Create namespace and PVC
kubectl create ns devtube || true
cat <<YAML | kubectl apply -n devtube -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata: { name: devtube-pvc }
spec:
  accessModes: ["ReadWriteOnce"]
  resources: { requests: { storage: 1Gi } }
YAML
