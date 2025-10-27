import io
import re
import app.s3_utils as s3u
from app import models

def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert b"OK" in r.data

def test_homepage_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Latest videos" in r.data

def test_add_youtube_and_watch(client):
    # Add a simple YouTube video via the upload form
    data = {
        "title": "Embed test",
        "youtube_url": "https://www.youtube.com/watch?v=E7wJTI-1dvQ",
    }
    r = client.post("/upload", data=data, follow_redirects=True)
    assert r.status_code == 200

    # Expect row id to be 1 for first insert
    r = client.get("/watch/1")
    assert r.status_code == 200
    # crude check for an iframe or youtube URL presence
    assert b"youtube.com" in r.data or b"<iframe" in r.data

def test_upload_file_paths_to_s3(client, monkeypatch):
    """
    Simulate a file upload and stub out the actual S3 call so tests don't need AWS.
    """
    captured = {}

    def fake_upload(fileobj, key, content_type):
        # record what would have been uploaded
        captured["key"] = key
        captured["content_type"] = content_type
        captured["size"] = len(fileobj.read())

    monkeypatch.setattr(s3u, "upload_fileobj", fake_upload)

    data = {
        "title": "Tiny clip",
        # important: (filefield_name, (fileobj, filename))
        "file": (io.BytesIO(b"test-bytes"), "tiny.mp4"),
    }
    r = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert r.status_code == 200
    # We should see the new item on the homepage
    assert b"Tiny clip" in r.data

    # Make sure our stub was invoked with a sensible key and content type
    assert captured["key"].endswith(".mp4")
    assert captured["content_type"] in ("video/mp4", "application/octet-stream")
    assert captured["size"] == len(b"test-bytes")
