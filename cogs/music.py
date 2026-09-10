"""음성 채널 음악 재생.

유튜브 URL 또는 검색어를 받아 오디오만 스트리밍합니다. 음원 파일을 서버에
내려받거나 저장하지 않으며, 서버마다 독립적인 대기열을 사용합니다.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

log = logging.getLogger(__name__)

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"

YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "default_search": "ytsearch",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

# VPS IP가 유튜브에서 자동 요청으로 차단될 때, 소유자가 제공한 쿠키 파일을
# 선택적으로 사용합니다. 파일이 없으면 기존 공개 검색 방식으로 동작합니다.
COOKIE_FILE = os.getenv("YTDLP_COOKIE_FILE", "").strip()
if COOKIE_FILE and os.path.isfile(COOKIE_FILE):
    YTDLP_OPTIONS["cookiefile"] = COOKIE_FILE
    log.info("유튜브 쿠키 파일을 사용합니다.")
elif COOKIE_FILE:
    log.warning("YTDLP_COOKIE_FILE 경로에 쿠키 파일이 없습니다: %s", COOKIE_FILE)


@dataclass
class Track:
    title: str
    webpage_url: str
    duration: int | None
    requester: str
    channel: discord.abc.Messageable


@dataclass
class PlayerState:
    queue: Deque[Track] = field(default_factory=deque)
    current: Track | None = None
    current_source: discord.PCMVolumeTransformer | None = None
    task: asyncio.Task | None = None
    volume: float = 0.5


@app_commands.guild_only()
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, PlayerState] = {}

    def _state(self, guild_id: int) -> PlayerState:
        return self.players.setdefault(guild_id, PlayerState())

    @staticmethod
    def _duration_text(seconds: int | None) -> str:
        if not seconds:
            return "알 수 없음"
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"

    @staticmethod
    def _extract(query: str) -> dict:
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
        if not info:
            raise RuntimeError("검색 결과를 찾지 못했습니다.")
        return info

    async def _track_from_query(
        self, query: str, requester: str, channel: discord.abc.Messageable
    ) -> Track:
        info = await asyncio.to_thread(self._extract, query)
        url = info.get("webpage_url") or info.get("original_url") or query
        return Track(
            title=info.get("title") or "제목을 알 수 없는 음악",
            webpage_url=url,
            duration=info.get("duration"),
            requester=requester,
            channel=channel,
        )

    async def _stream_url(self, track: Track) -> str:
        # 유튜브의 실제 스트림 주소는 만료될 수 있어 재생 직전에 다시 얻습니다.
        info = await asyncio.to_thread(self._extract, track.webpage_url)
        stream_url = info.get("url")
        if not stream_url:
            raise RuntimeError("오디오 스트림 주소를 찾지 못했습니다.")
        return stream_url

    async def _player_loop(self, guild: discord.Guild, state: PlayerState):
        voice = guild.voice_client
        try:
            while state.queue and voice and voice.is_connected():
                track = state.queue.popleft()
                state.current = track

                try:
                    stream_url = await self._stream_url(track)
                    audio = discord.FFmpegPCMAudio(
                        stream_url,
                        before_options=FFMPEG_BEFORE_OPTIONS,
                        options=FFMPEG_OPTIONS,
                    )
                    source = discord.PCMVolumeTransformer(audio, volume=state.volume)
                    state.current_source = source
                    finished = asyncio.get_running_loop().create_future()

                    def after_playing(error: Exception | None):
                        def mark_finished():
                            if not finished.done():
                                finished.set_result(error)

                        self.bot.loop.call_soon_threadsafe(mark_finished)

                    voice.play(source, after=after_playing)
                    await track.channel.send(
                        f"🎵 지금 재생: **{track.title}** ({self._duration_text(track.duration)})"
                    )
                    error = await finished
                    if error:
                        log.warning("음악 재생 오류: %s", error)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.exception("음악 재생 준비 실패")
                    await track.channel.send(f"❌ **{track.title}** 재생에 실패해 다음 곡으로 넘어갑니다: {exc}")
                finally:
                    state.current = None
                    state.current_source = None

            if voice and voice.is_connected() and not voice.is_playing():
                await voice.disconnect()
        except asyncio.CancelledError:
            if voice and voice.is_connected():
                await voice.disconnect()
            raise
        finally:
            state.task = None
            state.current = None
            state.current_source = None

    async def _connect_for(self, interaction: discord.Interaction) -> discord.VoiceClient | None:
        guild = interaction.guild
        member = interaction.user
        voice_state = getattr(member, "voice", None)
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message(
                "먼저 재생할 음성 채널에 들어가 주세요.", ephemeral=True
            )
            return None

        current = guild.voice_client
        if current and current.is_connected():
            if current.channel != voice_state.channel:
                state = self._state(guild.id)
                if current.is_playing() or state.queue:
                    await interaction.response.send_message(
                        f"이미 {current.channel.mention}에서 재생 중입니다.", ephemeral=True
                    )
                    return None
                await current.move_to(voice_state.channel)
            return current

        return await voice_state.channel.connect()

    @app_commands.command(name="재생", description="유튜브 URL 또는 검색어를 음성 채널에서 재생합니다.")
    @app_commands.describe(검색어="유튜브 URL 또는 가수명과 노래 제목")
    async def play(self, interaction: discord.Interaction, 검색어: str):
        voice = await self._connect_for(interaction)
        if voice is None:
            return

        await interaction.response.defer()
        try:
            track = await self._track_from_query(
                검색어, interaction.user.display_name, interaction.channel
            )
        except Exception as exc:
            log.exception("음악 검색 실패")
            message = f"❌ 음악을 찾지 못했습니다: {exc}"
            if "Sign in to confirm you're not a bot" in str(exc):
                message = (
                    "❌ 유튜브가 VPS 요청을 차단했습니다. 관리자에게 유튜브 쿠키 파일 "
                    "설정을 요청해 주세요. 자세한 방법은 서버 설정 안내를 확인하세요."
                )
            await interaction.followup.send(message, ephemeral=True)
            return

        state = self._state(interaction.guild.id)
        state.queue.append(track)
        if state.task is None or state.task.done():
            state.task = asyncio.create_task(self._player_loop(interaction.guild, state))
            await interaction.followup.send(f"🎶 재생 목록에 추가: **{track.title}**")
        else:
            await interaction.followup.send(
                f"📥 대기열에 추가: **{track.title}** ({self._duration_text(track.duration)})"
            )

    @app_commands.command(name="일시정지", description="현재 음악을 일시정지합니다.")
    async def pause(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client
        if not voice or not voice.is_playing():
            await interaction.response.send_message("지금 재생 중인 음악이 없습니다.", ephemeral=True)
            return
        voice.pause()
        await interaction.response.send_message("⏸️ 일시정지했습니다.")

    @app_commands.command(name="재개", description="일시정지한 음악을 다시 재생합니다.")
    async def resume(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client
        if not voice or not voice.is_paused():
            await interaction.response.send_message("일시정지된 음악이 없습니다.", ephemeral=True)
            return
        voice.resume()
        await interaction.response.send_message("▶️ 재생을 이어갑니다.")

    @app_commands.command(name="스킵", description="현재 음악을 건너뜁니다.")
    async def skip(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client
        if not voice or not (voice.is_playing() or voice.is_paused()):
            await interaction.response.send_message("건너뛸 음악이 없습니다.", ephemeral=True)
            return
        voice.stop()
        await interaction.response.send_message("⏭️ 다음 곡으로 넘어갑니다.")

    @app_commands.command(name="정지", description="대기열을 비우고 음악 재생을 끝냅니다.")
    async def stop(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        state.queue.clear()
        if state.task and not state.task.done():
            state.task.cancel()
        voice = interaction.guild.voice_client
        if voice and voice.is_connected():
            await voice.disconnect()
        await interaction.response.send_message("⏹️ 재생을 끝내고 음성 채널에서 나왔습니다.")

    @app_commands.command(name="대기열", description="현재 음악 대기열을 확인합니다.")
    async def queue(self, interaction: discord.Interaction):
        state = self._state(interaction.guild.id)
        lines: list[str] = []
        if state.current:
            lines.append(f"▶️ 현재 재생: **{state.current.title}**")
        if state.queue:
            lines.extend(
                f"{index}. **{track.title}** ({self._duration_text(track.duration)})"
                for index, track in enumerate(list(state.queue)[:10], start=1)
            )
            if len(state.queue) > 10:
                lines.append(f"… 외 {len(state.queue) - 10}곡")
        if not lines:
            lines.append("대기열이 비어 있습니다.")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="볼륨", description="음악 볼륨을 0~200%로 설정합니다.")
    @app_commands.describe(퍼센트="0~200 사이의 볼륨")
    async def volume(self, interaction: discord.Interaction, 퍼센트: app_commands.Range[int, 0, 200]):
        state = self._state(interaction.guild.id)
        state.volume = 퍼센트 / 100
        if state.current_source:
            state.current_source.volume = state.volume
        await interaction.response.send_message(f"🔊 볼륨을 **{퍼센트}%**로 설정했습니다.")

    async def cog_unload(self):
        for state in self.players.values():
            if state.task and not state.task.done():
                state.task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
