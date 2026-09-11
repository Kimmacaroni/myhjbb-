"""한국어 TTS 음성 채널 재생 명령어."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from experimental.huggingface_korean_tts import HuggingFaceKoreanTTS, VOICE_OPTIONS
from voice_idle import cancel_idle, schedule_idle

log = logging.getLogger(__name__)

VOICE_CHOICES = [
    app_commands.Choice(name=description[:100], value=key)
    for key, description in VOICE_OPTIONS.items()
]


@app_commands.guild_only()
class KoreanTTS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tts = HuggingFaceKoreanTTS()
        self.guild_locks: dict[int, asyncio.Lock] = {}

    async def cog_load(self):
        self.warmup_task = asyncio.create_task(self._warmup())

    async def _warmup(self):
        started = time.perf_counter()
        try:
            await asyncio.to_thread(self.tts.warmup)
            log.info("TTS 기본 모델 준비 완료 %.3fs", time.perf_counter() - started)
        except Exception:
            log.exception("TTS 사전 준비 실패; 다음 요청에서 다시 시도합니다")

    def _lock(self, guild_id: int) -> asyncio.Lock:
        return self.guild_locks.setdefault(guild_id, asyncio.Lock())

    @app_commands.command(name="음성", description="입력한 한국어 문장을 음성 채널에서 읽습니다.")
    @app_commands.describe(
        내용="봇이 읽을 문장 (최대 300자)",
        목소리="사용할 목소리. 선택하지 않으면 빠른 한국어 음성",
        말투="예: 차분하고 진지하게, 밝고 신나게",
    )
    @app_commands.choices(목소리=VOICE_CHOICES)
    async def speech(
        self,
        interaction: discord.Interaction,
        내용: app_commands.Range[str, 1, 300],
        목소리: app_commands.Choice[str] | None = None,
        말투: app_commands.Range[str, 1, 100] | None = None,
    ):
        received = time.perf_counter()
        member_voice = getattr(interaction.user, "voice", None)
        if not member_voice or not member_voice.channel:
            await interaction.response.send_message(
                "먼저 음성 채널에 들어가 주세요.", ephemeral=True
            )
            return

        voice = interaction.guild.voice_client
        cancel_idle(self.bot, interaction.guild.id)
        if voice and (voice.is_playing() or voice.is_paused()):
            await interaction.response.send_message(
                "현재 음악 또는 음성을 재생 중입니다. 끝난 뒤 다시 시도해 주세요.", ephemeral=True
            )
            return
        if self._lock(interaction.guild.id).locked():
            await interaction.response.send_message(
                "이미 음성을 만들고 있습니다. 잠시 후 다시 시도해 주세요.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        selected = 목소리.value if 목소리 else "fast_korean"
        await interaction.edit_original_response(content=(
            "🔊 빠른 한국어 음성을 준비하고 있습니다."
            if selected == "fast_korean" else
            "🔊 고품질 음성을 준비하고 있습니다. 이 목소리는 CPU 서버에서 수십 초 걸릴 수 있습니다."
        ))
        output = Path(tempfile.gettempdir()) / f"honorary-tts-{interaction.id}.wav"

        async with self._lock(interaction.guild.id):
            async def generate():
                started = time.perf_counter()
                await self.tts.synthesize_async(
                    내용, output, voice=selected,
                    style=말투 or "따뜻하고 자연스러운 말투로 말해 주세요.",
                )
                log.info("TTS 생성 voice=%s chars=%d seconds=%.3f", selected, len(내용), time.perf_counter() - started)

            synthesis = asyncio.create_task(generate())
            try:
                if voice is None or not voice.is_connected():
                    voice = await member_voice.channel.connect(self_deaf=True)
                elif voice.channel != member_voice.channel:
                    await voice.move_to(member_voice.channel)
                    await interaction.guild.change_voice_state(
                        channel=member_voice.channel, self_deaf=True
                    )

                await asyncio.shield(synthesis)
                if voice.is_playing() or voice.is_paused():
                    raise RuntimeError("준비 중 다른 음악이 시작됐습니다. 재생 종료 후 다시 시도해 주세요.")

                finished = asyncio.get_running_loop().create_future()

                def after_playing(error: Exception | None):
                    def mark_finished():
                        if not finished.done():
                            finished.set_result(error)

                    self.bot.loop.call_soon_threadsafe(mark_finished)

                voice.play(discord.FFmpegPCMAudio(str(output)), after=after_playing)
                log.info("TTS 재생 시작 voice=%s total_seconds=%.3f", selected, time.perf_counter() - received)
                await interaction.edit_original_response(content="🔊 음성을 재생합니다.")
                error = await finished
                if error:
                    raise RuntimeError(str(error))
            except Exception as exc:
                log.exception("TTS 생성 또는 재생 실패")
                await interaction.followup.send(f"❌ 음성 생성에 실패했습니다: {exc}", ephemeral=True)
            finally:
                # 실행 중인 모델 스레드가 파일을 다 쓴 뒤 임시 파일을 정리한다.
                await asyncio.gather(synthesis, return_exceptions=True)
                output.unlink(missing_ok=True)
                if voice and voice.is_connected() and not voice.is_playing():
                    schedule_idle(self.bot, interaction.guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(KoreanTTS(bot))
