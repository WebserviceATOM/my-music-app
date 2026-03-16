import os
import yt_dlp
import requests
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        urls = request.json.get('urls', [])
        all_songs = []
        # YouTubeのブロックを回避するための設定を強化
        ydl_opts = {
            'quiet': True, 
            'extract_flat': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                result = ydl.extract_info(url, download=False)
                if not result: continue
                entries = result.get('entries', [result])
                for entry in entries:
                    if not entry: continue
                    all_songs.append({
                        "id": entry.get('id'),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "title": entry.get('title', '無題'),
                        "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                        "uploader": entry.get('uploader', 'Unknown')
                    })
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        # エラーが起きてもJSONを返す
        return jsonify({"success": False, "error": str(e)}), 200

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        url, filename, fmt = data.get('url'), data.get('filename'), data.get('format')
        auto_clean = data.get('auto_clean', False)
        off_s, off_e = int(data.get('offset_start', 0)), int(data.get('offset_end', 0))

        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
            'format': 'bestaudio/best',
            'nocheckcertificate': True,
        }

        if auto_clean:
            ydl_opts['postprocessors'] = [{'key': 'SponsorBlock', 'categories': ['intro', 'outro', 'music_offtopic', 'filler']}]

        ffmpeg_args = ['-ss', str(off_s)]
        if fmt == 'wav':
            ydl_opts.setdefault('postprocessors', []).append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'})
            ydl_opts['postprocessor_args'] = ['-ar', '48000', '-sample_fmt', 's24']

        # 実行
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            path = f"{DOWNLOAD_FOLDER}/{filename}.{fmt}"

        if not os.path.exists(path): return "File missing", 404

        @after_this_request
        def cleanup(response):
            if os.path.exists(path): os.remove(path)
            return response
        return send_file(path, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
