"""식단 정보 조회 및 임베드 생성.

상시 실행 봇(`cogs/menu.py`)과 GitHub Actions 단발 실행 스크립트(`food_bot.py`)가
같은 로직을 쓰도록 여기에 모아둡니다. 한쪽만 고쳐서 결과가 달라지는 일을
막기 위한 것이므로, 식단 형식을 바꿀 때는 이 파일만 수정하면 됩니다.

buspia.co.kr 사이트를 직접 크롤링하던 이전 방식은 사이트 구조가 바뀌며
깨졌습니다. 대신 같은 정보를 이미 정리해서 제공하고 있는 대원여객
배차확인 앱의 Worker API(daewon-dispatch)를 호출합니다 — 소유자 확인 후
재사용을 허락받았습니다.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import discord
import requests

DAEWON_API_URL = "https://daewon-dispatch.kcy990830.workers.dev"

KST = timezone(timedelta(hours=9))


def _first_day_meals(meals: list[dict]) -> list[dict]:
    """API가 여러 날치를 한 배열에 이어붙여 내려주는 경우가 있어서, 두 번째로
    나오는 "조식" 앞까지만 잘라 맨 앞 하루(오늘) 것만 남깁니다. 하루치만
    오면(조식이 한 번뿐이면) 그대로 둡니다.
    """
    breakfast_indexes = [i for i, m in enumerate(meals) if m.get("type") == "조식"]
    if len(breakfast_indexes) >= 2:
        return meals[: breakfast_indexes[1]]
    return meals


def _format_meals(meals: list[dict]) -> str:
    if not meals:
        raise ValueError("오늘의 식단 정보가 없습니다.")

    final = []
    for meal in _first_day_meals(meals):
        meal_type = meal.get("type", "")
        if meal_type in ("중식", "석식"):
            final.append("─" * 20)
        kcal = meal.get("kcal")
        final.append(f"{meal_type} ({kcal}Kcal)" if kcal else meal_type)
        final.extend(meal.get("items") or [])
    return "\n".join(final)


def fetch_menu() -> str:
    """daewon-dispatch Worker의 오늘 식단 정보를 받아 텍스트로 정리합니다.

    Raises:
        requests.RequestException: API를 호출하지 못한 경우.
        ValueError: 응답은 받았지만 오늘 식단 정보가 없는 경우.
    """
    response = requests.post(
        DAEWON_API_URL, json={"action": "foodmenu"}, timeout=10
    )
    response.raise_for_status()
    data = response.json()

    error = data.get("error")
    if error:
        raise ValueError(error)

    meals = (data.get("today") or {}).get("meals")
    return _format_meals(meals)


def make_embed(menu: str) -> discord.Embed:
    embed = discord.Embed(
        title="🏢 명예회장님의 오늘의 식단 브리핑",
        description=(
            f"**날짜: {datetime.now(KST).strftime('%Y년 %m월 %d일')}**\n\n{menu}"
        ),
        colour=15158332,
    )
    embed.set_footer(
        text="KD 운송그룹이 가는 곳에 길이 있습니다.\n길이 있는 곳에 KD 운송그룹이 있습니다."
    )
    return embed


async def build_embed() -> discord.Embed:
    """API 조회 후 임베드를 만듭니다.

    requests는 동기 호출이라 이벤트 루프를 막지 않도록 스레드로 넘깁니다.
    """
    return make_embed(await asyncio.to_thread(fetch_menu))
