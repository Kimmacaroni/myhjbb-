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

전국 고속도로를 다 알려주면 필요없는 지역 소식까지 너무 많이 와서,
수도권(서울/인천/경기) 주요 고속도로만 걸러서 알립니다. API 응답에는
지역 구분값이 따로 없고 도로 이름(routeName)만 있어서(예: "경부선",
"호남선"), 수도권을 지나는 노선명 키워드 목록으로 거릅니다
(CAPITAL_REGION_ROAD_KEYWORDS). 경부선·서해안선처럼 수도권 밖까지 뻗은
노선은 그 노선 전체가 걸러지므로(구간 단위 지역 판정은 이 API로는 할 수
없음), 지방 구간의 정체도 함께 잡힐 수 있습니다.

Cloudflare 버전(traffic-source.ts)과 로직을 맞춰 뒀습니다 — 한쪽만 고쳐서
동작이 달라지지 않도록, 형식을 바꿀 때는 두 파일을 같이 고쳐 주세요.
"""
import discord
import requests

HIGHWAY_API_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest"

_DIRECTION_LABEL = {"S": "기점 방향", "E": "종점 방향"}

# 수도권(서울/인천/경기)을 지나는 주요 고속도로 노선명 키워드입니다.
# routeName이 이 중 하나라도 포함하면 수도권 관련 도로로 봅니다.
#   경부(경부선), 서해안(서해안선), 영동(영동선), 중부(중부선·중부내륙선),
#   서울양양(서울양양선), 수도권(수도권제1순환선·수도권제2순환선),
#   평택시흥(평택시흥선), 경인(경인선·제2경인선)
CAPITAL_REGION_ROAD_KEYWORDS = [
    "경부", "서해안", "영동", "중부", "서울양양", "수도권", "평택시흥", "경인",
]


def is_capital_region_road(road_name: str | None) -> bool:
    """도로 이름이 수도권 주요 고속도로에 해당하는지 확인합니다."""
    if not road_name:
        return False
    return any(keyword in road_name for keyword in CAPITAL_REGION_ROAD_KEYWORDS)


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
        segment = " ".join(v for v in (conzone_name, direction) if v)
        speed = item.get("speed")
        speed_text = f"평균 속도 {speed}km/h" if speed else "정체 심함"

        incidents.append({
            "key": key,
            "message": f"{location or '구간 정보 없음'} 정체 중 ({speed_text})",
            "roadName": route_name,
            "kind": "정체",
            "startName": conzone_name,
            "segmentText": f"{segment or '구간 정보 없음'} 정체 중 ({speed_text})",
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
    incidents = parse_incidents(response.json())
    return [i for i in incidents if is_capital_region_road(i.get("roadName"))]


def format_incident_lines_by_road(incidents: list[dict]) -> list[str]:
    """/교통정보 명령어에서 한 메시지(텍스트) 안에 고속도로별로 묶어 보여줄 때 씁니다."""
    groups: dict[str, list[dict]] = {}
    for incident in incidents:
        road = incident.get("roadName") or "도로 정보 없음"
        groups.setdefault(road, []).append(incident)

    lines: list[str] = []
    for road, group in groups.items():
        lines.append(f"🚧 **{road}**")
        for incident in group:
            lines.append(f"- {incident['segmentText']}")
    return lines


def make_incident_embed(incident: dict) -> discord.Embed:
    title_parts = [p for p in (incident.get("roadName"), incident.get("kind")) if p]
    title = "🚧 " + (" · ".join(title_parts) if title_parts else "고속도로 정체")

    embed = discord.Embed(title=title, description=incident["message"], colour=0xED4245)
    if incident.get("startName"):
        embed.add_field(name="구간", value=incident["startName"], inline=False)
    return embed


def make_road_embeds(incidents: list[dict]) -> list[discord.Embed]:
    """30분마다 자동으로 보내는 알림(cogs/traffic.py)에서, 같은 고속도로의
    구간들을 임베드 하나로 묶어 보여줄 때 씁니다 — 도로마다 임베드가
    따로따로 오지 않도록."""
    groups: dict[str, list[dict]] = {}
    for incident in incidents:
        road = incident.get("roadName") or "도로 정보 없음"
        groups.setdefault(road, []).append(incident)

    return [
        discord.Embed(
            title=f"🚧 {road}",
            description="\n".join(f"- {incident['segmentText']}" for incident in group),
            colour=0xED4245,
        )
        for road, group in groups.items()
    ]
