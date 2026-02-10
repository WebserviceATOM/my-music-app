import streamlit as st
import yt_dlp
import os, re, zipfile, tempfile
from pydub import AudioSegment
from mutagen.id3 import ID3, TPE1, TIT2, TALB, ID3NoHeaderError
from mutagen.wave import WAVE

st.set_page_config(page_title="Music Downloader", layout="wide")
st.title("🎵 音楽ダウンローダー")

# メタデータ書き込み
def set_metadata(file_path, title, artist, album):
    try:
        try: tags = ID3(file_path)
        except ID3NoHeaderError: tags = ID3()
        tags.add(TPE1(encoding=3, text=artist))
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TALB(encoding=3, text=album))
        tags.save(file_path)
        audio = WAVE(file_path)
        audio["IART"], audio["INAM"] = artist, title
        audio.save()
    except: pass

# YouTube情報取得
url = st.text_input("YouTubeのURLを貼り付けてください")
if url:
    if 'song_list' not in st.session_state:
        with st.spinner("情報取得中..."):
            ydl_opts = {'extract_flat': True, 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [info])
                st.session_state.song_list = []
                for e in entries:
                    t = e.get('title', '')
                    m = re.search(r'『(.*?)』', t)
                    st.session_state.song_list.append({
                        'url': f"https://www.youtube.com/watch?v={e.get('id')}" if 'id' in e else url,
                        'title': m.group(1) if m else t,
                        'artist': info.get('uploader', ''),
                        'album': info.get('title', 'My Album'),
                        's': 0.0, 'e': 0.0
                    })

    # 入力フォーム
    if 'song_list' in st.session_state:
        edited_songs = []
        for i, song in enumerate(st.session_state.song_list):
            with st.expander(f"曲 {i+1}: {song['title']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_title = st.text_input(f"曲名##{i}", song['title'])
                    new_artist = st.text_input(f"アーティスト##{i}", song['artist'])
                with col2:
                    new_album = st.text_input(f"アルバム##{i}", song['album'])
                    c1, c2 = st.columns(2)
                    new_s = c1.number_input(f"開始カット(秒)##{i}", value=0.0, step=0.1)
                    new_e = c2.number_input(f"終了カット(秒)##{i}", value=0.0, step=0.1)
                edited_songs.append({'url':song['url'], 'title':new_title, 'artist':new_artist, 'album':new_album, 's':new_s, 'e':new_e})

        if st.button("ZIP作成＆ダウンロード開始", type="primary"):
            tmpdir = tempfile.mkdtemp()
            zip_path = os.path.join(tmpdir, "songs.zip")
            progress = st.progress(0)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for i, s in enumerate(edited_songs):
                    st.write(f"処理中: {s['title']}...")
                    opts = {'format':'bestaudio/best','outtmpl':f"{tmpdir}/{i}.%(ext)s",'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'wav'}],'quiet':True}
                    with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([s['url']])
                    
                    wav = f"{tmpdir}/{i}.wav"
                    if os.path.exists(wav):
                        audio = AudioSegment.from_wav(wav)
                        trimmed = audio[s['s']*1000 : (len(audio)-s['e']*1000) if s['e']>0 else None]
                        final_wav = os.path.join(tmpdir, f"{s['title']}.wav")
                        trimmed.export(final_wav, format="wav")
                        set_metadata(final_wav, s['title'], s['artist'], s['album'])
                        zipf.write(final_wav, f"{s['title']}.wav")
                    progress.progress((i + 1) / len(edited_songs))

            with open(zip_path, "rb") as f:
                st.download_button("ここを押してZIPを保存", f, file_name="music.zip")