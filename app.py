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

@app.route('/find_official', methods=['POST'])
def find_official():
    try:
        data = request.json
        search_query = f"{data.get('title')} {data.get('artist')} official audio"
        ydl_opts = {'quiet': True, 'extract_flat': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch1:{search_query}", download=False)
            if 'entries' in search_result and len(search_result['entries']) > 0:
                official = search_result['entries'][0]
                return jsonify({
                    "success": True,
                    "url": f"https://www.youtube.com/watch?v={official['id']}",
                    "title": official['title'],
                    "id": official['id']
                })
        return jsonify({"success": False, "error": "Not Found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        urls = request.json.get('urls', [])
        all_songs = []
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                result = ydl.extract_info(url, download=False)
                entries = result.get('entries', [result])
                for entry in entries:
                    all_songs.append({
                        "id": entry.get('id'),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "title": entry.get('title'),
                        "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                        "uploader": entry.get('uploader', 'Unknown')
                    })
        return jsonify({"success": True, "songs": all_songs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        url, filename, fmt = data.get('url'), data.get('filename'), data.get('format')
        auto_clean = data.get('auto_clean', False)
        off_s, off_e = int(data.get('offset_start', 0)), int(data.get('offset_end', 0))

        # 超高音質設定
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
            'format': 'bestaudio/best', # 最高音質ストリームを選択
            'nocheckcertificate': True,
        }

        # SponsorBlock (AIカット)
        post_processors = []
        if auto_clean:
            post_processors.append({
                'key': 'SponsorBlock',
                'categories': ['intro', 'outro', 'music_offtopic', 'filler'],
            })

        # 高音質変換引数 (WAV 24bit / 48kHz)
        if fmt == 'wav':
            post_processors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            })
            # FFmpegへの直接命令: 48kHz, 24bit指定
            ydl_opts['postprocessor_args'] = ['-ar', '48000', '-sample_fmt', 's24']

        ydl_opts['postprocessors'] = post_processors

        # トリミング設定
        ffmpeg_i_args = []
        if off_s > 0: ffmpeg_i_args.extend(['-ss', str(off_s)])
        if off_e > 0 or off_s > 0:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl_info:
                info = ydl_info.extract_info(url, download=False)
                duration = info.get('duration', 0)
                if off_e > 0 and duration > off_e:
                    ffmpeg_i_args.extend(['-to', str(duration - off_e)])
            ydl_opts['external_downloader'] = 'ffmpeg'
            ydl_opts['external_downloader_args'] = {'ffmpeg_i': ffmpeg_i_args}

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
