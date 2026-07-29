"""식단표 크롤링 및 임베드 생성.

상시 실행 봇(`cogs/menu.py`)과 GitHub Actions 단발 실행 스크립트(`food_bot.py`)가
같은 로직을 쓰도록 여기에 모아둡니다. 한쪽만 고쳐서 결과가 달라지는 일을
막기 위한 것이므로, 식단 형식을 바꿀 때는 이 파일만 수정하면 됩니다.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone

import discord
import requests
from bs4 import BeautifulSoup

import config

KST = timezone(timedelta(hours=9))


def fetch_menu() -> str:
    """식단표 페이지를 읽어 텍스트로 정리합니다.

    Raises:
        requests.RequestException: 페이지를 가져오지 못한 경우.
        ValueError: 페이지는 받았지만 식단 내용을 찾지 못한 경우.
    """
    response = requests.get(
        config.MENU_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    content = soup.find("div", class_="content") or soup.find("table")
    if content is None:
        raise ValueError("식단표 영역을 찾지 못했습니다. 사이트 구조가 바뀌었을 수 있습니다.")

    lines = [line.strip() for line in content.get_text().split("\n") if line.strip()]
    if not lines:
        raise ValueError("식단표가 비어 있습니다.")

    # 사이트가 오늘과 내일 식단을 구분 없이 한 번에 내려주는 경우가 있어서,
    # 하루 시작을 알리는 "조식열량"이 두 번째로 나오는 지점부터는 잘라내고
    # 첫 번째 날(오늘) 것만 남깁니다.
    breakfast_starts = [i for i, line in enumerate(lines) if re.match(r"^조식\s*열량", line)]
    if len(breakfast_starts) >= 2:
        lines = lines[: breakfast_starts[1]]

    final = []
    for line in lines:
        if any(word in line for word in ("중식", "석식")):
            final.append("─" * 20)
        final.append(line)
    return "\n".join(final)


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
    """크롤링 후 임베드를 만듭니다.

    requests는 동기 호출이라 이벤트 루프를 막지 않도록 스레드로 넘깁니다.
    """
    return make_embed(await asyncio.to_thread(fetch_menu))
