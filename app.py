import os, yt_dlp, time, re
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'
COOKIE_FILE = 'cookies.txt'

def safe_filename(name):
    # Android/Windowsで禁止されている記号を確実に除去
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name[:50].strip()

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
            'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
            'client_identifier': 'android',
            'user_agent': 'com.google.android.youtube/19.08.35 (Linux; U; Android 14; ja_JP; CPH2523)',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                res = ydl.extract_info(url, download=False)
                entries = res.get('entries', [res])
                for entry in entries:
                    all_songs.append({
                        "id": entry.get('id'),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "title": entry.get('title', 'UNTITLED'),
                        "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                        "uploader": entry.get('uploader', 'UNKNOWN')
                    })
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/download', methods=['POST'])
def download():
    try:
        d = request.json
        url, raw_name, fmt = d.get('url'), d.get('filename'), d.get('format')
        name = safe_filename(raw_name)
        
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{name}.%(ext)s',
            'nocheckcertificate': True,
            'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
            'client_identifier': 'android',
            'format': 'bestaudio/best',
        }

        if fmt == 'wav':
            ydl_opts.update({
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'postprocessor_args': ['-ar', '44100', '-sample_fmt', 's16']
            })
        else:
            ydl_opts.update({'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        path = f"{DOWNLOAD_FOLDER}/{name}.{fmt}"
        return send_file(path, as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # Railway環境では環境変数 PORT が割り当てられるので、それを優先して使います
    port = int(os.environ.get("PORT", 8080))
    # 0.0.0.0 で待ち受けるのが必須です
    app.run(host='0.0.0.0', port=port)
