import os
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from models import init_db, query, execute
from s3_utils import upload_fileobj, presigned_url

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512MB cap

# Ensure DB exists
init_db()

@app.route("/")
def index():
    videos = query("SELECT id, title, source, s3_key, youtube_url, views, likes, created_at FROM videos ORDER BY id DESC")
    enriched = []
    for v in videos:
        vid = {
            "id": v[0],
            "title": v[1],
            "source": v[2],
            "s3_key": v[3],
            "youtube_url": v[4],
            "views": v[5],
            "likes": v[6],
            "created_at": v[7],
            "play_url": presigned_url(v[3]) if v[2] == "s3" and v[3] else v[4]
        }
        enriched.append(vid)
    return render_template("index.html", videos=enriched)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        title = request.form.get("title", "Untitled")
        youtube_url = request.form.get("youtube_url")
        file = request.files.get("file")

        if youtube_url and youtube_url.strip():
            execute(
                "INSERT INTO videos (title, source, youtube_url) VALUES (?, 'youtube', ?)",
                (title, youtube_url.strip()),
            )
            return redirect(url_for("index"))

        if file and file.filename:
            filename = secure_filename(file.filename)
            key = f"uploads/{filename}"
            content_type = file.mimetype or "application/octet-stream"
            upload_fileobj(file, key, content_type)
            execute(
                "INSERT INTO videos (title, source, s3_key) VALUES (?, 's3', ?)",
                (title, key),
            )
            return redirect(url_for("index"))

    return render_template("upload.html")

@app.route("/watch/<int:vid>")
def watch(vid: int):
    row = query("SELECT id, title, source, s3_key, youtube_url, views, likes FROM videos WHERE id=?", (vid,))
    if not row:
        return "Not found", 404
    v = row[0]
    execute("UPDATE videos SET views = views + 1 WHERE id=?", (vid,))
    play_url = presigned_url(v[3]) if v[2] == "s3" and v[3] else v[4]
    return render_template("watch.html", video={
        "id": v[0],
        "title": v[1],
        "source": v[2],
        "play_url": play_url,
        "likes": v[6],
        "views": v[5] + 1,
    })

@app.route("/like/<int:vid>", methods=["POST"])
def like(vid: int):
    execute("UPDATE videos SET likes = likes + 1 WHERE id=?", (vid,))
    return ("", 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
