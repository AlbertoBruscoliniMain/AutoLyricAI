import difflib
from statistics import median

from faster_whisper import WhisperModel


MATCH_DIAG = 1
MATCH_UP = 2
MATCH_LEFT = 3

GAP_LYRIC = -1.15
GAP_WHISPER = -0.45
MISMATCH = -1.8
EXACT_MATCH = 2.6
STRONG_MATCH = 1.8
WEAK_MATCH = 1.05
MIN_LINE_SECONDS = 0.18


def get_transcription(file_path: str, hint_lyrics: str = None) -> list:
    """
    Transcribes audio and returns lyric segments with timestamps.

    When official lyrics are available we align the lyric words against
    Whisper's word timestamps with a monotonic global alignment so repeated
    choruses stay in the correct section of the song.
    """
    model = WhisperModel("small", device="cpu", compute_type="int8")

    segs_gen, _ = model.transcribe(
        file_path,
        beam_size=5,
        initial_prompt=hint_lyrics,
        vad_filter=False,
        word_timestamps=True,
    )
    whisper_segs = list(segs_gen)

    if hint_lyrics and whisper_segs:
        lines = [line.strip() for line in hint_lyrics.splitlines() if line.strip()]
        if lines:
            return _forced_align(lines, whisper_segs)

    result = []
    for seg in whisper_segs:
        text = seg.text.strip()
        if not text:
            continue
        start = seg.words[0].start if seg.words else seg.start
        result.append({"start": round(start, 2), "end": round(seg.end, 2), "text": text})
    return result


def _norm(word: str) -> str:
    return "".join(ch for ch in word.casefold() if ch.isalnum())


def _word_score(a: str, b: str, cache: dict[tuple[str, str], float]) -> float:
    key = (a, b)
    if key in cache:
        return cache[key]

    if not a or not b:
        score = MISMATCH
    elif a == b:
        score = EXACT_MATCH
    elif min(len(a), len(b)) >= 4 and (a in b or b in a):
        score = STRONG_MATCH
    else:
        ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
        if min(len(a), len(b)) >= 4 and ratio >= 0.9:
            score = STRONG_MATCH
        elif min(len(a), len(b)) >= 5 and ratio >= 0.8:
            score = WEAK_MATCH
        else:
            score = MISMATCH

    cache[key] = score
    return score


def _collect_whisper_words(whisper_segs: list) -> list:
    whisper_words = []
    for seg in whisper_segs:
        if not seg.words:
            continue
        for word in seg.words:
            norm = _norm(word.word)
            if norm:
                whisper_words.append(
                    {
                        "word": norm,
                        "start": float(word.start),
                        "end": float(word.end),
                    }
                )
    return whisper_words


def _collect_lyric_words(lines: list) -> tuple[list, list]:
    lyric_words = []
    line_word_counts = []
    for line_idx, line in enumerate(lines):
        count = 0
        for pos_in_line, raw_word in enumerate(line.split()):
            norm = _norm(raw_word)
            if not norm:
                continue
            lyric_words.append(
                {
                    "word": norm,
                    "line": line_idx,
                    "pos": count,
                }
            )
            count += 1
        line_word_counts.append(count)
    return lyric_words, line_word_counts


def _semi_global_align(lyric_words: list, whisper_words: list) -> list[tuple[int, int]]:
    n = len(lyric_words)
    m = len(whisper_words)
    directions = [bytearray(m + 1) for _ in range(n + 1)]

    prev = [0.0] * (m + 1)
    score_cache: dict[tuple[str, str], float] = {}

    for i in range(1, n + 1):
        curr = [0.0] * (m + 1)
        curr[0] = prev[0] + GAP_LYRIC
        directions[i][0] = MATCH_UP

        lyric_word = lyric_words[i - 1]["word"]
        for j in range(1, m + 1):
            whisper_word = whisper_words[j - 1]["word"]
            diag_score = prev[j - 1] + _word_score(lyric_word, whisper_word, score_cache)
            up_score = prev[j] + GAP_LYRIC
            left_score = curr[j - 1] + GAP_WHISPER

            best_score = left_score
            best_dir = MATCH_LEFT

            if up_score > best_score:
                best_score = up_score
                best_dir = MATCH_UP

            if diag_score > best_score or (
                abs(diag_score - best_score) < 1e-9
                and _word_score(lyric_word, whisper_word, score_cache) > 0
            ):
                best_score = diag_score
                best_dir = MATCH_DIAG

            curr[j] = best_score
            directions[i][j] = best_dir

        prev = curr

    end_j = max(range(m + 1), key=prev.__getitem__)
    matches = []
    i, j = n, end_j

    while i > 0 and j >= 0:
        direction = directions[i][j]
        if direction == MATCH_DIAG and j > 0:
            score = _word_score(lyric_words[i - 1]["word"], whisper_words[j - 1]["word"], score_cache)
            if score > 0:
                matches.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif direction == MATCH_UP:
            i -= 1
        else:
            if j == 0:
                break
            j -= 1

    matches.reverse()
    return matches


def _estimate_word_step(whisper_words: list) -> float:
    if len(whisper_words) < 2:
        return 0.32

    deltas = []
    for first, second in zip(whisper_words, whisper_words[1:]):
        delta = second["start"] - first["start"]
        if 0.05 <= delta <= 1.2:
            deltas.append(delta)

    if not deltas:
        return 0.32

    return min(0.8, max(0.14, float(median(deltas))))


def _fill_missing_times(anchor_times: dict[int, float], count: int, start_default: float, end_default: float) -> list[float]:
    if count == 0:
        return []

    if not anchor_times:
        span = max(end_default - start_default, MIN_LINE_SECONDS * count)
        return [start_default + (idx / max(count, 1)) * span for idx in range(count)]

    result = [None] * count
    anchors = sorted((idx, time) for idx, time in anchor_times.items() if 0 <= idx < count)

    for idx, time in anchors:
        result[idx] = time

    first_idx, first_time = anchors[0]
    for idx in range(first_idx):
        frac = (idx + 1) / (first_idx + 1)
        result[idx] = start_default + frac * (first_time - start_default)

    last_idx, last_time = anchors[-1]
    for idx in range(last_idx + 1, count):
        frac = (idx - last_idx) / (count - last_idx)
        result[idx] = last_time + frac * (end_default - last_time)

    for (left_idx, left_time), (right_idx, right_time) in zip(anchors, anchors[1:]):
        gap = right_idx - left_idx
        if gap <= 1:
            continue
        for idx in range(left_idx + 1, right_idx):
            frac = (idx - left_idx) / gap
            result[idx] = left_time + frac * (right_time - left_time)

    floor = start_default
    for idx, value in enumerate(result):
        if value is None:
            value = floor + MIN_LINE_SECONDS
        value = max(value, floor)
        result[idx] = value
        floor = value + 0.01

    return result


def _forced_align(lines: list, whisper_segs: list) -> list:
    whisper_words = _collect_whisper_words(whisper_segs)
    if not whisper_words:
        return _uniform(lines, whisper_segs)

    lyric_words, line_word_counts = _collect_lyric_words(lines)
    if not lyric_words:
        return _uniform(lines, whisper_segs)

    matches = _semi_global_align(lyric_words, whisper_words)
    if not matches:
        return _uniform(lines, whisper_segs)

    word_step = _estimate_word_step(whisper_words)
    line_matches: dict[int, list] = {}

    for lyric_idx, whisper_idx in matches:
        lyric_word = lyric_words[lyric_idx]
        line_idx = lyric_word["line"]
        line_matches.setdefault(line_idx, []).append(
            {
                "pos": lyric_word["pos"],
                "start": whisper_words[whisper_idx]["start"],
                "end": whisper_words[whisper_idx]["end"],
            }
        )

    start_anchors = {}
    end_anchors = {}
    t_first = whisper_words[0]["start"]
    t_last = whisper_words[-1]["end"]

    for line_idx, matches_for_line in line_matches.items():
        matches_for_line.sort(key=lambda item: item["pos"])
        first_match = matches_for_line[0]
        last_match = matches_for_line[-1]

        total_words = max(1, line_word_counts[line_idx])
        matched_span_words = max(1, last_match["pos"] - first_match["pos"])
        matched_span_time = max(last_match["end"] - first_match["start"], word_step)
        line_word_step = max(word_step, matched_span_time / matched_span_words)

        leading_words = first_match["pos"]
        trailing_words = max(0, total_words - last_match["pos"] - 1)

        start_anchors[line_idx] = max(t_first, first_match["start"] - leading_words * line_word_step)
        end_anchors[line_idx] = min(t_last, last_match["end"] + trailing_words * line_word_step)

    starts = _fill_missing_times(start_anchors, len(lines), t_first, t_last)

    result = []
    for idx, line in enumerate(lines):
        start = starts[idx]
        if idx + 1 < len(starts):
            next_start = starts[idx + 1]
            if idx in end_anchors:
                end = min(next_start, max(start + MIN_LINE_SECONDS, end_anchors[idx]))
            else:
                end = max(start + MIN_LINE_SECONDS, next_start)
        else:
            end = max(start + MIN_LINE_SECONDS, end_anchors.get(idx, t_last))
            end = min(end, t_last)

        result.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "text": line,
            }
        )

    return result


def _uniform(lines: list, whisper_segs: list) -> list:
    count = len(lines)
    start = whisper_segs[0].start
    end = whisper_segs[-1].end
    span = max(end - start, MIN_LINE_SECONDS * count)

    result = []
    for idx, line in enumerate(lines):
        seg_start = start + (idx / count) * span
        seg_end = start + ((idx + 1) / count) * span
        result.append(
            {
                "start": round(seg_start, 2),
                "end": round(seg_end, 2),
                "text": line,
            }
        )
    return result
