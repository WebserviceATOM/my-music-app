import os
import yt_dlp
import requests
from flask import Flask, render_template, request, send_file, jsonify, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOWNLOAD_FOLDER = '/tmp'

def get_metadata(title, artist):
    query = f"{title} {artist}"
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    try:
        res = requests.get(url).json()
        if res['resultCount'] > 0:
            return {
                "album": res['results'][0].get('collectionName', ''),
                "artist": res['results'][0].get('artistName', ''),
                "cover": res['results'][0].get('artworkUrl100', '')
            }
    except: pass
    return {"album": "不明なアルバム", "artist": artist, "cover": ""}

def get_lyrics(title, artist):
    url = f"https://lrclib.net/api/search?q={title} {artist}"
    try:
        res = requests.get(url).json()
        if res:
            return {"lrc": res[0].get('syncedLyrics', ''), "txt": res[0].get('plainLyrics', '')}
    except: pass
    return {"lrc": "", "txt": ""}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    url = request.json.get('url')
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'Unknown')
        uploader = info.get('uploader', 'Unknown')
        meta = get_metadata(title, uploader)
        lyrics = get_lyrics(title, meta['artist'])
        return jsonify({
            "title": title, "artist": meta['artist'], "album": meta['album'],
            "lyrics": lyrics, "thumbnail": info.get('thumbnail')
        })

@app.route('/download', methods=['POST'])
def download():
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
        info = ydl.extract_info(url, download=True)
        ext = 'wav' if format_type == 'wav' else 'mp4'
        path = f"{DOWNLOAD_FOLDER}/{filename}.{ext}"

    @after_this_request
    def cleanup(response):
        if os.path.exists(path): os.remove(path)
        return response
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
