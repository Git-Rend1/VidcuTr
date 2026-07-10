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


def get_downloads_info():
    """Return list of files (name, mtime, size) and total size in bytes."""
    files = []
    total_size = 0
    if os.path.isdir(DOWNLOADS_DIR):
        for name in os.listdir(DOWNLOADS_DIR):
            path = os.path.join(DOWNLOADS_DIR, name)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                files.append({
                    "name": name,
                    "mtime": mtime,
                    "size": size,
                })
                total_size += size
        # Newest first
        files.sort(key=lambda f: f["mtime"], reverse=True)
    return files, total_size  # [web:238][web:250][web:230]


INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My Video Cutter</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; }
    label { display: block; margin-top: 10px; }
    input[type="text"], input[type="number"] { width: 100%; padding: 8px; }
    button { margin-top: 20px; padding: 10px 16px; }
    .note { font-size: 0.9em; color: #555; margin-top: 10px; }
    .section-title { margin-top: 40px; font-size: 1.2em; }

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

    /* Downloads table */
    table.downloads {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }

    table.downloads th, table.downloads td {
      padding: 6px 8px;
      border-bottom: 1px solid #ddd;
      font-size: 0.95em;
    }

    table.downloads th {
      text-align: left;
      background-color: #f5f5f5;
    }

    .size-cell {
      color: #555;
    }
  </style>
</head>
<body>
  <h1>Online Video Cutter</h1>

  <form id="cut-form" method="POST" action="/cut">
    <label>Video URL</label>
    <input type="text" name="url" placeholder="Paste video link" required>

    <label>Filename prefix (optional)</label>
    <input type="text"
           name="prefix"
           placeholder="e.g. MyClip_">

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
      <input type="checkbox" id="cut-toggle" name="cut_enabled">
      <span class="slider round"></span>
    </label>
    <span id="cut-toggle-label">Cutting enabled</span>

    <p class="note">
      -----------------------------------------------------------
    </p>

    <button type="submit">Cut</button>

    <p class="note">
      Xhamster,Xvideo,Xnxx,Pornhub.
    </p>
  </form>

  <form id="clear-form" method="POST" action="{{ url_for('clear_downloads') }}" style="margin-top:20px;">
    <button type="submit" style="background:#c62828;color:#fff;">
      Clear Downloads Folder
    </button>
  </form>

  <h2 class="section-title">Downloads (stored on server)</h2>
  <p class="note">
    Total storage used: {{ (total_size / (1024 * 1024))|round(2) }} MB
  </p>

  {% if files %}
    <table class="downloads">
      <thead>
        <tr>
          <th>Filename</th>
          <th>Size (MB)</th>
          <th>Download</th>
        </tr>
      </thead>
      <tbody>
        {% for f in files %}
          <tr>
            <td>{{ f.name }}</td>
            <td class="size-cell">{{ (f.size / (1024 * 1024))|round(2) }}</td>
            <td><a href="{{ url_for('download_file', filename=f.name) }}">Download</a></td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="note">No files in downloads folder yet.</p>
  {% endif %}

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
                msg = 'Cut finished. See downloads section below. Cut file: ' + result.data.cut_file;
              } else {
                msg = 'Download finished. Full video saved. File: ' + result.data.original_file;
              }
              alert(msg);
              // Reload page to update downloads list and total size
              window.location.reload();
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
              window.location.reload();
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
    files, total_size = get_downloads_info()
    return render_template_string(INDEX_HTML, files=files, total_size=total_size)


@app.route("/cut", methods=["POST"])
def cut():
    url = request.form.get("url", "").strip()
    prefix = request.form.get("prefix", "").strip()
    start_str = request.form.get("start", "").strip()
    end_str = request.form.get("end", "").strip()
    resolution = request.form.get("resolution", "0").strip()
    cut_enabled_raw = request.form.get("cut_enabled")

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

        # Name from yt-dlp
        filename = f"{info['title']}.{info['ext']}"
        orgFile_path = os.path.join(tmpdir, filename)
        print("DL File Path: " + orgFile_path)

        # Apply optional prefix
        download_name = os.path.basename(filename)
        if prefix:
            download_name = prefix + download_name  # prepend prefix [web:241][web:244][web:243]

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
            return jsonify({
                "status": "ok",
                "cut_file": None,
                "original_file": download_name,
            }), 200


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