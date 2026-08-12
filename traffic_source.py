"""고속도로 구간별 소통정보(교통량·속도·정체도) 조회.

한국도로공사(EX) Open API(data.ex.co.kr)의 "구간별 소통정보"
(trafficAmountByCongest) 서비스를 씁니다. 처음엔 "돌발정보"(사고/공사/
통제) API를 쓰려 했지만, 실제로 발급받아 확인해 보니 그런 사고/통제
설명이 있는 API가 아니라 도로 구간(VDS 센서)별 속도·교통량·소통등급
(grade) 숫자만 주는 API였습니다. 그래서 "돌발상황 알림" 대신 "심한 정체
구간 알림"으로 씁니다 — grade가 정체를 뜻하는 값일 때만 알림 대상으로
고릅니다. 사고/통제 자체는 이 API로는 알 수 없습니다.

HIGHWAY_API_KEY 환경변수로 API 키를 등록해야 동작합니다.

⚠️ grade 값의 정확한 인코딩(숫자 코드 "3"인지 "정체" 같은 텍스트인지)은
아직 실제 응답으로 확인되지 않았습니다. 숫자 "3"과, 텍스트 안에 "정체"가
포함된 경우를 모두 심한 정체로 인식하도록 방어적으로 작성했습니다.

Cloudflare 버전(traffic-source.ts)과 로직을 맞춰 뒀습니다 — 한쪽만 고쳐서
동작이 달라지지 않도록, 형식을 바꿀 때는 두 파일을 같이 고쳐 주세요.
"""
import discord
import requests

HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest"

_DIRECTION_LABEL = {"S": "기점 방향", "E": "종점 방향"}


def _is_severe_congestion(grade: str | None) -> bool:
    if not grade:
        return False
    return grade == "3" or "정체" in grade


def parse_incidents(raw: object) -> list[dict]:
    """API 응답(list 배열)에서 심한 정체 구간만 골라
    {key, message, roadName, kind, startName} 형태로 정리합니다."""
    if not isinstance(raw, dict):
        return []
    items = raw.get("list")
    if not isinstance(items, list):
        return []

    incidents = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _is_severe_congestion(item.get("grade")):
            continue

        route_no = item.get("routeNo")
        conzone_id = item.get("conzoneId")
        updown = item.get("updownTypeCode")
        key = "|".join(str(v) for v in (route_no, conzone_id, updown) if v)
        if not key:
            continue

        route_name = item.get("routeName")
        conzone_name = item.get("conzoneName")
        direction = _DIRECTION_LABEL.get(updown, updown) if updown else None
        location = " ".join(v for v in (route_name, conzone_name, direction) if v)
        speed = item.get("speed")
        speed_text = f"평균 속도 {speed}km/h" if speed else "정체 심함"

        incidents.append({
            "key": key,
            "message": f"{location or '구간 정보 없음'} 정체 중 ({speed_text})",
            "roadName": route_name,
            "kind": "정체",
            "startName": conzone_name,
        })
    return incidents


def fetch_incidents(api_key: str) -> list[dict]:
    """현재 심한 정체인 구간 목록을 받아옵니다.

    Raises:
        requests.RequestException: API를 호출하지 못한 경우.
    """
    response = requests.get(
        HIGHWAY_API_URL,
        params={"key": api_key, "type": "json"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    response.raise_for_status()
    return parse_incidents(response.json())


def make_incident_embed(incident: dict) -> discord.Embed:
    title_parts = [p for p in (incident.get("roadName"), incident.get("kind")) if p]
    title = "🚧 " + (" · ".join(title_parts) if title_parts else "고속도로 정체")

    embed = discord.Embed(title=title, description=incident["message"], colour=0xED4245)
    if incident.get("startName"):
        embed.add_field(name="구간", value=incident["startName"], inline=False)
    return embed
