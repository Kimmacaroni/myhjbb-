import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 설정 정보
URL = "https://www.buspia.co.kr/m/intranet/subpage/my/foodtable.php"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1470778560297046099/yOSb2f6U9r6gmmQkxLhXzoDWOZGO07roGmYENovqT9b_UfhpB89rmAbCBuKee9jOP5sn"

def get_buspia_menu():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        content = soup.find('div', class_='content') or soup.find('table')
        
        if content:
            lines = content.get_text().split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            final_lines = []
            for line in cleaned_lines:
                # '중식'이나 '석식' 단어가 포함된 줄 앞에 구분선 추가
                if "중식" in line or "석식" in line:
                    final_lines.append("─" * 20) # 구분선 삽입
                final_lines.append(line)
            
            return "\n".join(final_lines)
        
        return "식단표 내용을 읽어올 수 없습니다."
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

def send_discord():
    menu_data = get_buspia_menu()
    
    payload = {
        "username": "명예회장봇",
        "embeds": [{
            "title": "🏢 명예회장님의 오늘의 식단 브리핑",
            "description": f"**날짜: {datetime.now().strftime('%Y년 %m월 %d일')}**\n\n{menu_data}",
            "color": 15158332,
            "footer": {"text": "사우가족여러분의 식사는 나 허명이가 책입집니다!"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    send_discord()
