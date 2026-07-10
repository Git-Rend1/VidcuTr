import os
import subprocess
import tempfile
import shutil

import yt_dlp
from flask import Flask, request, send_file, render_template_string, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


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

    /* Rounded switch */
    .switch {
      position: relative;
      display: inline-block;
      width: 50px;
      height: 24px;
      margin-top: 8px;
    }

    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
    }

    .slider {
      position: absolute;
      cursor: pointer;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-color: #ccc;
      transition: .4s;
    }

    .slider:before {
      position: absolute;
      content: "";
      height: 18px;
      width: 18px;
      left: 3px;
      bottom: 3px;
      background-color: white;
      transition: .4s;
    }

    input:checked + .slider {
      background-color: #4caf50;
    }

    input:focus + .slider {
      box-shadow: 0 0 1px #4caf50;
    }

    input:checked + .slider:before {
      transform: translateX(26px);
    }

    .slider.round {
      border-radius: 24px;
    }

    .slider.round:before {
      border-radius: 50%;
    }
  </style>
</head>
<body>
  <h1>Online Video Cutter</h1>

  <form id="cut-form" method="POST" action="/cut">
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
      <option value="480" selected>Original resolution</option>
      <option value="360">360p (640x360)</option>
      <option value="480">480p (854x480)</option>
      <option value="720">720p (1280x720)</option>
      <option value="1080">1080p (1920x1080)</option>
    </select>

    <label>Cutting mode</label>
    <label class="switch">
      <input type="checkbox" id="cut-toggle" name="cut_enabled" checked>
      <span class="slider round"></span>
    </label>
    <span id="cut-toggle-label">Cutting enabled</span>

    <p class="note">
      -----------------------------------------------------------
    </p>

    <button type="submit">Cut</button>

    <p class="note">
      <a href="{{ url_for('list_downloads') }}">View saved downloads</a>
    </p>

    <p class="note">
      Xhamster,Xvideo,Xnxx,Pornhub.
    </p>
  </form>

  <form id="clear-form" method="POST" action="{{ url_for('clear_downloads') }}" style="margin-top:20px;">
    <button type="submit" style="background:#c62828;color:#fff;">
      Clear Downloads Folder
    </button>
  </form>

  <script>
    (function() {
      var cutForm = document.getElementById('cut-form');
      if (cutForm) {
        cutForm.addEventListener('submit', function (e) {
          e.preventDefault();

          var formData = new FormData(cutForm);

          fetch('/cut', {
            method: 'POST',
            body: formData
          })
          .then(function(res) {
            return res.json().then(function(data) {
              return { ok: res.ok, data: data };
            });
          })
          .then(function(result) {
            if (result.ok && result.data.status === 'ok') {
              var msg;
              if (result.data.cut_file) {
                msg = 'Cut finished. Go to "View saved downloads" to download the file. Cut file: ' + result.data.cut_file;
              } else {
                msg = 'Download finished. Full video saved. File: ' + result.data.original_file;
              }
              alert(msg);
            } else {
              alert('Error: ' + (result.data && result.data.message ? result.data.message : 'Unknown error'));
            }
          })
          .catch(function(err) {
            alert('Network error: ' + err);
          });
        });
      }

      var clearForm = document.getElementById('clear-form');
      if (clearForm) {
        clearForm.addEventListener('submit', function (e) {
          e.preventDefault();

          fetch('/clear-downloads', {
            method: 'POST'
          })
          .then(function(res) {
            return res.json().then(function(data) {
              return { ok: res.ok, data: data };
            });
          })
          .then(function(result) {
            if (result.ok && result.data.status === 'ok') {
              alert(result.data.message || 'Downloads folder cleared.');
            } else {
              alert('Error: ' + (result.data && result.data.message ? result.data.message : 'Unknown error'));
            }
          })
          .catch(function(err) {
            alert('Network error: ' + err);
          });
        });
      }

      // Cutting enable/disable switch label
      var cutToggle = document.getElementById('cut-toggle');
      var cutToggleLabel = document.getElementById('cut-toggle-label');
      if (cutToggle && cutToggleLabel) {
        function updateCutLabel() {
          if (cutToggle.checked) {
            cutToggleLabel.textContent = 'Cutting enabled';
          } else {
            cutToggleLabel.textContent = 'Cutting disabled (download full video)';
          }
        }
        updateCutLabel();
        cutToggle.addEventListener('change', updateCutLabel);
      }
    })();
  </script>

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
    resolution = request.form.get("resolution", "0").strip()
    cut_enabled_raw = request.form.get("cut_enabled")

    # Checkbox: present when checked, missing when not
    cutting_enabled = cut_enabled_raw is not None

    if not url:
        return jsonify({"status": "error", "message": "Missing URL"}), 400

    if cutting_enabled:
        if not start_str or not end_str:
            return jsonify({"status": "error", "message": "Missing start or end time"}), 400
        try:
            start_sec = parse_hhmmss(start_str)
            end_sec = parse_hhmmss(end_str)
            if end_sec <= start_sec:
                return jsonify({"status": "error", "message": "End time must be greater than start time"}), 400
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    else:
        # If cutting disabled, we don't need start/end; use full video
        start_sec = 0
        end_sec = None

    resolution_int = int(resolution)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "%(title)s.%(ext)s")
        ydl_opts = {
            "format": f"[height={resolution_int}]",
            "merge_output_format": "mp4",
            "outtmpl": input_path,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Download error: {e}"}), 500

        filename = f"{info['title']}.{info['ext']}"
        orgFile_path = os.path.join(tmpdir, filename)
        print("DL File Path: " + orgFile_path)

        download_name = os.path.basename(filename)
        saved_original_path = os.path.join(DOWNLOADS_DIR, download_name)
        os.replace(orgFile_path, saved_original_path)
        print("Org file Moved to Path: " + saved_original_path)

        if cutting_enabled:
            output_path = os.path.join(DOWNLOADS_DIR, "cut" + download_name)
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(start_sec),
                "-i", saved_original_path,
                "-to", str(end_sec),
                "-c", "copy",
                output_path,
            ]
            print("Cuted File Path: " + output_path)
            try:
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                return jsonify({"status": "error", "message": f"FFmpeg error: {e}"}), 500

            return jsonify({
                "status": "ok",
                "cut_file": "cut" + download_name,
                "original_file": download_name,
            }), 200
        else:
            # Cutting disabled: only full video saved
            return jsonify({
                "status": "ok",
                "cut_file": None,
                "original_file": download_name,
            }), 200


@app.route("/downloads", methods=["GET"])
def list_downloads():
    files = []
    if os.path.isdir(DOWNLOADS_DIR):
        names = os.listdir(DOWNLOADS_DIR)
        for name in names:
            path = os.path.join(DOWNLOADS_DIR, name)
            if os.path.isfile(path):
                files.append({
                    "name": name,
                    "mtime": os.path.getmtime(path),
                    "size": os.path.getsize(path),  # bytes
                })
        # Sort by modification time, newest first
        files.sort(key=lambda f: f["mtime"], reverse=True)

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Saved Downloads</title>
      <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; }
        ul { list-style: none; padding: 0; }
        li { margin: 6px 0; }
        a { text-decoration: none; color: #1976d2; }
        .size { color: #555; font-size: 0.9em; margin-left: 8px; }
      </style>
    </head>
    <body>
      <h1>Downloads folder</h1>
      <ul>
        {% for f in files %}
          <li>
            <a href="{{ url_for('download_file', filename=f.name) }}">{{ f.name }}</a>
            <span class="size">({{ (f.size / (1024 * 1024))|round(2) }} MB)</span>
          </li>
        {% endfor %}
      </ul>
      <p><a href="{{ url_for('index') }}">Back to cutter</a></p>
    </body>
    </html>
    """
    return render_template_string(html, files=files)


@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename):
    path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.isfile(path):
        return "File not found.", 404
    return send_file(
        path,
        as_attachment=True,
        download_name=filename
    )


@app.route("/clear-downloads", methods=["POST"])
def clear_downloads():
    try:
        if not os.path.isdir(DOWNLOADS_DIR):
            return jsonify({"status": "error", "message": "Downloads folder does not exist."}), 404

        for name in os.listdir(DOWNLOADS_DIR):
            path = os.path.join(DOWNLOADS_DIR, name)
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)

        return jsonify({"status": "ok", "message": "Downloads folder cleared."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error clearing downloads: {e}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)