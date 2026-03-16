import os
import yt_dlp
import requests
import traceback
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'

# --- 外部API連携 (エラーに強く修正) ---
def get_metadata(title, artist):
    try:
        query = f"{title} {artist}"
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        res = requests.get(url, timeout=5).json()
        if res.get('resultCount', 0) > 0:
            return {
                "album": res['results'][0].get('collectionName', 'Unknown Album'),
                "artist": res['results'][0].get('artistName', artist),
                "cover": res['results'][0].get('artworkUrl100', '')
            }
    except: pass
    return {"album": "Unknown Album", "artist": artist, "cover": ""}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        url = request.json.get('url')
        # yt-dlpのオプション設定
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            uploader = info.get('uploader', 'Unknown')
            meta = get_metadata(title, uploader)
            
            return jsonify({
                "success": True,
                "title": title, 
                "artist": meta['artist'], 
                "album": meta['album'],
                "thumbnail": info.get('thumbnail')
            })
    except Exception as e:
        print(f"Error during analyze: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        url, format_type = data.get('url'), data.get('format')
        start, end = data.get('start'), data.get('end')
        filename = data.get('filename', 'output')

        ydl_opts = {'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s'}
        ffmpeg_args = []
        if start: ffmpeg_args.extend(['-ss', start])
        if end: ffmpeg_args.extend(['-to', end])

        if format_type == 'wav':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'external_downloader': 'ffmpeg',
                'external_downloader_args': {'ffmpeg_i': ffmpeg_args}
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
                'external_downloader': 'ffmpeg',
                'external_downloader_args': {'ffmpeg_i': ffmpeg_args}
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            ext = 'wav' if format_type == 'wav' else 'mp4'
            path = f"{DOWNLOAD_FOLDER}/{filename}.{ext}"

        if not os.path.exists(path):
            return "File not found", 404

        @after_this_request
        def cleanup(response):
            if os.path.exists(path): os.remove(path)
            return response
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
