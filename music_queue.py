"""현재 곡과 대기 곡을 구분해 보여주는 대기열 페이지."""
import math
import discord

PAGE_SIZE = 10


def queue_embed(current, waiting: list, page: int = 0) -> discord.Embed:
    pages = max(1, math.ceil(len(waiting) / PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    embed = discord.Embed(title=f"📋 대기열 · {len(waiting)}곡 대기",
                          colour=discord.Colour.blurple())
    current_title = discord.utils.escape_markdown(current.title[:200]) if current else None
    embed.add_field(name="▶️ 현재 재생", value=current_title or "현재 재생 중인 곡이 없습니다.",
                    inline=False)
    if waiting:
        lines = []
        start = page * PAGE_SIZE
        for index, track in enumerate(waiting[start:start + PAGE_SIZE], start=start + 1):
            title = discord.utils.escape_markdown(track.title[:200]).replace("\n", " ")
            lines.append(f"**{index}.** {title}")
        embed.description = "**⏳ 다음 재생 순서**\n" + "\n".join(lines)
    else:
        embed.description = "**⏳ 다음 재생 순서**\n대기 중인 곡이 없습니다. 재생할 곡을 추가해 주세요."
    embed.set_footer(text=f"{page + 1}/{pages}페이지 · 조회 시점의 목록 · 현재 곡은 대기 곡 수에서 제외")
    return embed


class QueueView(discord.ui.View):
    def __init__(self, current, waiting: list):
        super().__init__(timeout=180)
        self.current = current
        self.waiting = waiting
        self.page = 0
        self.pages = max(1, math.ceil(len(waiting) / PAGE_SIZE))
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=queue_embed(self.current, self.waiting, self.page), view=self)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.pages - 1, self.page + 1)
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=queue_embed(self.current, self.waiting, self.page), view=self)
