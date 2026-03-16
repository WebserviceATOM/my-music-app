import os, yt_dlp, time, re
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'
RAW_COOKIE_FILE = 'cookies.txt'
FIXED_COOKIE_FILE = '/tmp/fixed_cookies.txt'

# --- どんなに壊れたクッキーファイルでもプロ仕様に直す「強制修理装置」 ---
def fix_cookie_format():
    if not os.path.exists(RAW_COOKIE_FILE):
        return None
    try:
        with open(RAW_COOKIE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. 文字としての「\t」を本物の「タブ記号」に変換
        content = content.replace('\\t', '\t')
        
        fixed_lines = []
        fixed_lines.append("# Netscape HTTP Cookie File")
        
        for line in content.splitlines():
            if line.startswith('#') or not line.strip():
                continue
            
            # タブ、または複数のスペースで分割して無理やり7項目にする
            parts = re.split(r'\t| +', line.strip())
            if len(parts) >= 7:
                # ドメインの先頭にドットがない場合は追加
                domain = parts[0]
                if not domain.startswith('.'):
                    domain = '.' + domain
                parts[0] = domain
                # 項目を本物のタブで結合し直す
                fixed_lines.append('\t'.join(parts[:7]))
        
        with open(FIXED_COOKIE_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(fixed_lines) + '\n')
            
        print("--- Cookie File Fixed Successfully ---")
        return FIXED_COOKIE_FILE
    except Exception as e:
        print(f"Cookie Fix Error: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        urls = request.json.get('urls', [])
        all_songs = []
        
        # 使う直前にクッキーを修理する
        cookie_path = fix_cookie_format()
        
        ydl_opts = {
            'quiet': True, 'extract_flat': True, 'nocheckcertificate': True,
            'cookiefile': cookie_path if cookie_path else None,
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
        # Android/Windowsで安全なファイル名に
        name = re.sub(r'[\\/:*?"<>|]', '_', raw_name)[:50]
        
        cookie_path = fix_cookie_format()
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{name}.%(ext)s',
            'nocheckcertificate': True,
            'cookiefile': cookie_path if cookie_path else None,
            'client_identifier': 'android',
        }

        if fmt == 'wav':
            ydl_opts.update({
                'format': 'bestaudio/best',
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
