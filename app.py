import os
import json
import glob
import mimetypes
import urllib.parse
import urllib.request
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file
from downloader import download_audio
from transcriber import get_transcription
from formatter import save_as_lrc, update_playlist, check_cache, get_playlist_entry
from lyrics_fetcher import fetch_lyrics
from song_finder import find_song

app = Flask(__name__)

BASE_DIR  = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(BASE_DIR, 'lyrics_output', 'audio')
COVERS_DIR = os.path.join(BASE_DIR, 'lyrics_output', 'covers')


def safe_title(title: str) -> str:
    return "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)


def ev(type_, **kwargs):
    kwargs['type'] = type_
    return f"data: {json.dumps(kwargs)}\n\n"


def split_display_title(display_title: str) -> tuple[str, str]:
    if ' -- ' in display_title:
        title, artist = display_title.split(' -- ', 1)
        return title.strip(), artist.strip()
    if ' - ' in display_title:
        title, artist = display_title.split(' - ', 1)
        return title.strip(), artist.strip()
    return display_title.strip(), ''


def load_playlist_entries() -> list:
    playlist_path = os.path.join(BASE_DIR, 'lyrics_output', 'playlist.json')
    if not os.path.exists(playlist_path):
        return []
    with open(playlist_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_playlist_entries(playlist: list) -> None:
    output_dir = os.path.join(BASE_DIR, 'lyrics_output')
    os.makedirs(output_dir, exist_ok=True)
    playlist_path = os.path.join(output_dir, 'playlist.json')
    with open(playlist_path, 'w', encoding='utf-8') as f:
        json.dump(playlist, f, ensure_ascii=False, indent=2)


def guess_cover_extension(url: str, content_type: str) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(';', 1)[0].strip())
        if ext == '.jpe':
            ext = '.jpg'
        if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
            return ext

    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
        return ext
    return '.jpg'


def download_cover_file(url: str, display_title: str) -> str | None:
    if not url:
        return None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AutoLyricAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            content_type = r.headers.get('Content-Type', '')
    except Exception:
        return None

    if not data:
        return None

    os.makedirs(COVERS_DIR, exist_ok=True)
    stem = safe_title(display_title)
    ext = guess_cover_extension(url, content_type)
    filename = f"{stem}{ext}"
    path = os.path.join(COVERS_DIR, filename)

    for existing in glob.glob(os.path.join(COVERS_DIR, f"{stem}.*")):
        if existing != path and os.path.isfile(existing):
            os.remove(existing)

    with open(path, 'wb') as f:
        f.write(data)

    return filename


def ensure_entry_cover(entry: dict) -> bool:
    changed = False
    cover = entry.get('cover')
    if cover and os.path.exists(os.path.join(COVERS_DIR, cover)):
        return False
    if cover:
        entry.pop('cover', None)
        changed = True

    title, artist = split_display_title(entry.get('title', ''))
    lookup = f"{title} {artist}".strip() or entry.get('title', '')
    song_info = find_song(lookup)
    cover_url = (song_info or {}).get('artwork_url', '')
    if not cover_url:
        return changed

    cover_filename = download_cover_file(cover_url, entry.get('title', lookup))
    if not cover_filename:
        return changed

    entry['cover'] = cover_filename
    return True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/process')
def process():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query vuota'}), 400

    def generate():
        # ── Cache hit ──────────────────────────────────────────
        cached = check_cache(query)
        if cached:
            entry = get_playlist_entry(query)
            yield ev('done',
                      segments=cached,
                      cached=True,
                      audio=entry.get('audio') if entry else None,
                      cover=entry.get('cover') if entry else None,
                      display_title=entry.get('title', query) if entry else query)
            return

        # ── Step 1: canonical title/artist via iTunes ──────────
        yield ev('progress', message='Ricerca canzone...')
        song_info = find_song(query)
        if song_info and song_info.get('title'):
            title  = song_info['title']
            artist = song_info['artist']
            display_title = f"{title} -- {artist}" if artist else title
        else:
            parts  = [p.strip() for p in query.split(' - ', 1)]
            title  = parts[0]
            artist = parts[1] if len(parts) > 1 else ''
            display_title = query

        yield ev('song_info', display_title=display_title)

        # ── Step 2: fetch lyrics ────────────────────────────────
        yield ev('progress', message='Ricerca testo online...')
        lyrics = fetch_lyrics(artist, title)
        lyrics_lines = None
        if lyrics:
            lyrics_lines = [l.strip() for l in lyrics.splitlines() if l.strip()]
            yield ev('lyrics_found', lines=lyrics_lines)
        else:
            yield ev('progress', message='Testo non trovato, userò trascrizione AI...')

        # ── Step 3: download audio (clean query, no lyrics videos)
        yield ev('progress', message='Download audio...')
        search_q = f"{title} {artist}".strip() if (title and artist) else query
        try:
            audio_path, download_meta = download_audio(search_q)
        except Exception as e:
            yield ev('error', message=f'Errore download: {e}')
            return

        # ── Step 4: Whisper for timestamps only ─────────────────
        yield ev('progress', message='Analisi timing audio...')
        try:
            segments = get_transcription(audio_path, hint_lyrics=lyrics)
        except Exception as e:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            yield ev('error', message=f'Errore analisi: {e}')
            return

        # ── Save ────────────────────────────────────────────────
        os.makedirs(AUDIO_DIR, exist_ok=True)
        audio_filename = f"{safe_title(display_title)}.mp3"
        os.replace(audio_path, os.path.join(AUDIO_DIR, audio_filename))
        lrc_path = save_as_lrc(segments, display_title)
        cover_url = (song_info or {}).get('artwork_url') or download_meta.get('thumbnail')
        cover_filename = download_cover_file(cover_url, display_title)
        update_playlist(display_title, lrc_path, audio_filename, cover_filename)

        yield ev('done',
                 segments=segments,
                 cached=False,
                 audio=audio_filename,
                 cover=cover_filename,
                 display_title=display_title)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/api/playlist')
def get_playlist():
    playlist = load_playlist_entries()
    updated = False
    for entry in playlist:
        if ensure_entry_cover(entry):
            updated = True
    if updated:
        save_playlist_entries(playlist)
    return jsonify(playlist)


@app.route('/api/load')
def load_song():
    title = request.args.get('title', '').strip()
    segments = check_cache(title)
    if not segments:
        return jsonify({'error': 'Non trovato'}), 404
    entry = get_playlist_entry(title)
    return jsonify({'segments': segments, 'audio': entry.get('audio') if entry else None})


@app.route('/api/delete', methods=['POST'])
def delete_song():
    title = request.json.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Titolo mancante'}), 400

    output_dir = os.path.join(BASE_DIR, 'lyrics_output')
    playlist_path = os.path.join(output_dir, 'playlist.json')
    if not os.path.exists(playlist_path):
        return jsonify({'error': 'Playlist non trovata'}), 404

    with open(playlist_path, 'r', encoding='utf-8') as f:
        playlist = json.load(f)

    entry = next((e for e in playlist if e['title'] == title), None)
    if not entry:
        return jsonify({'error': 'Canzone non trovata'}), 404

    for path in [
        os.path.join(output_dir, entry['lrc']),
        os.path.join(AUDIO_DIR, entry['audio']) if entry.get('audio') else None,
        os.path.join(COVERS_DIR, entry['cover']) if entry.get('cover') else None,
    ]:
        if path and os.path.exists(path):
            os.remove(path)

    with open(playlist_path, 'w', encoding='utf-8') as f:
        json.dump([e for e in playlist if e['title'] != title], f, ensure_ascii=False, indent=2)

    return jsonify({'ok': True})


@app.route('/api/audio/<path:filename>')
def serve_audio(filename):
    path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'File non trovato'}), 404
    return send_file(path, mimetype='audio/mpeg', conditional=True)


@app.route('/api/cover/<path:filename>')
def serve_cover(filename):
    path = os.path.join(COVERS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'File non trovato'}), 404
    mimetype = mimetypes.guess_type(path)[0] or 'image/jpeg'
    return send_file(path, mimetype=mimetype, conditional=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
