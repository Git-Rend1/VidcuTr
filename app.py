import os
import subprocess
import tempfile
import yt_dlp
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func

app = Flask(__name__)

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My Video Cutter</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; }
    label { display: block; margin-top: 10px; }
    input[type="text"], input[type="number"] { width: 100%; padding: 8px; }
    button { margin-top: 20px; padding: 10px 16px; }
    .note { font-size: 0.9em; color: #555; margin-top: 10px; }
  </style>
</head>
<body>
  <h1>Online Video Cutter</h1>
  <form method="POST" action="/cut">
    <label>Video URL</label>
    <input type="text" name="url" placeholder="Paste video link" required>

    <label>Start time (seconds)</label>
    <input type="number" name="start" min="0" value="0" required>

    <label>End time (seconds)</label>
    <input type="number" name="end" min="1" value="30" required>
    
    <label>Video resolution (advanced)</label>
    <select name="resolution">
      <option value="original" selected>Original resolution</option>
      <option value="360p">360p (640x360)</option>
      <option value="480p">480p (854x480)</option>
      <option value="720p">720p (1280x720)</option>
      <option value="1080p">1080p (1920x1080)</option>
    </select>
    
    <p class="note">
      -----------------------------------------------------------
    </p>   
    
    <button type="submit">Cut & Download</button>
    <p class="note">
      Only use URLs you have permission to download and edit.
    </p>
  </form>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/cut", methods=["POST"])
def cut():
    url = request.form.get("url", "").strip()
    start = request.form.get("start", "0").strip()
    end = request.form.get("end", "0").strip()
    resolution = request.form.get("resolution", "original").strip()

    if not url:
        return "Missing URL", 400

    try:
        start_sec = float(start)
        end_sec = float(end)
        resolution = int(resolution)
        if end_sec <= start_sec:
            return "End time must be greater than start time.", 400
    except ValueError:
        return "Invalid time values.", 400

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "%(title)s.%(ext)s")
        ydl_opts = {
            #"format": f'bestvideo[height={resolution}]+bestaudio/best',
            #"format": f"[height<={resolution}]/[height<=720]",
            "format": f"[height={resolution}]",
            "merge_output_format": 'mp4',
            "outtmpl": input_path,
            "download_ranges": yt_dlp.utils.download_range_func([], [[0.0, 30.0]]),
            #"download_ranges": download_range_func(None, [(start_sec, end_sec)]),  #Seconds
            "force_keyframes_at_cuts": True,
            #"format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best"
            #'listformats': True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return f"Download error: {e}", 500

        # Get the actual file path from info_dict
        output_path = info.get("_filename")
        if not output_path or not os.path.isfile(output_path):
            return "Downloaded file not found.", 500

        # Use the final file name for download_name (nice for the user)
        download_name = os.path.basename(output_path)

        # ffmpeg_cmd = [
            # "ffmpeg",
            # "-y",
            # "-ss", str(start_sec),
            # "-i", input_path,
            # "-t", str(duration),
            # "-c", "copy",
            # output_path,
        # ]

        # try:
            # subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # except subprocess.CalledProcessError as e:
            # return f"FFmpeg error: {e}", 500

        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="video/mp4",
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)