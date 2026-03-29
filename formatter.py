import os
import re
import time
import json
from datetime import datetime

def seconds_to_lrc_time(seconds: float) -> str:
    """Converts seconds (e.g. 75.5) to LRC timestamp format [mm:ss.xx]."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"[{minutes:02d}:{int(secs):02d}.{centiseconds:02d}]"

def save_as_lrc(segments: list, song_title: str) -> str:
    """
    Converts transcription segments to .lrc format and saves the file.
    Returns the output file path.
    """
    output_dir = os.path.join(os.path.dirname(__file__), "lyrics_output")
    os.makedirs(output_dir, exist_ok=True)

    safe_title = "".join(c if c.isalnum() or c in " -_()" else "_" for c in song_title)
    output_path = os.path.join(output_dir, f"{safe_title}.lrc")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"[ti:{song_title}]\n")
        f.write(f"[by:AutoLyric AI]\n\n")
        for segment in segments:
            timestamp = seconds_to_lrc_time(segment["start"])
            f.write(f"{timestamp}{segment['text']}\n")

    return output_path


def play_synchronized(segments: list, song_title: str):
    """Prints each lyric line in real-time, synchronized with the original timestamps."""
    print(f"\n♪ {song_title}\n")
    start_time = time.time()

    for segment in segments:
        target = segment["start"]
        elapsed = time.time() - start_time
        wait = target - elapsed
        if wait > 0:
            time.sleep(wait)
        print(f"  {segment['text']}")


def update_playlist(song_title: str, lrc_path: str, audio_filename: str = None, cover_filename: str = None) -> str:
    """Adds the song to the playlist JSON file in lyrics_output/."""
    output_dir = os.path.join(os.path.dirname(__file__), "lyrics_output")
    playlist_path = os.path.join(output_dir, "playlist.json")

    if os.path.exists(playlist_path):
        with open(playlist_path, "r", encoding="utf-8") as f:
            playlist = json.load(f)
    else:
        playlist = []

    entry = next((item for item in playlist if item["title"] == song_title), None)
    if entry is None:
        entry = {
            "title": song_title,
            "lrc": os.path.basename(lrc_path),
            "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        playlist.append(entry)

    entry["lrc"] = os.path.basename(lrc_path)
    if audio_filename:
        entry["audio"] = audio_filename
    if cover_filename:
        entry["cover"] = cover_filename

    with open(playlist_path, "w", encoding="utf-8") as f:
        json.dump(playlist, f, ensure_ascii=False, indent=2)

    return playlist_path


def get_playlist_entry(query: str) -> dict:
    """Returns the full playlist entry for a song, or None."""
    output_dir = os.path.join(os.path.dirname(__file__), 'lyrics_output')
    playlist_path = os.path.join(output_dir, 'playlist.json')
    if not os.path.exists(playlist_path):
        return None
    with open(playlist_path, 'r', encoding='utf-8') as f:
        playlist = json.load(f)
    for entry in playlist:
        if _title_matches(entry['title'], query):
            return entry
    return None


def load_from_lrc(lrc_path: str) -> list:
    """Parse a .lrc file back into a list of segments."""
    segments = []
    pattern = re.compile(r'^\[(\d+):(\d+(?:\.\d+)?)\](.*)')
    with open(lrc_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                minutes = int(m.group(1))
                secs = float(m.group(2))
                text = m.group(3).strip()
                if text:
                    segments.append({'start': minutes * 60 + secs, 'text': text})
    return segments


def _title_matches(stored: str, query: str) -> bool:
    """Match exact title OR 'Query -- Artist' format."""
    s, q = stored.lower(), query.lower()
    return s == q or s.startswith(q + ' --')


def check_cache(query: str):
    """Returns segments from cache if the song was already transcribed, else None."""
    output_dir = os.path.join(os.path.dirname(__file__), 'lyrics_output')
    playlist_path = os.path.join(output_dir, 'playlist.json')
    if not os.path.exists(playlist_path):
        return None
    with open(playlist_path, 'r', encoding='utf-8') as f:
        playlist = json.load(f)
    for entry in playlist:
        if _title_matches(entry['title'], query):
            lrc_path = os.path.join(output_dir, entry['lrc'])
            if os.path.exists(lrc_path):
                return load_from_lrc(lrc_path)
    return None
