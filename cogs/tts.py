"""한국어 TTS 음성 채널 재생 명령어."""

from __future__ import annotations

import asyncio
import logging
import tempfile
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

    def _lock(self, guild_id: int) -> asyncio.Lock:
        return self.guild_locks.setdefault(guild_id, asyncio.Lock())

    @app_commands.command(name="음성", description="입력한 한국어 문장을 음성 채널에서 읽습니다.")
    @app_commands.describe(
        내용="봇이 읽을 문장 (최대 300자)",
        목소리="사용할 목소리. 선택하지 않으면 한국어 Sohee",
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
        output = Path(tempfile.gettempdir()) / f"honorary-tts-{interaction.id}.wav"

        async with self._lock(interaction.guild.id):
            try:
                if voice is None or not voice.is_connected():
                    voice = await member_voice.channel.connect(self_deaf=True)
                elif voice.channel != member_voice.channel:
                    await voice.move_to(member_voice.channel)
                    await interaction.guild.change_voice_state(
                        channel=member_voice.channel, self_deaf=True
                    )

                await self.tts.synthesize_async(
                    내용,
                    output,
                    voice=목소리.value if 목소리 else "sohee",
                    style=말투 or "따뜻하고 자연스러운 말투로 말해 주세요.",
                )

                finished = asyncio.get_running_loop().create_future()

                def after_playing(error: Exception | None):
                    def mark_finished():
                        if not finished.done():
                            finished.set_result(error)

                    self.bot.loop.call_soon_threadsafe(mark_finished)

                voice.play(discord.FFmpegPCMAudio(str(output)), after=after_playing)
                await interaction.followup.send("🔊 음성을 재생합니다.", ephemeral=True)
                error = await finished
                if error:
                    raise RuntimeError(str(error))
            except Exception as exc:
                log.exception("TTS 생성 또는 재생 실패")
                await interaction.followup.send(f"❌ 음성 생성에 실패했습니다: {exc}", ephemeral=True)
            finally:
                output.unlink(missing_ok=True)
                if voice and voice.is_connected() and not voice.is_playing():
                    schedule_idle(self.bot, interaction.guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(KoreanTTS(bot))
