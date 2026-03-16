import os, yt_dlp, requests
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'
COOKIE_FILE = 'cookies.txt'
CLEAN_COOKIE_FILE = '/tmp/clean_cookies.txt'

# --- 処理側の問題を解決する「クッキー浄化装置」 ---
def sanitize_cookies():
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with open(CLEAN_COOKIE_FILE, 'w', encoding='utf-8') as f:
            for line in lines:
                # 文字としての「\t」を本物の「タブ記号」に強制置換
                clean_line = line.replace('\\t', '\t')
                # ドメインの先頭にドットがない場合に追加（Netscape形式の厳格ルール対応）
                if clean_line.startswith('youtube.com'):
                    clean_line = '.' + clean_line
                f.write(clean_line)
        return CLEAN_COOKIE_FILE
    except:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        urls = request.json.get('urls', [])
        all_songs = []
        
        # クッキーを浄化してから使用
        clean_path = sanitize_cookies()
        
        ydl_opts = {
            'quiet': True, 'extract_flat': True, 'nocheckcertificate': True,
            'cookiefile': clean_path if clean_path else None,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
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
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/download', methods=['POST'])
def download():
    try:
        d = request.json
        url, name, fmt = d.get('url'), d.get('filename'), d.get('format')
        off_s, off_e = int(d.get('offset_start', 0)), int(d.get('offset_end', 0))

        clean_path = sanitize_cookies()
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{name}.%(ext)s',
            'format': 'bestaudio/best',
            'nocheckcertificate': True,
            'cookiefile': clean_path if clean_path else None
        }

        if fmt == 'wav':
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}]
            ydl_opts['postprocessor_args'] = ['-ar', '48000', '-sample_fmt', 's24']

        if off_s > 0 or off_e > 0:
            with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': clean_path}) as ydl_info:
                info = ydl_info.extract_info(url, download=False)
                duration = info.get('duration', 0)
                ffmpeg_args = ['-ss', str(off_s)]
                if off_e > 0: ffmpeg_args.extend(['-to', str(duration - off_e)])
                ydl_opts['external_downloader'] = 'ffmpeg'
                ydl_opts['external_downloader_args'] = {'ffmpeg_i': ffmpeg_args}

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
    app.run(host='0.0.0.0', port=10000)
