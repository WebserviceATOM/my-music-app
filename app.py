import os
import yt_dlp
import requests
import traceback
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'

def get_metadata(title, artist):
    try:
        query = f"{title} {artist}"
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        res = requests.get(url, timeout=5).json()
        if res.get('resultCount', 0) > 0:
            return {
                "album": res['results'][0].get('collectionName', 'Unknown Album'),
                "artist": res['results'][0].get('artistName', artist)
            }
    except: pass
    return {"album": "Unknown Album", "artist": artist}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        urls = request.json.get('urls', [])
        all_songs = []
        
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                result = ydl.extract_info(url, download=False)
                if 'entries' in result:
                    for entry in result['entries']:
                        all_songs.append({
                            "id": entry.get('id'),
                            "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                            "title": entry.get('title'),
                            "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                            "uploader": entry.get('uploader', 'Unknown')
                        })
                else:
                    all_songs.append({
                        "id": result.get('id'),
                        "url": url,
                        "title": result.get('title'),
                        "thumbnail": result.get('thumbnail'),
                        "uploader": result.get('uploader', 'Unknown')
                    })
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/get_extra_info', methods=['POST'])
def get_extra_info():
    data = request.json
    return jsonify(get_metadata(data.get('title'), data.get('uploader')))

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        url = data.get('url')
        filename = data.get('filename')
        fmt = data.get('format')
        offset_start = int(data.get('offset_start', 0))
        offset_end = int(data.get('offset_end', 0))

        # 動画の長さを取得してエンドトリミングを計算
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            total_duration = info.get('duration')

        ydl_opts = {'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s'}
        
        # FFmpegのトリミング引数を構築
        # -ss (開始秒) -to (終了秒)
        end_time = total_duration - offset_end if total_duration else None
        ffmpeg_args = ['-ss', str(offset_start)]
        if end_time and end_time > offset_start:
            ffmpeg_args.extend(['-to', str(end_time)])

        if fmt == 'wav':
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
            path = f"{DOWNLOAD_FOLDER}/{filename}.{fmt}"

        @after_this_request
        def cleanup(response):
            if os.path.exists(path): os.remove(path)
            return response
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
