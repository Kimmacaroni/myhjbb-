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

        # 식단표가 들어있는 영역 찾기
        content = soup.find('div', class_='content') or soup.find('table')
        
        if content:
            # 모든 텍스트를 가져온 뒤, 줄바꿈(\n) 단위로 쪼갭니다.
            lines = content.get_text().split('\n')
            
            # 각 줄에서 앞뒤 공백을 없애고(strip), 내용이 있는 줄만 골라냅니다.
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            # 골라낸 줄들을 다시 한 줄씩 줄바꿈으로 합칩니다.
            return "\n".join(cleaned_lines)
        
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
            "footer": {"text": "오늘도 안전 운행하십시오. 대원여객 파이팅!"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    send_discord()
