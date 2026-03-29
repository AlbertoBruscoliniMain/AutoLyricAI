import urllib.request
import urllib.parse
import json
import re

# Patterns to strip from YouTube titles before querying the lyrics API
_CLEANUP = re.compile(
    r'(\(Official.*?\)|\[Official.*?\]'
    r'|\(Lyrics.*?\)|\[Lyrics.*?\]'
    r'|\(feat\..*?\)|\(ft\..*?\)|\(with.*?\)|\(w\b.*?\)'
    r'|\(Remaster.*?\)|\(Ultimate.*?\)|\(Audio.*?\)'
    r'|\d{4}\s*Remaster|\d+K\s*REMASTER|-\s*\d+K.*'
    r'|\|\s*.*$)',           # everything after a pipe
    flags=re.IGNORECASE,
)

def clean_title(title: str) -> str:
    """Remove YouTube-specific suffixes from track titles."""
    t = _CLEANUP.sub('', title)
    # Remove trailing dashes and whitespace
    t = re.sub(r'[\s\-–]+$', '', t)
    return t.strip()


def fetch_lyrics(artist: str, title: str) -> str:
    """
    Fetches lyrics from lyrics.ovh.
    Tries multiple artist/title combinations and cleans the strings first.
    Returns lyrics as a string (with section markers stripped), or None.
    """
    c_title  = clean_title(title)
    c_artist = clean_title(artist)

    # Also try splitting on ' & ' or ' and ' in case artist has features
    artist_short = re.split(r'\s+&\s+|\s+and\s+', c_artist, flags=re.IGNORECASE)[0].strip()

    candidates = []
    if c_artist and c_title:
        candidates.append((c_artist, c_title))
    if artist_short and artist_short != c_artist and c_title:
        candidates.append((artist_short, c_title))
    # Try swapped (some queries are "Title - Artist")
    if c_artist and c_title and c_artist != c_title:
        candidates.append((c_title, c_artist))

    for a, t in candidates:
        result = _request(a, t)
        if result:
            return _clean_lyrics(result)

    return None


def _request(artist: str, title: str) -> str:
    try:
        url = "https://api.lyrics.ovh/v1/{}/{}".format(
            urllib.parse.quote(artist),
            urllib.parse.quote(title),
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AutoLyricAI/1.0"})
        with urllib.request.urlopen(req, timeout=7) as r:
            data = json.loads(r.read())
            return data.get("lyrics", "").strip() or None
    except Exception:
        return None


def _clean_lyrics(lyrics: str) -> str:
    """Remove section markers like [Verse 1], [Chorus], etc."""
    lines = []
    for line in lyrics.splitlines():
        line = line.strip()
        if line and not re.match(r'^\[.+\]$', line):
            lines.append(line)
    return '\n'.join(lines)
