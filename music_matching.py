"""Conservative metadata matching: ambiguous results must not be played."""

import re
import unicodedata


class MusicLookupError(RuntimeError):
    """A safe, user-facing lookup failure."""


def _tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.findall(r"[^\W_]+", value, flags=re.UNICODE)


def matches_query(query: str, candidate: dict) -> bool:
    """Require every query token in title/artist/channel, with a title match.

    Latin words require token boundaries (Love must not match Lovely).
    Korean spacing may vary, so adjacent Hangul words are also matched joined.
    No fuzzy guesses or translated-name substitutions are accepted.
    """
    requested = _tokens(query)
    title = _tokens(str(candidate.get("title") or ""))
    identity = title + _tokens(" ".join(str(candidate.get(k) or "") for k in
                                       ("artist", "channel", "uploader")))
    boilerplate = {"official", "audio", "video", "lyrics", "lyric", "mp3", "topic",
                   "음원", "가사", "뮤직비디오", "뮤비"}
    title_identity = [t for t in title if t not in boilerplate]
    identity = [t for t in identity if t not in boilerplate]
    creator = _tokens(" ".join(str(candidate.get(k) or "") for k in
                               ("artist", "channel", "uploader")))
    creator = [t for t in creator if t not in boilerplate]

    def contains(token: str, fields: list[str]) -> bool:
        if re.fullmatch(r"[가-힣]+", token):
            return token in "".join(fields)
        return token in fields

    return bool(requested and title_identity
                and all(contains(t, identity) for t in requested)
                and any(contains(t, title_identity) for t in requested)
                and all(contains(t, requested) or contains(t, creator)
                        for t in title_identity))
