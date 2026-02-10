import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import asyncio

# 봇 설정 정보
TOKEN = "MTQ3MDc4NjkzMTYyNDM3ODQyOA.Gc8jH1.0Umn3lvWjS6Yy4NgM_boz0idhl3irYexUzidC4"
# 식단을 올릴 채널 ID (메시지를 보낼 채널 우클릭 -> ID 복사)
CHANNEL_ID = 1470221003597680773 

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

def get_buspia_menu():
    try:
        url = "https://www.buspia.co.kr/m/intranet/subpage/my/foodtable.php"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content = soup.find('div', class_='content') or soup.find('table')
        if content:
            lines = content.get_text().split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            final_lines = []
            for line in cleaned_lines:
                if any(word in line for word in ["중식", "석식"]):
                    final_lines.append("─" * 20)
                final_lines.append(line)
            return "\n".join(final_lines)
        return "식단표 내용을 읽어올 수 없습니다."
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

@bot.event
async def on_ready():
    print(f'{bot.user.name} 연결 성공!')
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        menu_data = get_buspia_menu()
        embed = discord.Embed(
            title="🏢 명예회장님의 오늘의 식단 브리핑", 
            description=f"**날짜: {datetime.now().strftime('%Y년 %m월 %d일')}**\n\n{menu_data}", 
            color=15158332
        )
        embed.set_footer(text="오늘도 안전 운행하십시오. 대원여객 파이팅!")
        await channel.send(embed=embed)
    
    # 메시지 전송 후 봇 종료 (GitHub Actions용)
    await bot.close()

if __name__ == "__main__":
    bot.run(TOKEN)
