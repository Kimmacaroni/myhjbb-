"""봇 전역 설정.

민감한 값은 전부 환경변수로 읽습니다. 코드에 토큰을 직접 적지 마세요.
"""
import os


def _int_env(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


# ── 필수 ──────────────────────────────────────────────
TOKEN = os.environ.get("DISCORD_TOKEN", "")

# 명령어를 등록할 서버 ID. 비워두면 봇이 참여 중인 모든 서버에 자동 등록합니다.
# (전역 등록은 반영까지 최대 1시간 걸리므로 사용하지 않습니다.)
GUILD_ID = _int_env("GUILD_ID")

# 경험치/칭호 데이터가 저장될 SQLite 파일 경로.
# 호스팅 시 이 파일이 재시작 후에도 남는 위치인지 반드시 확인하세요.
DB_PATH = os.environ.get("DB_PATH", "bot.db")


# ── 식단 브리핑 ───────────────────────────────────────
ENABLE_MENU_TASK = os.environ.get("ENABLE_MENU_TASK", "1") == "1"
# GitHub Actions용 food_bot.py 전용 값입니다. 채널은 /식단채널설정 명령어로
# 지정하므로 bot.py(cogs/menu.py)는 이 값을 읽지 않습니다.
MENU_CHANNEL_ID = _int_env("MENU_CHANNEL_ID")
# 식단을 보낼 시각 (KST 기준)
MENU_HOUR_KST = _int_env("MENU_HOUR_KST", 6)


# ── 채팅 경험치 ───────────────────────────────────────
CHAT_XP_MIN = _int_env("CHAT_XP_MIN", 15)
CHAT_XP_MAX = _int_env("CHAT_XP_MAX", 25)
# 같은 사람에게 다시 채팅 경험치를 줄 때까지의 대기 시간(초). 도배 방지용.
CHAT_XP_COOLDOWN = _int_env("CHAT_XP_COOLDOWN", 60)


# ── 통화방(음성) 경험치 ───────────────────────────────
VOICE_XP_PER_MINUTE = _int_env("VOICE_XP_PER_MINUTE", 5)
# 통화방에 사람이 이 수 미만이면 지급하지 않음 (혼자 켜두고 방치 방지)
VOICE_MIN_MEMBERS = _int_env("VOICE_MIN_MEMBERS", 2)
# 자체 음소거 상태면 지급하지 않음
VOICE_IGNORE_SELF_MUTED = os.environ.get("VOICE_IGNORE_SELF_MUTED", "1") == "1"


# ── 레벨 / 칭호 ───────────────────────────────────────
# 레벨업 알림을 보낼 채널. 0이면 마지막으로 대화한 채널에 전송.
LEVEL_UP_CHANNEL_ID = _int_env("LEVEL_UP_CHANNEL_ID")
# True면 가장 높은 등급의 칭호 하나만 유지하고 하위 칭호는 회수합니다.
KEEP_ONLY_HIGHEST_TITLE = os.environ.get("KEEP_ONLY_HIGHEST_TITLE", "1") == "1"


# ── 교통정보(고속도로 정체 구간) 알림 ─────────────────
ENABLE_TRAFFIC_TASK = os.environ.get("ENABLE_TRAFFIC_TASK", "1") == "1"
# 한국도로공사 Open API(data.ex.co.kr) 인증키. 없으면 교통정보 기능은 꺼집니다.
HIGHWAY_API_KEY = os.environ.get("HIGHWAY_API_KEY", "")
# 새로 정체가 시작됐는지 확인하는 주기(분)
TRAFFIC_POLL_MINUTES = _int_env("TRAFFIC_POLL_MINUTES", 30)
