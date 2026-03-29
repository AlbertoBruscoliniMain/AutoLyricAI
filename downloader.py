import yt_dlp
import os

def download_audio(query: str) -> tuple:
    """
    Searches YouTube for the given query and downloads the audio as .mp3.
    Returns (file_path, metadata) where metadata contains artist, title, and thumbnail.
    """
    output_path = os.path.join(os.path.dirname(__file__), "temp_audio")
    os.makedirs(output_path, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "default_search": "ytsearch1",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]

        meta = {
            "artist": info.get("artist") or info.get("creator") or info.get("uploader", ""),
            "title":  info.get("track")  or info.get("title", query),
            "thumbnail": info.get("thumbnail") or "",
        }
        if not meta["thumbnail"]:
            thumbs = info.get("thumbnails") or []
            for thumb in reversed(thumbs):
                url = (thumb or {}).get("url")
                if url:
                    meta["thumbnail"] = url
                    break

        yt_title = info.get("title", "unknown")
        file_path = os.path.join(output_path, f"{yt_title}.mp3")

        if not os.path.exists(file_path):
            for f in os.listdir(output_path):
                if f.endswith(".mp3"):
                    file_path = os.path.join(output_path, f)
                    break
            else:
                raise FileNotFoundError("Audio file not found after download.")

    return file_path, meta
