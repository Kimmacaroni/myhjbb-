"""멜론 TOP100 공개 차트를 읽는 작은 어댑터."""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re

MELON_CHART_URL = "https://www.melon.com/chart/index.htm"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.melon.com/",
}
REQUEST_TIMEOUT_SECONDS = 15

ROW_PATTERN = re.compile(
    r'<tr\b[^>]*\bclass="[^"]*\blst(?:50|100)\b[^"]*"[^>]*>(.*?)</tr>',
    re.IGNORECASE | re.DOTALL,
)


class MelonChartError(RuntimeError):
    """차트를 가져오거나 해석할 수 없을 때 발생한다."""


@dataclass(frozen=True)
class MelonChartEntry:
    rank: int
    title: str
    artist: str


def _text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", "", value)).replace("\xa0", " ").split())


def _match_text(pattern: str, row: str) -> str | None:
    match = re.search(pattern, row, re.IGNORECASE | re.DOTALL)
    return _text(match.group(1)) if match else None


def parse_melon_top100(html: str) -> list[MelonChartEntry]:
    """멜론 차트 HTML에서 순위, 곡명, 아티스트를 1~100위 순으로 추출한다."""
    entries: list[MelonChartEntry] = []
    for row in ROW_PATTERN.findall(html):
        rank_text = _match_text(r'<span\b[^>]*\bclass="rank\s*"[^>]*>\s*(\d+)\s*</span>', row)
        title = _match_text(r'<div\b[^>]*\bclass="ellipsis\s+rank01"[^>]*>.*?<a\b[^>]*>(.*?)</a>', row)
        artist = _match_text(r'<div\b[^>]*\bclass="ellipsis\s+rank02"[^>]*>.*?<a\b[^>]*>(.*?)</a>', row)
        if not rank_text or not title or not artist:
            continue
        entries.append(MelonChartEntry(rank=int(rank_text), title=title, artist=artist))

    entries.sort(key=lambda entry: entry.rank)
    if len(entries) != 100 or [entry.rank for entry in entries] != list(range(1, 101)):
        raise MelonChartError("멜론 TOP100 차트 형식을 확인하지 못했습니다.")
    return entries


def fetch_melon_top100() -> list[MelonChartEntry]:
    """현재 멜론 TOP100 공개 차트를 가져온다."""
    try:
        import requests

        response = requests.get(
            MELON_CHART_URL,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as exc:
        raise MelonChartError("멜론 TOP100 차트를 가져오지 못했습니다.") from exc
    return parse_melon_top100(response.text)
