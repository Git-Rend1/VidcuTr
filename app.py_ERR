import os
import subprocess
import tempfile
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ------------ Helpers ------------

def parse_hhmmss(time_str: str) -> float:
    """Convert 'HH:MM:SS' (or 'H:MM:SS') to seconds."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 3:
            raise ValueError("Time must be in HH:MM:SS format")
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception as e:
        raise ValueError(f"Invalid time value '{time_str}': {e}")


def get_resolution_args(resolution: str):
    """
    Map resolution choice to FFmpeg scale filter.
    Common streaming resolutions: 360p, 480p, 720p, 1080p. [web:75][web:76][web:78]
    """
    if resolution == "360p":
        # 640x360
        return ["-vf", "scale=640:360"]
    elif resolution == "480p":
        # 854x480
        return ["-vf", "scale=854:480"]
    elif resolution == "720p":
        # 1280x720
        return ["-vf", "scale=1280:720"]
    elif resolution == "1080p":
        # 1920x1080
        return ["-vf", "scale=1920:1080"]
    else:
        # "original" or unknown -> no scale filter
        return []


def build_ffmpeg_cmd(input_path: str, output_path: str, start_sec: float, duration: float,
                     quality: str, resolution: str):
    """
    Build an ffmpeg command based on desired quality and resolution.
    - quality: 'high' / 'medium' / 'low' (CRF-based).
    - resolution: 'original' / '360p' / '480p' / '720p' / '1080p'.
    """
    base = [
        "ffmpeg",
        "-y",
        "-ss", str(start_sec),
        "-i", input_path,
        "-t", str(duration),
    ]

    # Quality options (CRF for libx264). [web:75][web:76][web:78][web:84]
    if quality == "high":
        quality_args = ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]
    elif quality == "medium":
        quality_args = ["-c:v", "libx264", "-crf", "23", "-preset", "fast"]
    elif quality == "low":
        quality_args = ["-c:v", "libx264", "-crf", "28", "-preset", "fast"]
    else:
        quality_args = ["-c:v", "libx264", "-crf", "23", "-preset", "fast"]

    # Resolution args (optional scale filter)
    resolution_args = get_resolution_args(resolution)

    # Always copy audio
    audio_args = ["-c:a", "copy"]

    return base + quality_args + resolution_args + audio_args + [output_path]


# ------------ HTML Template ------------

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My Video Cutter</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; }
    label { display: block; margin-top: 10px; }
    input[type="text"], select { width: 100%; padding: 8px; }
    button { margin-top: 20px; padding: 10px 16px; }
    .note { font-size: 0.9em; color: #555; margin-top: 10px; }
  </style>
</head>
<body>
  <h1>Online Video Cutter</h1>
  <form method="POST" action="/cut">
    <label>Video URL</label>
    <input type="text" name="url" placeholder="Paste video link" required>

    <label>Start time (HH:MM:SS)</label>
    <input type="text"
           name="start"
           placeholder="00:00:00"
           pattern="^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$"
           required>

    <label>End time (HH:MM:SS)</label>
    <input type="text"
           name="end"
           placeholder="00:01:30"
           pattern="^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$"
           required>

    <label>Video quality (CRF)</label>
    <select name="quality">
      <option value="high">High (larger file, better quality)</option>
      <option value="medium" selected>Medium (recommended)</option>
      <option value="low">Low (smaller file, lower quality)</option>
    </select>

    <label>Video resolution (advanced)</label>
    <select name="resolution">
      <option value="original" selected>Original resolution</option>
      <option value="360p">360p (640x360)</option>
      <option value="480p">480p (854x480)</option>
      <option value="720p">720p (1280x720)</option>
      <option value="1080p">1080p (1920x1080)</option>
    </select>

    <button type="submit">Cut & Download</button>
    <p class="note">
      Time format example: 00:01:30 = 1 minute 30 seconds.<br>
      Quality controls file size and sharpness; resolution controls the frame size (e.g. 720p).<br>
      Only use URLs you have permission to download and edit.
    </p>
  </form>
</body>
</html>
"""


# ------------ Routes ------------

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)


@app.route("/cut", methods=["POST"])
def cut():
    url = request.form.get("url", "").strip()
    start_str = request.form.get("start", "").strip()
    end_str = request.form.get("end", "").strip()
    quality = request.form.get("quality", "medium").strip()
    resolution = request.form.get("resolution", "original").strip()

    if not url:
        return "Missing URL", 400
    if not start_str or not end_str:
        return "Missing start or end time.", 400

    # Convert HH:MM:SS to seconds
    try:
        start_sec = parse_hhmmss(start_str)
        end_sec = parse_hhmmss(end_str)
        if end_sec <= start_sec:
            return "End time must be greater than start time.", 400
    except ValueError as e:
        return str(e), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.mp4")

        # yt-dlp options: best MP4 or similar
        ydl_opts = {
            "outtmpl": input_path,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best"
        }

        # Download video
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            return f"Download error: {e}", 500

        # Cut & re-encode with ffmpeg based on quality and resolution
        output_path = os.path.join(tmpdir, "clip.mp4")
        duration = end_sec - start_sec

        ffmpeg_cmd = build_ffmpeg_cmd(
            input_path=input_path,
            output_path=output_path,
            start_sec=start_sec,
            duration=duration,
            quality=quality,
            resolution=resolution,
        )

        try:
            subprocess.run(
                ffmpeg_cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            return f"FFmpeg error: {e}", 500

        return send_file(
            output_path,
            as_attachment=True,
            download_name="clip.mp4",
            mimetype="video/mp4",
        )


# ------------ Entry point ------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)