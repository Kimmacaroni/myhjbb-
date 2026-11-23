"""Rank music identities using spelling aliases and bounded typo matching."""

import re
import unicodedata

# Common Korean spellings resolve to the same artist/title identity.
SPELLING_EQUIVALENTS = {
    "아드레날린": "adrenaline",
    "에이티즈": "ateez",
    "파워업": "power up",
    "툴라": "tula",
    "투앤이원": "2ne1",
    "투엔이원": "2ne1",
    "투애니원": "2ne1",
    "투에니원": "2ne1",
    "퐈이어": "fire",
    "파이어": "fire",
    "씨엘": "cl",
    "씨엘에": "cl",
    "아이코닉": "iconic",
}


class MusicLookupError(RuntimeError):
    """A safe, user-facing lookup failure."""


def _tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold()
    return [part
            for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE)
            for part in SPELLING_EQUIVALENTS.get(token, token).split()]


def _strip_upload_labels(title: str) -> str:
    """Ignore upload descriptions, but retain unknown text and version names."""
    label = re.compile(
        r'^(?:(?:official\s+)?(?:audio|music\s+video|lyric\s+video|lyrics?|visualizer)|'
        r'(?:color\s+coded\s+)?lyrics?(?:\s+(?:eng|rom|han|kor|가사|한국어|해석))*|'
        r'해석|가사(?:\s*(?:첨부|포함|영상|해석))?|한글\s*가사|'
        r'(?:original\s+animation\s+)?soundtrack|ost|'
        r'(?:고음질|음원|mp3|hd|hq|4k|1080p|320\s*kbps))$', re.I)

    def replace(match):
        parts = re.split(r'\s*[/|·,]\s*', match.group(0)[1:-1].strip())
        return ' ' if parts and all(label.fullmatch(p.strip()) for p in parts) else match.group(0)

    return re.sub(r'\([^()]*\)|\[[^\[\]]*\]', replace, title)


def _matches_query_exact(query: str, candidate: dict) -> bool:
    """Require every query token in title/artist/channel, with a title match.

    Latin words require token boundaries (Love must not match Lovely).
    Korean spacing may vary, so adjacent Hangul words are also matched joined.
    Only explicitly registered spelling equivalents are accepted; no fuzzy guesses.
    """
    # Search hints describe the desired upload rather than the song's identity.
    hints = {'가사', '음원', '노래', 'lyrics', 'audio', 'official', 'mp3'}
    requested = [t for t in _tokens(query) if t not in hints]
    raw_title = _strip_upload_labels(str(candidate.get("title") or ""))
    # Metadata labels are not song-title words. Strip only known full labels.
    raw_title = re.sub(
        r"[\[(](?:(?:가사\s*(?:첨부|포함|영상)?|(?:color\s+coded\s+)?lyrics?|official\s+audio|audio|음원|mp3)\s*(?:[/|]\s*)?)+[\])]",
        " ", raw_title, flags=re.IGNORECASE,
    )
    # A Korean title followed by its English rendering is common on official
    # uploads. Keep the Korean side only when the query itself is all Hangul;
    # never discard extra words within the same language/title.
    if requested and all(re.fullmatch(r"[가-힣]+", t) for t in requested):
        sections = re.split(r"\s*[|｜]\s*", raw_title)
        if len(sections) > 1:
            korean_sections = [s for s in sections if re.search(r"[가-힣]", s)]
            if len(korean_sections) == 1:
                raw_title = korean_sections[0]
    title = _tokens(raw_title)
    # Common upload format: Artist - Song. Artist suffixes/aliases are not
    # extra song-title words. All requested words must still match the full
    # metadata, and the song side must match the requested title exactly.
    sections = re.split(r"\s+[-–—]\s+", raw_title, maxsplit=1)
    explicit_artist = _tokens(sections[0]) if len(sections) == 2 else []
    song_title = _tokens(sections[1]) if explicit_artist else title
    identity = title + _tokens(" ".join(str(candidate.get(k) or "") for k in
                                       ("artist", "channel", "uploader")))
    boilerplate = {"official", "audio", "video", "lyrics", "lyric", "mp3", "topic",
                   "음원", "가사", "뮤직비디오", "뮤비"}
    title_identity = [t for t in song_title if t not in boilerplate]
    identity = [t for t in identity if t not in boilerplate]
    creator = explicit_artist + _tokens(" ".join(str(candidate.get(k) or "") for k in
                                                 ("artist", "channel", "uploader")))
    creator = [t for t in creator if t not in boilerplate]

    def contains(token: str, fields: list[str]) -> bool:
        if re.fullmatch(r"[가-힣]+", token):
            return token in "".join(fields)
        return token in fields

    # Permit spacing differences only when the entire remaining title agrees.
    # This accepts "LoveDive" / "Love Dive", but never "Love" / "Love Again".
    requested_song = [t for t in requested if not contains(t, creator)]
    candidate_song = [t for t in title_identity if not contains(t, creator)]
    spacing_match = bool(requested_song and candidate_song
                         and ''.join(requested_song) == ''.join(candidate_song)
                         and (not explicit_artist or all(
                             not contains(t, creator) or contains(t, explicit_artist)
                             for t in requested)))
    # If the query contains an artist, it must be accounted for by this upload.
    # Equality above retains any unmatched artist token, so it cannot disappear.
    return spacing_match or bool(requested and title_identity
                and all(contains(t, identity) for t in requested)
                and (not explicit_artist or all(
                    contains(t, title_identity) or contains(t, explicit_artist) for t in requested))
                and any(contains(t, title_identity) for t in requested)
                and all(contains(t, requested) or contains(t, creator)
                        for t in title_identity))


def normalized_search_query(query: str) -> str:
    normalized = ' '.join(_tokens(query))
    return query.strip() if normalized == query.strip().casefold() else normalized


def _word_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    # Very short words and artist initials are too ambiguous for typo guesses.
    if min(len(left), len(right)) < 3:
        return 0.0
    # Compare Hangul by its letters as well, so a misspelled syllable can match.
    left = unicodedata.normalize('NFD', left)
    right = unicodedata.normalize('NFD', right)
    rows = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        rows[i][0] = i
    for j in range(len(right) + 1):
        rows[0][j] = j
    for i in range(1, len(left) + 1):
        for j in range(1, len(right) + 1):
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1,
                             rows[i - 1][j - 1] + (left[i - 1] != right[j - 1]))
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)
    return 1 - rows[-1][-1] / max(len(left), len(right))


def query_score(query: str, candidate: dict) -> float:
    """Exact identity wins; otherwise rank small artist/title spelling errors."""
    if _matches_query_exact(query, candidate):
        return 1.0
    # A typo in a song name must not turn "Love" into a "Live" version.
    version_words = r'\b(?:live|cover|instrumental|remix|slowed|sped|version|ver)\b|라이브|커버|반주'
    if re.search(version_words, str(candidate.get('title') or ''), re.I) and not re.search(version_words, query, re.I):
        return 0.0
    labels = {'official', 'audio', 'video', 'lyrics', 'lyric', 'mp3', 'topic',
              '가사', '음원', '노래', '뮤비', '뮤직비디오'}

    def tokens(text):
        return [t for t in _tokens(text) if t not in labels]

    requested = tokens(query)
    raw_title = _strip_upload_labels(str(candidate.get('title') or ''))
    parts = re.split(r'\s+[-–—]\s+', raw_title, maxsplit=1)
    title = tokens(parts[-1])
    explicit = tokens(parts[0]) if len(parts) == 2 else []
    creator = explicit + tokens(' '.join(str(candidate.get(k) or '') for k in ('artist', 'channel', 'uploader')))
    if not requested or not title:
        return 0.0

    def best(word, pool):
        return max((_word_similarity(word, other) for other in pool), default=0.0)

    identity = title + (explicit if explicit else creator)
    coverage = [best(word, identity) for word in requested]
    song = [word for word in title if word not in creator]
    # Artist-only queries must not select an arbitrary song from that channel.
    if not song or not any(best(word, song) >= .7 for word in requested):
        return 0.0
    title_coverage = [best(word, requested) for word in song]
    if min(coverage) < .7 or min(title_coverage) < .7:
        return 0.0
    return min(.99, (sum(coverage) / len(coverage) + sum(title_coverage) / len(title_coverage)) / 2)


def matches_query(query: str, candidate: dict) -> bool:
    return query_score(query, candidate) >= .72
