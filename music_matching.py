"""Conservative metadata matching: ambiguous results must not be played."""

import re
import unicodedata

# Explicit spelling equivalents only: never infer translations or fuzzy matches.
SPELLING_EQUIVALENTS = {
    "아드레날린": "adrenaline",
    "에이티즈": "ateez",
}


class MusicLookupError(RuntimeError):
    """A safe, user-facing lookup failure."""


def _tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold()
    return [SPELLING_EQUIVALENTS.get(token, token)
            for token in re.findall(r"[^\W_]+", value, flags=re.UNICODE)]


def matches_query(query: str, candidate: dict) -> bool:
    """Require every query token in title/artist/channel, with a title match.

    Latin words require token boundaries (Love must not match Lovely).
    Korean spacing may vary, so adjacent Hangul words are also matched joined.
    Only explicitly registered spelling equivalents are accepted; no fuzzy guesses.
    """
    requested = _tokens(query)
    raw_title = str(candidate.get("title") or "")
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

    return bool(requested and title_identity
                and all(contains(t, identity) for t in requested)
                and (not explicit_artist or all(
                    contains(t, title_identity) or contains(t, explicit_artist) for t in requested))
                and any(contains(t, title_identity) for t in requested)
                and all(contains(t, requested) or contains(t, creator)
                        for t in title_identity))
