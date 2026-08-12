"""고속도로 돌발상황(사고/공사/기타통제/기상통제) 조회.

한국도로공사(EX) Open API(data.ex.co.kr) "돌발정보" 서비스를 씁니다.
data.ex.co.kr에서 무료로 API 키를 발급받아 HIGHWAY_API_KEY 환경변수로
등록해야 동작합니다.

⚠️ 필드 이름은 공개된 문서를 기준으로 최선으로 맞춘 것입니다. 실제 키를
발급받아 연결한 뒤 응답을 직접 확인해 다듬어야 할 수 있습니다 — 식단
API(daewon-dispatch)를 처음 연결했을 때와 같은 과정입니다. 응답 형태가
예상과 달라도 parse_incidents()가 조용히 빈 리스트를 돌려줄 뿐 죽지는
않습니다.

Cloudflare 버전(traffic-source.ts)과 로직을 맞춰 뒀습니다 — 한쪽만 고쳐서
동작이 달라지지 않도록, 형식을 바꿀 때는 두 파일을 같이 고쳐 주세요.
"""
import discord
import requests

HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/trafficapi/eventInfo"


def _fallback_key(item: dict) -> str:
    return "|".join(
        str(v) for v in (item.get("roadName"), item.get("startName"), item.get("endName"),
                          item.get("startDate"), item.get("startTime"))
        if v
    )


def parse_incidents(raw: object) -> list[dict]:
    """API 응답(list 배열)을 {key, message, roadName, kind, startName, endName} 형태로 정리합니다."""
    if not isinstance(raw, dict):
        return []
    items = raw.get("list")
    if not isinstance(items, list):
        return []

    incidents = []
    for item in items:
        if not isinstance(item, dict):
            continue
        message = item.get("msg") or item.get("message")
        if not message:
            continue
        key = str(item.get("key") or _fallback_key(item))
        if not key:
            continue
        incidents.append({
            "key": key,
            "message": message,
            "roadName": item.get("roadName"),
            "kind": item.get("kind") or item.get("gubun"),
            "startName": item.get("startName"),
            "endName": item.get("endName"),
        })
    return incidents


def fetch_incidents(api_key: str) -> list[dict]:
    """현재 등록된 고속도로 돌발상황 목록을 받아옵니다.

    Raises:
        requests.RequestException: API를 호출하지 못한 경우.
    """
    response = requests.get(
        HIGHWAY_API_URL, params={"key": api_key, "type": "json"}, timeout=10
    )
    response.raise_for_status()
    return parse_incidents(response.json())


def make_incident_embed(incident: dict) -> discord.Embed:
    title_parts = [p for p in (incident.get("roadName"), incident.get("kind")) if p]
    title = "🚧 " + (" · ".join(title_parts) if title_parts else "고속도로 돌발상황")

    embed = discord.Embed(title=title, description=incident["message"], colour=0xED4245)
    section = " ~ ".join(p for p in (incident.get("startName"), incident.get("endName")) if p)
    if section:
        embed.add_field(name="구간", value=section, inline=False)
    return embed
