import urllib.request
import urllib.parse
import json


def _best_artwork_url(result: dict) -> str:
    for key in ("artworkUrl100", "artworkUrl60", "artworkUrl30"):
        url = (result.get(key) or "").strip()
        if url:
            return (
                url.replace("100x100bb", "512x512bb")
                .replace("60x60bb", "512x512bb")
                .replace("30x30bb", "512x512bb")
            )
    return ""


def find_song(query: str) -> dict:
    """
    Uses iTunes Search API to get the canonical track name and artist.
    Returns {'title': str, 'artist': str, 'artwork_url': str} or None.
    """
    try:
        params = urllib.parse.urlencode({
            'term': query,
            'entity': 'song',
            'media': 'music',
            'limit': 1,
        })
        req = urllib.request.Request(
            f"https://itunes.apple.com/search?{params}",
            headers={"User-Agent": "AutoLyricAI/1.0"},
        )
        with urllib.request.urlopen(req, timeout=7) as r:
            data = json.loads(r.read())
            results = data.get('results', [])
            if results:
                return {
                    'title':  results[0].get('trackName', '').strip(),
                    'artist': results[0].get('artistName', '').strip(),
                    'artwork_url': _best_artwork_url(results[0]),
                }
    except Exception:
        pass
    return None
