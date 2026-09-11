"""환경변수로 전달된 Discord 소유자 ID 목록 파싱."""

from __future__ import annotations

import re

_OWNER_ID_RE = re.compile(r"^\d{1,20}$")


def parse_owner_ids(raw: str | None) -> frozenset[int]:
    """쉼표/공백 구분 ID 중 유효한 양의 정수만 보존합니다.

    미설정·오타·음수는 소유자 우회를 열지 않는 fail-closed 기본값으로
    처리합니다.
    """
    if not raw:
        return frozenset()
    return frozenset(
        owner_id
        for token in re.split(r"[,\s]+", raw.strip())
        if _OWNER_ID_RE.fullmatch(token)
        if (owner_id := int(token)) > 0
    )
