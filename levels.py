"""경험치 ↔ 레벨 변환 공식.

레벨 L에서 L+1로 올라가는 데 필요한 경험치는 5L² + 50L + 100 입니다.
레벨이 오를수록 요구량이 완만하게 증가하는 형태라, 초반에는 금방 오르고
고레벨로 갈수록 천천히 오릅니다.
"""
from functools import lru_cache


def xp_to_next_level(level: int) -> int:
    """`level`에서 `level + 1`로 올라가는 데 필요한 경험치."""
    return 5 * (level ** 2) + 50 * level + 100


@lru_cache(maxsize=512)
def total_xp_for_level(level: int) -> int:
    """레벨 0부터 `level`에 도달하기까지 필요한 누적 경험치."""
    return sum(xp_to_next_level(lv) for lv in range(level))


def level_from_xp(xp: int) -> int:
    """누적 경험치로부터 현재 레벨을 계산합니다."""
    level = 0
    remaining = max(0, xp)
    while remaining >= xp_to_next_level(level):
        remaining -= xp_to_next_level(level)
        level += 1
    return level


def progress(xp: int) -> tuple[int, int, int]:
    """(현재 레벨, 현재 레벨에서 모은 경험치, 다음 레벨까지 필요한 경험치)."""
    level = level_from_xp(xp)
    earned = max(0, xp) - total_xp_for_level(level)
    return level, earned, xp_to_next_level(level)


def progress_bar(earned: int, needed: int, width: int = 12) -> str:
    """텍스트 진행률 막대를 만듭니다."""
    if needed <= 0:
        return "▰" * width
    filled = min(width, max(0, round(width * earned / needed)))
    return "▰" * filled + "▱" * (width - filled)
