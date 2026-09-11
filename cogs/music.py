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
from music_helpers import duration_text, progress_text
from voice_idle import cancel_idle, schedule_idle
from voice_playback import start_playback

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
    # YouTube의 최신 JavaScript 검증 스크립트를 Deno로 받아 실행합니다.
    "remote_components": ["ejs:npm"],
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
    thumbnail: str | None
    requester: str
    channel: discord.abc.Messageable
    start_at: int = 0


@dataclass
class PlayerState:
    queue: Deque[Track] = field(default_factory=deque)
    current: Track | None = None
    current_source: discord.PCMVolumeTransformer | None = None
    task: asyncio.Task | None = None
    volume: float = 0.5
    started_at: float = 0.0
    progress_task: asyncio.Task | None = None
    dashboard_message: discord.Message | None = None


class MusicSearchModal(discord.ui.Modal, title="명예회장봇 음악 재생"):
    query = discord.ui.TextInput(
        label="유튜브 URL 또는 가수 · 노래 제목",
        placeholder="예: 아이유 좋은날 또는 유튜브 URL",
        max_length=300,
    )

    def __init__(self, cog: "Music"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.play.callback(self.cog, interaction, self.query.value)


class MusicSeekModal(discord.ui.Modal, title="재생 위치 이동"):
    seconds = discord.ui.TextInput(label="이동할 시점(초)", placeholder="예: 90 = 1분 30초", max_length=6)

    def __init__(self, cog: "Music"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            seconds = int(self.seconds.value)
        except ValueError:
            await interaction.response.send_message("0 이상의 숫자로 입력해 주세요.", ephemeral=True)
            return
        await self.cog.seek.callback(self.cog, interaction, seconds)


class MusicDashboardView(discord.ui.View):
    """재시작 뒤에도 유지되는 음악 대시보드 버튼 모음입니다."""

    def __init__(self, cog: "Music"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="재생", emoji="🎵", style=discord.ButtonStyle.primary, custom_id="honorary_music:play")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MusicSearchModal(self.cog))

    @discord.ui.button(label="대기열", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="honorary_music:queue")
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.queue.callback(self.cog, interaction)

    @discord.ui.button(label="일시정지", emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="honorary_music:pause")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.pause.callback(self.cog, interaction)

    @discord.ui.button(label="스킵", emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="honorary_music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip.callback(self.cog, interaction)

    @discord.ui.button(label="이동", emoji="⏩", style=discord.ButtonStyle.secondary, custom_id="honorary_music:seek")
    async def seek_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MusicSeekModal(self.cog))

    @discord.ui.button(label="정지", emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="honorary_music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.stop.callback(self.cog, interaction)


@app_commands.guild_only()
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, PlayerState] = {}
        self.dashboard_channels: set[int] = set()

    async def cog_load(self):
        self.bot.add_view(MusicDashboardView(self))

    def _is_dashboard_channel(self, channel: discord.abc.GuildChannel | discord.abc.Messageable) -> bool:
        return (
            getattr(channel, "id", None) in self.dashboard_channels
            or getattr(channel, "name", None) == "회장님의-뮤직피아"
        )

    async def _delete_later(self, message: discord.Message, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """대시보드 채널의 일반 채팅은 조작 화면을 깔끔하게 유지합니다."""
        if message.author.bot or not self._is_dashboard_channel(message.channel):
            return
        self.dashboard_channels.add(message.channel.id)
        asyncio.create_task(self._delete_later(message, 5))

    def _state(self, guild_id: int) -> PlayerState:
        return self.players.setdefault(guild_id, PlayerState())

    def _dashboard_embed(self, track: Track | None = None, state: PlayerState | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="🎧 명예회장봇 음악 채널",
            description=(
                "회장님의 뮤직피아에 오신 것을 환영합니다.\n"
                "아래 버튼으로 음악을 재생하고 관리하세요."
            ),
            colour=discord.Colour.dark_blue(),
        )
        embed.add_field(
            name="🎵 버튼 사용법",
            value=(
                "**재생** — 곡명 또는 유튜브 URL 입력\n"
                "**대기열** — 현재 재생·다음 곡 확인\n"
                "**일시정지 / 스킵 / 정지** — 재생 상태 제어"
            ),
            inline=False,
        )
        embed.add_field(
            name="💬 슬래시 명령어 예시",
            value=(
                "`/재생 아이유 좋은날`\n"
                "`/재생 https://www.youtube.com/watch?v=...`\n"
                "`/볼륨 70` · `/재개` · `/대기열`"
            ),
            inline=False,
        )
        if track and state:
            progress = progress_text(
                start_at=track.start_at,
                duration=track.duration,
                started_at=state.started_at,
                now=asyncio.get_running_loop().time(),
            )
            embed.add_field(
                name="🎶 지금 재생 중",
                value=f"**{track.title}**\n{progress}\n신청: {track.requester}",
                inline=False,
            )
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
        else:
            embed.add_field(name="🎶 지금 재생 중", value="현재 재생 중인 곡이 없습니다.", inline=False)
        embed.set_footer(text="명예회장봇 · 음성 채널 음악 대시보드")
        return embed

    async def _find_dashboard_message(self, guild: discord.Guild, state: PlayerState) -> discord.Message | None:
        if state.dashboard_message:
            return state.dashboard_message
        channel = discord.utils.get(guild.text_channels, name="회장님의-뮤직피아")
        if not channel:
            return None
        self.dashboard_channels.add(channel.id)
        try:
            pins = await channel.pins()
        except (discord.Forbidden, discord.HTTPException):
            return None
        for message in pins:
            if message.author == guild.me and message.embeds and message.embeds[0].title == "🎧 명예회장봇 음악 채널":
                state.dashboard_message = message
                return message
        return None

    async def _update_progress(self, message: discord.Message, track: Track, state: PlayerState):
        try:
            while state.current is track:
                await asyncio.sleep(5)
                if state.current is track:
                    await message.edit(embed=self._dashboard_embed(track, state), view=MusicDashboardView(self))
        except (asyncio.CancelledError, discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

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
            thumbnail=info.get("thumbnail"),
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
                state.started_at = asyncio.get_running_loop().time()

                try:
                    stream_url = await self._stream_url(track)
                    audio = discord.FFmpegPCMAudio(
                        stream_url,
                        before_options=(
                            f"-ss {track.start_at} {FFMPEG_BEFORE_OPTIONS}"
                            if track.start_at else FFMPEG_BEFORE_OPTIONS
                        ),
                        options=FFMPEG_OPTIONS,
                    )
                    source = discord.PCMVolumeTransformer(audio, volume=state.volume)
                    state.current_source = source
                    finished = start_playback(voice, source)
                    dashboard_message = await self._find_dashboard_message(guild, state)
                    if dashboard_message:
                        await dashboard_message.edit(
                            embed=self._dashboard_embed(track, state), view=MusicDashboardView(self)
                        )
                        state.progress_task = asyncio.create_task(
                            self._update_progress(dashboard_message, track, state)
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
                    if state.progress_task:
                        state.progress_task.cancel()
                        state.progress_task = None
                    state.current = None
                    state.current_source = None

            if voice and voice.is_connected() and not voice.is_playing():
                schedule_idle(self.bot, guild)
            dashboard_message = await self._find_dashboard_message(guild, state)
            if dashboard_message:
                await dashboard_message.edit(
                    embed=self._dashboard_embed(), view=MusicDashboardView(self)
                )
        except asyncio.CancelledError:
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
        cancel_idle(self.bot, guild.id)
        if current and current.is_connected():
            if current.channel != voice_state.channel:
                state = self._state(guild.id)
                if current.is_playing() or state.queue:
                    await interaction.response.send_message(
                        f"이미 {current.channel.mention}에서 재생 중입니다.", ephemeral=True
                    )
                    return None
                await current.move_to(voice_state.channel)
                await guild.change_voice_state(channel=voice_state.channel, self_deaf=True)
            return current

        return await voice_state.channel.connect(self_deaf=True)

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
            confirmation = await interaction.followup.send(
                f"🎶 재생 목록에 추가: **{track.title}**", wait=True
            )
        else:
            confirmation = await interaction.followup.send(
                f"📥 대기열에 추가: **{track.title}** ({duration_text(track.duration)})",
                wait=True,
            )
        if self._is_dashboard_channel(interaction.channel):
            self.dashboard_channels.add(interaction.channel.id)
            asyncio.create_task(self._delete_later(confirmation, 10))

    @app_commands.command(name="일시정지", description="현재 음악을 일시정지합니다.")
    async def pause(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        voice = interaction.guild.voice_client
        if not voice or not voice.is_playing():
            await interaction.response.send_message("지금 재생 중인 음악이 없습니다.", ephemeral=True)
            return
        voice.pause()
        await interaction.response.send_message("⏸️ 일시정지했습니다.")
        schedule_idle(self.bot, interaction.guild)

    @app_commands.command(name="재개", description="일시정지한 음악을 다시 재생합니다.")
    async def resume(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        voice = interaction.guild.voice_client
        if not voice or not voice.is_paused():
            await interaction.response.send_message("일시정지된 음악이 없습니다.", ephemeral=True)
            return
        voice.resume()
        await interaction.response.send_message("▶️ 재생을 이어갑니다.")

    @app_commands.command(name="스킵", description="현재 음악을 건너뜁니다.")
    async def skip(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        voice = interaction.guild.voice_client
        if not voice or not (voice.is_playing() or voice.is_paused()):
            await interaction.response.send_message("건너뛸 음악이 없습니다.", ephemeral=True)
            return
        voice.stop()
        await interaction.response.send_message("⏭️ 다음 곡으로 넘어갑니다.")

    @app_commands.command(name="이동", description="현재 음악의 원하는 시점(초)으로 이동합니다.")
    @app_commands.describe(초="이동할 시점. 예: 90은 1분 30초")
    async def seek(self, interaction: discord.Interaction, 초: app_commands.Range[int, 0, 86400]):
        cancel_idle(self.bot, interaction.guild.id)
        state = self._state(interaction.guild.id)
        voice = interaction.guild.voice_client
        track = state.current
        if not track or not voice or not (voice.is_playing() or voice.is_paused()):
            await interaction.response.send_message("이동할 재생 중인 음악이 없습니다.", ephemeral=True)
            return
        if track.duration is not None and 초 >= track.duration:
            await interaction.response.send_message(
                f"곡 길이({duration_text(track.duration)}) 안의 시점을 입력해 주세요.",
                ephemeral=True,
            )
            return
        track.start_at = 초
        state.queue.appendleft(track)
        if state.progress_task:
            state.progress_task.cancel()
        voice.stop()
        await interaction.response.send_message(
            f"⏩ **{duration_text(초)}** 지점으로 이동합니다."
        )

    @app_commands.command(name="정지", description="대기열을 비우고 음악 재생을 끝냅니다.")
    async def stop(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        state = self._state(interaction.guild.id)
        state.queue.clear()
        if state.task and not state.task.done():
            state.task.cancel()
        voice = interaction.guild.voice_client
        await interaction.response.send_message("⏹️ 재생과 대기열을 정리했습니다. 봇은 음성 채널에 머무릅니다.")
        if voice and voice.is_connected():
            schedule_idle(self.bot, interaction.guild)

    @app_commands.command(name="퇴장", description="봇을 음성 채널에서 퇴장시킵니다.")
    async def leave(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        state = self._state(interaction.guild.id)
        state.queue.clear()
        if state.task and not state.task.done():
            state.task.cancel()
        voice = interaction.guild.voice_client
        if not voice or not voice.is_connected():
            await interaction.response.send_message("현재 음성 채널에 들어가 있지 않습니다.", ephemeral=True)
            return
        await voice.disconnect()
        await interaction.response.send_message("👋 음성 채널에서 퇴장했습니다.")

    @app_commands.command(name="대기열", description="현재 음악 대기열을 확인합니다.")
    async def queue(self, interaction: discord.Interaction):
        cancel_idle(self.bot, interaction.guild.id)
        state = self._state(interaction.guild.id)
        lines: list[str] = []
        if state.current:
            lines.append(f"▶️ 현재 재생: **{state.current.title}**")
        if state.queue:
            lines.extend(
                f"{index}. **{track.title}** ({duration_text(track.duration)})"
                for index, track in enumerate(list(state.queue)[:10], start=1)
            )
            if len(state.queue) > 10:
                lines.append(f"… 외 {len(state.queue) - 10}곡")
        if not lines:
            lines.append("대기열이 비어 있습니다.")
        await interaction.response.send_message("\n".join(lines))
        if interaction.guild.voice_client:
            schedule_idle(self.bot, interaction.guild)

    @app_commands.command(name="볼륨", description="음악 볼륨을 0~200%로 설정합니다.")
    @app_commands.describe(퍼센트="0~200 사이의 볼륨")
    async def volume(self, interaction: discord.Interaction, 퍼센트: app_commands.Range[int, 0, 200]):
        cancel_idle(self.bot, interaction.guild.id)
        state = self._state(interaction.guild.id)
        state.volume = 퍼센트 / 100
        if state.current_source:
            state.current_source.volume = state.volume
        await interaction.response.send_message(f"🔊 볼륨을 **{퍼센트}%**로 설정했습니다.")
        if interaction.guild.voice_client and not interaction.guild.voice_client.is_playing():
            schedule_idle(self.bot, interaction.guild)

    @app_commands.command(name="음악대시보드설정", description="음악 채널에 명예회장봇 조작 대시보드를 게시합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def dashboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel_name = "회장님의-뮤직피아"
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel is None:
            try:
                channel = await guild.create_text_channel(
                    channel_name,
                    reason="명예회장봇 음악 대시보드 생성",
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ 전용 채널을 만들 권한이 없습니다. 봇 역할에 `채널 관리` 권한을 주세요.",
                    ephemeral=True,
                )
                return

        embed = self._dashboard_embed()
        self.dashboard_channels.add(channel.id)
        state = self._state(guild.id)
        dashboard_message = await self._find_dashboard_message(guild, state)
        if dashboard_message:
            await dashboard_message.edit(embed=embed, view=MusicDashboardView(self))
        else:
            banner_path = "assets/honorary-music-dashboard-banner.png"
            try:
                file = discord.File(banner_path, filename="honorary-music-dashboard-banner.png")
                embed.set_image(url="attachment://honorary-music-dashboard-banner.png")
                dashboard_message = await channel.send(
                    embed=embed, view=MusicDashboardView(self), file=file
                )
            except FileNotFoundError:
                dashboard_message = await channel.send(embed=embed, view=MusicDashboardView(self))
            try:
                await dashboard_message.pin(reason="명예회장봇 음악 대시보드를 채널 상단에 고정")
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ 대시보드는 만들었지만 상단 고정 권한이 없습니다. 봇 역할에 `메시지 관리` 권한을 주세요.",
                    ephemeral=True,
                )
        state.dashboard_message = dashboard_message
        await interaction.followup.send(
            f"✅ {channel.mention} 채널에 대시보드를 게시하고 상단에 고정했습니다. 일반 채팅은 5초 후 자동 삭제됩니다.",
            ephemeral=True,
        )

    async def cog_unload(self):
        for state in self.players.values():
            if state.task and not state.task.done():
                state.task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
