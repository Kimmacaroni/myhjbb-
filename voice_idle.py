"""음성 채널 연결의 10분 유휴 퇴장을 공통 관리합니다."""

from __future__ import annotations

import asyncio
import logging
import struct
from types import MethodType

import discord
from discord.ext import commands
from discord.voice_state import VoiceConnectionState

log = logging.getLogger(__name__)
IDLE_SECONDS = 10 * 60
DISCOVERY_TIMEOUT_SECONDS = 3


class VoiceConnectionTimeout(TimeoutError):
    """The voice handshake timed out, rather than music lookup."""


async def discover_voice_ip(websocket):
    """Register before sending and retry lost UDP discovery packets in-place."""
    state = websocket._connection
    loop = websocket.loop
    packet = struct.pack('>HHI', 1, 70, state.ssrc) + bytes(66)
    result = loop.create_future()

    def deliver(data):
        if len(data) == 74 and data[:2] == b'\x00\x02':
            def complete():
                if not result.done():
                    result.set_result(data)
            loop.call_soon_threadsafe(complete)

    state.add_socket_listener(deliver)
    state._socket_reader.resume()
    try:
        for attempt in range(3):
            await loop.sock_sendall(state.socket, packet)
            try:
                data = await asyncio.wait_for(asyncio.shield(result), timeout=DISCOVERY_TIMEOUT_SECONDS)
            except TimeoutError:
                log.warning('음성 UDP 응답 대기: 시도 %d/3 (%s:%s)', attempt + 1,
                            state.endpoint_ip, state.voice_port)
                continue
            end = data.index(0, 8)
            ip = data[8:end].decode('ascii')
            port = struct.unpack_from('>H', data, 72)[0]
            log.info('음성 UDP 연결 확인 완료')
            return ip, port
        raise VoiceConnectionTimeout('Discord 음성 UDP 응답이 없습니다. 서버 네트워크 또는 음성 서버 경로를 확인해야 합니다.')
    finally:
        state.remove_socket_listener(deliver)
        if not result.done():
            result.cancel()


class ReliableVoiceState(VoiceConnectionState):
    async def _connect_websocket(self, resume):
        websocket = await super()._connect_websocket(resume)
        websocket.discover_ip = MethodType(discover_voice_ip, websocket)
        return websocket


class ReliableVoiceClient(discord.VoiceClient):
    def create_connection_state(self):
        return ReliableVoiceState(self)

    async def connect(self, **kwargs):
        try:
            return await super().connect(**kwargs)
        except TimeoutError as exc:
            raise VoiceConnectionTimeout('Discord 음성 연결 시간이 초과됐습니다. 음악 검색 실패가 아닙니다.') from exc


def _tasks(bot: commands.Bot) -> dict[int, asyncio.Task]:
    tasks = getattr(bot, "voice_idle_tasks", None)
    if tasks is None:
        tasks = {}
        setattr(bot, "voice_idle_tasks", tasks)
    return tasks


def cancel_idle(bot: commands.Bot, guild_id: int) -> None:
    task = _tasks(bot).pop(guild_id, None)
    if task and not task.done():
        task.cancel()


def schedule_idle(bot: commands.Bot, guild: discord.Guild) -> None:
    """마지막 음성 명령으로부터 10분 후, 재생 중이 아니면 퇴장합니다."""
    cancel_idle(bot, guild.id)

    async def leave_when_idle() -> None:
        try:
            await asyncio.sleep(IDLE_SECONDS)
            voice = guild.voice_client
            if voice and voice.is_connected():
                if voice.is_playing():
                    schedule_idle(bot, guild)
                else:
                    await voice.disconnect()
                    log.info("[%s] 음성 채널 10분 유휴로 자동 퇴장", guild.name)
        except asyncio.CancelledError:
            pass
        finally:
            current = _tasks(bot).get(guild.id)
            if current is asyncio.current_task():
                _tasks(bot).pop(guild.id, None)

    _tasks(bot)[guild.id] = asyncio.create_task(leave_when_idle())
