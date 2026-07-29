"""GitHub Actions 전용 식단 전송 스크립트 (단발 실행).

24시간 호스팅 없이 식단 기능만 쓰고 싶을 때 사용합니다. 워크플로가 정해진
시각에 이 스크립트를 실행하면 식단을 한 번 보내고 즉시 종료합니다.

경험치·레벨·칭호 시스템은 채팅과 통화방을 계속 지켜봐야 하므로 이 방식으로는
동작하지 않습니다. 그쪽은 `bot.py` 를 상시 실행해야 합니다.

필요한 환경변수 (GitHub Secrets 로 등록):
    DISCORD_TOKEN    봇 토큰
    MENU_CHANNEL_ID  식단을 올릴 채널 ID

실패하면 0이 아닌 코드로 종료하므로 Actions 실행이 빨갛게 표시됩니다.
조용히 실패해서 며칠 뒤에야 알게 되는 상황을 막기 위한 것입니다.
"""
import asyncio
import logging
import sys

import discord

import config
import menu_source

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("menu-oneshot")


async def send_menu() -> None:
    # 이벤트를 받을 필요가 없으므로 인텐트는 전부 끕니다.
    client = discord.Client(intents=discord.Intents.none())
    error: BaseException | None = None

    @client.event
    async def on_ready():
        nonlocal error
        try:
            # 캐시가 비어 있으므로 get_channel 대신 REST로 직접 조회합니다.
            channel = await client.fetch_channel(config.MENU_CHANNEL_ID)
            await channel.send(embed=await menu_source.build_embed())
            log.info("식단 전송 완료 → #%s", getattr(channel, "name", channel.id))
        except BaseException as exc:
            error = exc
        finally:
            # 여기서 닫아야 아래 start()가 반환되고 스크립트가 끝납니다.
            await client.close()

    # 로그인 자체가 실패하면 on_ready가 오지 않으므로 start()가 예외를 던집니다.
    # 이벤트를 기다리는 방식으로 짜면 이 경우 영원히 멈춰 있게 됩니다.
    try:
        await client.start(config.TOKEN)
    finally:
        if not client.is_closed():
            await client.close()

    if error is not None:
        raise error


def main() -> int:
    if not config.TOKEN:
        log.error(
            "DISCORD_TOKEN 이 없습니다. 저장소 Settings > Secrets and variables > "
            "Actions 에서 DISCORD_TOKEN 을 등록하세요."
        )
        return 1
    if not config.MENU_CHANNEL_ID:
        log.error("MENU_CHANNEL_ID 가 없습니다. 같은 곳에 채널 ID도 등록하세요.")
        return 1

    try:
        # 네트워크가 응답하지 않는 상황에서 러너를 붙잡고 있지 않도록 상한을 둡니다.
        asyncio.run(asyncio.wait_for(send_menu(), timeout=120))
    except asyncio.TimeoutError:
        log.error("2분 안에 전송을 마치지 못했습니다. 디스코드 연결을 확인하세요.")
        return 1
    except discord.LoginFailure:
        log.error("토큰이 올바르지 않습니다. 토큰을 재발급해 Secret 을 갱신하세요.")
        return 1
    except discord.NotFound:
        log.error("채널 %s 를 찾을 수 없습니다.", config.MENU_CHANNEL_ID)
        return 1
    except discord.Forbidden:
        log.error("채널 %s 에 메시지를 보낼 권한이 없습니다.", config.MENU_CHANNEL_ID)
        return 1
    except Exception:
        log.exception("식단 전송 실패")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
