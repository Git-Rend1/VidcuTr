import os
import subprocess
import tempfile
import yt_dlp
from flask import Flask, request, send_file, render_template_string
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func

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

    <label>Start time (HH:MM:SS)</label>
    <input type="text"
           name="start"
           placeholder="00:00:00"
           value="00:00:00"
           pattern="^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$"
           required>

    <label>End time (HH:MM:SS)</label>
    <input type="text"
           name="end"
           placeholder="00:01:30"
           value="00:00:01"
           pattern="^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$"
           required>
    
    <label>Video resolution (advanced)</label>
    <select name="resolution">
      <option value=480 selected>Original resolution</option>
      <option value=360>360p (640x360)</option>
      <option value=480>480p (854x480)</option>
      <option value=720>720p (1280x720)</option>
      <option value=1080>1080p (1920x1080)</option>
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
    start_str = request.form.get("start", "").strip()
    end_str = request.form.get("end", "").strip()
    resolution = request.form.get("resolution", "0").strip()

    if not url:
        return "Missing URL", 400
    if not start_str or not end_str:
        return "Missing start or end time.", 400
        
    try:
        start_sec = parse_hhmmss(start_str)
        end_sec = parse_hhmmss(end_str)
        if end_sec <= start_sec:
            return "End time must be greater than start time.", 400
    except ValueError as e:
        return str(e), 400
            
    resolution_int = int(resolution)
        
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "%(title)s.%(ext)s")
        ydl_opts = {
            #"format": f'bestvideo[height={resolution}]+bestaudio/best',
            #"format": f"[height<={resolution}]/[height<=720]",
            "format": f"[height={resolution}]",
            "merge_output_format": 'mp4',
            "outtmpl": input_path,
            #"download_ranges": yt_dlp.utils.download_range_func([], [[start_sec, end_sec]]),
            #"force_keyframes_at_cuts": True,
            #'listformats': True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return f"Download error: {e}", 500

        # Get the actual file path from info_dict
        output_path = os.path.join(tmpdir, f"{info['title']}.{info['ext']}")
        print(output_path)
        #output_path = info.get("_filename")
        if not output_path or not os.path.isfile(output_path):
            return "Downloaded file not found.", 500

        # Use the final file name for download_name (nice for the user)
        download_name = os.path.basename(output_path)
        #duration = end_sec - start_sec
        
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-i", download_name,
            "-to", str(start_sec),
            "-c", "copy",
            ("cut"+download_name),
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            return f"FFmpeg error: {e}", 500

        return send_file(
            output_path,
            as_attachment=True,
            download_name=("cut"+download_name),
            mimetype="video/mp4",
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)