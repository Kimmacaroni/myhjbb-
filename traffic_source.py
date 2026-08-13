"""고속도로 정체 구간(구간별 소통정보) 조회.

한국도로공사(EX) Open API(data.ex.co.kr)의 "구간별 소통정보"
(trafficAmountByCongest) 서비스를 씁니다. 처음엔 "돌발정보"(사고/공사/
통제) API를 쓰려 했지만, 실제로 발급받아 확인해 보니 그런 사고/통제
설명이 있는 API가 아니었습니다.

실제 응답을 두 번 받아 확인한 결과, 이 API는 이름(...ByCongest) 그대로
**이미 정체로 분류된 구간만** 돌려주는 것으로 보입니다 — 두 응답 모두
모든 항목의 grade가 "3"으로 동일했습니다. 그래서 grade로 다시 거르지
않고, 응답에 있는 구간을 그대로 알림 대상으로 씁니다. 대신 같은
구간(conzone)에 VDS 센서가 여러 개 있어 항목이 중복으로 오므로, 구간당
속도가 가장 낮은(가장 정체가 심한) 값 하나만 남깁니다.

HIGHWAY_API_KEY 환경변수로 API 키를 등록해야 동작합니다.

Cloudflare 버전(traffic-source.ts)과 로직을 맞춰 뒀습니다 — 한쪽만 고쳐서
동작이 달라지지 않도록, 형식을 바꿀 때는 두 파일을 같이 고쳐 주세요.
"""
import discord
import requests

HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest"

_DIRECTION_LABEL = {"S": "기점 방향", "E": "종점 방향"}


def _segment_key(item: dict) -> str:
    return "|".join(
        str(v) for v in (item.get("routeNo"), item.get("conzoneId"), item.get("updownTypeCode")) if v
    )


def _to_speed(speed: str | None) -> float:
    try:
        return float(speed)
    except (TypeError, ValueError):
        return float("inf")


def parse_incidents(raw: object) -> list[dict]:
    """API 응답(list 배열)을 구간(conzone) 단위로 합쳐
    {key, message, roadName, kind, startName} 형태로 정리합니다."""
    if not isinstance(raw, dict):
        return []
    items = raw.get("list")
    if not isinstance(items, list):
        return []

    # 같은 구간에 VDS 센서가 여러 개 잡히면, 그중 속도가 가장 낮은(가장
    # 막히는) 값만 남깁니다.
    worst_by_segment: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _segment_key(item)
        if not key:
            continue
        existing = worst_by_segment.get(key)
        if existing is None or _to_speed(item.get("speed")) < _to_speed(existing.get("speed")):
            worst_by_segment[key] = item

    incidents = []
    for key, item in worst_by_segment.items():
        route_name = item.get("routeName")
        conzone_name = item.get("conzoneName")
        updown = item.get("updownTypeCode")
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
    """현재 정체 중인 구간 목록을 받아옵니다.

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


def format_incident_lines(incidents: list[dict]) -> list[str]:
    """/교통정보 명령어에서 도로별로 나누지 않고 한 메시지(텍스트)로 모아 보여줄 때 씁니다."""
    return [f"🚧 {incident['message']}" for incident in incidents]


def make_incident_embed(incident: dict) -> discord.Embed:
    title_parts = [p for p in (incident.get("roadName"), incident.get("kind")) if p]
    title = "🚧 " + (" · ".join(title_parts) if title_parts else "고속도로 정체")

    embed = discord.Embed(title=title, description=incident["message"], colour=0xED4245)
    if incident.get("startName"):
        embed.add_field(name="구간", value=incident["startName"], inline=False)
    return embed
