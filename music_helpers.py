"""음악 Cog에서 사용하는 부작용 없는 표시 형식 헬퍼."""

from __future__ import annotations


def duration_text(seconds: int | None) -> str:
    """초 단위 길이를 기존 대시보드 표기 형식으로 바꿉니다."""
    if not seconds:
        return "알 수 없음"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def progress_text(
    *,
    start_at: int,
    duration: int | None,
    started_at: float,
    now: float,
    segments: int = 14,
) -> str:
    """현재 재생 위치와 텍스트 재생바를 계산합니다."""
    if not duration:
        return "🔘 `재생 시간 확인 중`"

    elapsed = start_at + max(0, int(now - started_at))
    elapsed = min(elapsed, duration)
    filled = round((elapsed / duration) * segments)
    bar = "━" * filled + "🔘" + "━" * (segments - filled)
    return f"{bar}\n`{duration_text(elapsed)} / {duration_text(duration)}`"
