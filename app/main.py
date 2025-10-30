from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Support both "python -m app.main" (package) and "python app/main.py" (script)
try:
    # When executed as a package
    from .models import init_db, query, execute
    from .s3_utils import upload_fileobj, presigned_url, delete_object
except ImportError:  # When executed directly as a script
    from models import init_db, query, execute
    from s3_utils import upload_fileobj, presigned_url, delete_object

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512MB cap


@app.route("/healthz")
def healthz():
    return "OK", 200


# ---------- YouTube helpers ----------
def to_embed(url: str | None) -> str | None:
    """
    Normalize common YouTube URLs (youtube.com, youtu.be, shorts) to:
      https://www.youtube-nocookie.com/embed/<id>
    Returns None if the video id cannot be extracted.
    """
    if not url:
        return None

    u = urlparse(url)
    host = u.netloc.lower().replace("www.", "")

    # extract video id
    vid = ""
    if host == "youtu.be":
        vid = u.path.lstrip("/")
    elif "youtube.com" in host:
        if u.path.startswith("/watch"):
            vid = parse_qs(u.query).get("v", [""])[0]
        elif "/embed/" in u.path:
            vid = u.path.split("/embed/")[-1].split("/")[0]
        elif "/shorts/" in u.path:
            vid = u.path.split("/shorts/")[-1].split("/")[0]

    return f"https://www.youtube-nocookie.com/embed/{vid}" if vid else None
# -------------------------------------


# Ensure DB exists
init_db()


@app.route("/")
def index():
    rows = query(
        """
        SELECT id, title, source, s3_key, youtube_url, views, likes, created_at
        FROM videos ORDER BY id DESC
        """
    )
    videos = []
    for r in rows:
        _id, title, source, s3_key, yt_url, views, likes, created_at = r
        play_url = presigned_url(s3_key) if (source == "s3" and s3_key) else to_embed(yt_url)
        videos.append(
            {
                "id": _id,
                "title": title,
                "source": source,
                "s3_key": s3_key,
                "youtube_url": yt_url,
                "views": views,
                "likes": likes,
                "created_at": created_at,
                "play_url": play_url,
            }
        )
    return render_template("index.html", videos=videos)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        title = request.form.get("title", "Untitled").strip()
        youtube_url = (request.form.get("youtube_url") or "").strip()
        file = request.files.get("file")

        # Add a YouTube link
        if youtube_url:
            execute(
                "INSERT INTO videos (title, source, youtube_url) VALUES (?, 'youtube', ?)",
                (title or "Untitled", youtube_url),
            )
            return redirect(url_for("index"))

        # Upload a file to S3
        if file and file.filename:
            filename = secure_filename(file.filename)
            key = f"uploads/{filename}"
            content_type = file.mimetype or "application/octet-stream"
            upload_fileobj(file, key, content_type)
            execute(
                "INSERT INTO videos (title, source, s3_key) VALUES (?, 's3', ?)",
                (title or filename, key),
            )
            return redirect(url_for("index"))

    return render_template("upload.html")


@app.route("/watch/<int:vid>")
def watch(vid: int):
    row = query(
        "SELECT id, title, source, s3_key, youtube_url, views, likes FROM videos WHERE id=?",
        (vid,),
    )
    if not row:
        return "Not found", 404

    _id, title, source, s3_key, yt_url, views, likes = row[0]
    execute("UPDATE videos SET views = views + 1 WHERE id=?", (vid,))
    play_url = presigned_url(s3_key) if (source == "s3" and s3_key) else to_embed(yt_url)

    return render_template(
        "watch.html",
        video={
            "id": _id,
            "title": title,
            "source": source,
            "play_url": play_url,
            "likes": likes,
            "views": views + 1,
        },
    )


@app.post("/delete/<int:vid>")
def delete_video(vid: int):
    """
    Delete a video record; if it is S3-backed, delete the object too.
    Safe to call even if the S3 object was already manually removed.
    """
    row = query("SELECT source, s3_key FROM videos WHERE id=?", (vid,))
    if not row:
        return "Not found", 404

    source, s3_key = row[0]
    if source == "s3" and s3_key:
        delete_object(s3_key)  # Swallows NoSuchKey

    execute("DELETE FROM videos WHERE id=?", (vid,))
    return redirect(url_for("index"))


@app.post("/like/<int:vid>")
def like(vid: int):
    execute("UPDATE videos SET likes = likes + 1 WHERE id=?", (vid,))
    return ("", 204)


if __name__ == "__main__":
    # When run directly (e.g., local dev: python app/main.py)
    app.run(host="0.0.0.0", port=5000)
