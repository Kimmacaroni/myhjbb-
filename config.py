"""봇 전역 설정.

민감한 값은 전부 환경변수로 읽습니다. 코드에 토큰을 직접 적지 마세요.
"""
import os

from dotenv import load_dotenv

# 로컬 개발 시 .env 파일을 읽어 os.environ에 채워줍니다.
# 실제 호스팅(예: systemd, Docker, GitHub Actions Secrets)에서는 환경변수를
# 플랫폼이 직접 주입하므로 .env 파일이 없어도 조용히 넘어갑니다.
load_dotenv()


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
MENU_CHANNEL_ID = _int_env("MENU_CHANNEL_ID")
MENU_URL = "https://www.buspia.co.kr/m/intranet/subpage/my/foodtable.php"
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
# 레벨업 알림을 보낼 채널. 0이면 경험치를 얻은 채팅 채널에 전송(통화방 경험치는 무시).
LEVEL_UP_CHANNEL_ID = _int_env("LEVEL_UP_CHANNEL_ID")
# True면 가장 높은 등급의 칭호 하나만 유지하고 하위 칭호는 회수합니다.
KEEP_ONLY_HIGHEST_TITLE = os.environ.get("KEEP_ONLY_HIGHEST_TITLE", "1") == "1"


def _parse_level_roles(raw: str) -> dict[int, int]:
    """"레벨:역할ID,레벨:역할ID" 형식 문자열을 {레벨: 역할ID} 딕셔너리로 바꿉니다.

    역할은 서버마다 이름/색이 다르므로 봇이 이름을 짓지 않고, 운영진이 디스코드에서
    미리 만들어 둔 역할의 ID를 여기 연결하는 방식으로 둡니다.
    """
    roles: dict[int, int] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        level_str, _, role_id_str = pair.partition(":")
        try:
            roles[int(level_str)] = int(role_id_str)
        except ValueError:
            continue
    return roles


# 레벨 달성 시 자동으로 줄 역할. 예) LEVEL_ROLES="5:123456789012345678,10:234567890123456789"
LEVEL_ROLES = _parse_level_roles(os.environ.get("LEVEL_ROLES", ""))


# ── 신규 멤버 환영 ────────────────────────────────────
# 0이면 환영 메시지를 보내지 않습니다.
WELCOME_CHANNEL_ID = _int_env("WELCOME_CHANNEL_ID")


# ── 운영 로그 ─────────────────────────────────────────
# 추방/차단/경고 등 운영 기록을 남길 채널. 0이면 명령어 응답으로만 남기고 별도 기록은 안 함.
MOD_LOG_CHANNEL_ID = _int_env("MOD_LOG_CHANNEL_ID")
