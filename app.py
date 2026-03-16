import os, yt_dlp, requests
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
        
        ydl_opts = {
            'quiet': True, 'extract_flat': True, 'nocheckcertificate': True,
            # Android公式アプリのふりをする（ブロック回避策）
            'client_identifier': 'android',
            'user_agent': 'com.google.android.youtube/19.08.35 (Linux; U; Android 14; ja_JP; CPH2523) gzip',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                try:
                    res = ydl.extract_info(url, download=False)
                    entries = res.get('entries', [res])
                    for entry in entries:
                        all_songs.append({
                            "id": entry.get('id'),
                            "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                            "title": entry.get('title', '無題'),
                            "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                            "uploader": entry.get('uploader', '不明')
                        })
                except: continue
        
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/download', methods=['POST'])
def download():
    try:
        d = request.json
        url, name, fmt = d.get('url'), d.get('filename'), d.get('format')
        off_s = int(d.get('offset_start', 0))

        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{name}.%(ext)s',
            'client_identifier': 'android',
            'nocheckcertificate': True,
        }

        if fmt == 'wav':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'postprocessor_args': ['-ar', '48000', '-sample_fmt', 's24']
            })
        else:
            ydl_opts.update({'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'})

        if off_s > 0:
            ydl_opts['external_downloader'] = 'ffmpeg'
            ydl_opts['external_downloader_args'] = {'ffmpeg_i': ['-ss', str(off_s)]}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            path = f"{DOWNLOAD_FOLDER}/{name}.{fmt}"

        @after_this_request
        def cleanup(r):
            if os.path.exists(path): os.remove(path)
            return r
        return send_file(path, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # RailwayはPORT環境変数を使うのでそれに対応
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
