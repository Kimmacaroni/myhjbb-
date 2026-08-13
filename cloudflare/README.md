# 명예회장봇 — Cloudflare Workers 버전

호스팅(VPS/라즈베리파이) 없이, **완전 무료 서버리스**로 슬래시 명령어를
운영하기 위한 버전입니다.

## 이 버전에서 빠진 것

**채팅/통화방 참여도에 따른 자동 경험치 적립은 없습니다.** Cloudflare
Workers는 요청이 올 때만 잠깐 실행되는 구조라, 디스코드와 상시 연결
(Gateway)을 유지하며 "누가 채팅 쳤다/통화방에 있다"를 실시간으로 감지할 수
없기 때문입니다. 그 대신:

- 경험치는 **`/경험치지급`, `/경험치차감`, `/경험치설정`으로 관리자가 수동
  지급**합니다.
- 레벨이 바뀌면 칭호(역할)는 **그대로 자동 지급/회수**됩니다 (명령어 처리
  시점에 REST API로 바로 반영되므로 상시 연결이 필요 없습니다).
- 식단 자동 전송은 Cron Trigger로 그대로 매일 실행됩니다.
- 고속도로 정체 구간(교통정보) 알림도 Cron Trigger(30분 간격)로 새로 생긴
  상황만 골라 전송합니다. `HIGHWAY_API_KEY` secret이 없으면 이 기능만
  조용히 꺼집니다.

`bot.py`(Python, 24시간 호스팅 필요)로 가면 채팅/통화방 자동 경험치까지 전부
쓸 수 있습니다 — 저장소 루트의 README를 참고하세요.

## 사전 준비

- [Cloudflare 계정](https://dash.cloudflare.com/sign-up) (무료)
- Node.js 18 이상
- 디스코드 개발자 포털에서 발급받은:
  - **Bot Token** (Bot 탭 → Reset Token)
  - **Public Key** (General Information 탭에 있음 — 토큰과 다른 값입니다!)
  - **Application ID** (General Information 탭)

## 1) 의존성 설치 & 로그인

```bash
cd cloudflare
npm install
npx wrangler login   # 브라우저가 열리며 Cloudflare 계정 인증
```

## 2) D1 데이터베이스 생성

```bash
npx wrangler d1 create honorary-bot
```

출력에 나오는 `database_id`를 복사해서 `wrangler.toml`의
`REPLACE_WITH_YOUR_D1_DATABASE_ID` 부분에 붙여넣으세요.

```bash
npm run d1:migrate:remote   # 실제 배포될 D1에 스키마 적용
```

## 3) 비밀값 등록

`wrangler.toml`에는 절대 토큰을 적지 않고, `secret`으로 등록합니다.
명령마다 값을 입력하라는 프롬프트가 뜹니다.

```bash
npx wrangler secret put DISCORD_TOKEN
npx wrangler secret put DISCORD_PUBLIC_KEY
npx wrangler secret put DISCORD_APPLICATION_ID
npx wrangler secret put HIGHWAY_API_KEY   # 교통정보 알림용. 선택 — 없으면 그 기능만 꺼집니다
```

`HIGHWAY_API_KEY`는 [data.ex.co.kr](https://data.ex.co.kr)(한국도로공사 Open
API)에서 무료로 회원가입 후 발급받을 수 있습니다.

## 3.5) daewon-dispatch Service Binding 연결

`/식단`은 같은 계정에 있는 `daewon-dispatch` Worker의 식단 API를 호출합니다.
그런데 Cloudflare는 **같은 계정 안의 `*.workers.dev` Worker끼리 일반
`fetch()`로 서로 호출하는 것을 막습니다** (무한 루프 방지 — 시도하면
`HTTP 404`, 오류 코드 `1042`가 뜹니다). 그래서 **Service Binding**이라는
전용 연결 방식이 꼭 필요합니다.

`wrangler.toml`에 바인딩 설정(`[[services]]`, binding명 `DAEWON_API`,
대상 `daewon-dispatch`)이 이미 들어 있지만, **Git 연동 배포(Workers
Builds)는 `wrangler.toml`의 바인딩을 자동으로 반영하지 않을 수 있습니다**
(cron 트리거도 같은 이유로 대시보드에서 따로 추가해야 했던 적이
있습니다). 그러니 대시보드에서도 직접 추가해 주세요:

1. Cloudflare 대시보드 → **Workers & Pages** → `honorary-bot` 선택
2. **Settings** → **Variables and Bindings** (또는 "변수 및 바인딩")
3. **Add binding** → **Service** 선택
4. Variable name: `DAEWON_API`, Service: `daewon-dispatch`, Environment:
   `production` 선택 후 저장
5. 저장하면 자동으로 재배포되거나, 안 되면 `Deployments` 탭에서 최신
   배포를 **Retry**/재배포

`npm run deploy`(wrangler CLI)로 직접 배포하는 경우에는 `wrangler.toml`에
있는 설정이 그대로 반영되므로 이 단계를 건너뛰어도 됩니다.

> 바인딩 없이도 코드는 동작합니다 — 바인딩이 없으면 일반 `fetch()`로
> 대체하도록 만들어 뒀지만, 그 경우 계정 내 Worker 간 호출 제한 때문에
> 다시 404가 뜹니다. `/setup/debug-menu` 진단 엔드포인트로 열어보면
> `[Service Binding: 사용함/설정 안 됨]` 표시로 바로 확인할 수 있습니다.

## 4) 배포

```bash
npm run deploy
```

성공하면 `https://honorary-bot.<your-subdomain>.workers.dev` 같은 주소가
출력됩니다. **이 주소를 복사해 두세요.**

## 5) 슬래시 명령어 등록

Worker 배포와 명령어 등록은 별개입니다. 로컬에서 한 번 실행하세요.

```bash
DISCORD_TOKEN=봇토큰 \
DISCORD_APPLICATION_ID=앱ID \
GUILD_ID=테스트서버ID \
node scripts/register-commands.mjs
```

`GUILD_ID`를 주면 그 서버에 **즉시** 반영됩니다 (테스트용으로 권장).
운영 단계에서 여러 서버에 배포하려면 `GUILD_ID` 없이 실행하세요 — 전역
등록되어 봇이 들어간 모든 서버에 적용되지만 반영까지 최대 1시간 걸립니다.

## 6) 디스코드에 Interactions Endpoint URL 등록

1. [Developer Portal](https://discord.com/developers/applications) → 해당 앱 → **General Information**
2. **Interactions Endpoint URL**에 4단계에서 받은 Worker 주소를 입력
   (예: `https://honorary-bot.your-subdomain.workers.dev`)
3. 저장 시 디스코드가 그 주소로 PING을 보내 서명 검증이 되는지 확인합니다.
   `INVALID SIGNATURE` 오류가 뜨면 `DISCORD_PUBLIC_KEY` secret 값이 맞는지
   확인하세요 (Bot Token이 아니라 Public Key입니다).

## 7) 봇 초대

`역할 관리(Manage Roles)`, `메시지 보내기`, `링크 첨부` 권한과
**`applications.commands` 스코프**를 포함해 초대하세요. (Interactions
기반이라 `bot` 스코프만으로는 슬래시 명령어가 등록되지 않습니다.)

> ⚠️ 서버 설정 → 역할에서 **봇의 역할을 칭호 역할들보다 위로** 올려주세요.
> 디스코드는 봇이 자기보다 위에 있는 역할을 건드리지 못하게 막습니다.

## 확인

디스코드에서 `/식단설정`을 쳐서 응답이 오면 성공입니다. `/식단채널설정`으로
채널을 지정하면, 그 자리에서 바로 테스트 메시지를 보내봐서 권한을
확인합니다 — 실패하면 즉시 원인을 알려줍니다.

---

## 개발 · 테스트

```bash
npm run typecheck   # TypeScript 타입 검사
npm test            # 순수 로직 + 명령어 핸들러 단위 테스트
npm run dev          # 로컬에서 Worker 실행 (wrangler dev)
```

`npm test`는 Cloudflare D1을 Node의 내장 SQLite로, 디스코드 REST 호출과
식단 API(daewon-dispatch) 호출을 가짜 `fetch`로 대체해 검증합니다. 다만
실제 daewon-dispatch API가 응답 형식을 바꾸는 등의 문제는 로컬 테스트로
잡히지 않으므로, 배포 후에는 `/식단`을 직접 실행해 실제 API에서 식단이
제대로 오는지 확인하세요.

## 알려진 제약 (무료 요금제 기준)

Cloudflare Workers 무료 요금제는 호출 1회당 하위 요청(fetch 호출)이
**50개로 제한**됩니다.

- `/칭호동기화`는 멤버 1명당 최대 2개(역할 지급/회수)를 쓰므로, 한 번에
  **최대 20명**까지만 처리합니다. 남은 인원이 있으면 안내 메시지가 뜨고,
  명령어를 다시 실행하면 이어서 처리됩니다.
- 매일 식단 전송(Cron)도 서버 수가 아주 많아지면(대략 45개 이상) 이 한도에
  걸릴 수 있습니다. 개인/소규모 커뮤니티 용도라면 문제되지 않습니다.
- 무료 요금제는 Cron Trigger를 하루 최대 몇백 회까지 지원하므로, 30분마다
  도는 교통정보 스케줄(하루 48회)은 문제없습니다.

### 교통정보는 "돌발상황" API가 아니라 "소통정보(정체)" API입니다

처음엔 사고/공사/통제 설명이 있는 "돌발정보" API를 쓰려 했지만, 실제
발급받아 확인해 보니 그런 API가 아니라 **도로 구간(VDS 센서)별
속도·교통량·소통등급(grade) 숫자만 주는 API**
(`data.ex.co.kr/openapi/odtraffic/trafficAmountByCongest`)였습니다. 그래서
"돌발상황 알림" 대신 "심한 정체 구간 알림"으로 동작합니다 — 사고나 통제
자체는 이 API로 알 수 없습니다.

응답 필드(`stdDate`, `stdHour`, `vdsId`, `trafficAmout`, `speed`,
`shareRatio`, `timeAvg`, `grade`, `routeNo`, `routeName`,
`updownTypeCode`, `conzoneId`, `conzoneName`, `code`, `message`,
`count`)와 실제 값은 두 번 받아본 원본 응답으로 확인했습니다. **응답에
있는 항목은 모두 grade가 `"3"`으로 동일**했습니다 — 이름
(`...ByCongest`) 그대로 이 API 자체가 이미 정체로 분류된 구간만 돌려주는
것으로 보여서, grade로 다시 거르지 않고 응답에 있는 구간을 그대로 알림
대상으로 씁니다. 대신 같은 구간(conzone)에 VDS 센서가 여러 개 잡혀
항목이 중복으로 오므로, 구간당 속도가 가장 낮은 값 하나만 남깁니다
(`src/traffic-source.ts`의 `parseIncidents()`, `traffic_source.py`의
`parse_incidents()`).

`HIGHWAY_API_KEY` secret을 등록한 뒤 아래 주소를 열면 실제 원본 JSON을
확인할 수 있습니다 (`/setup/debug-menu`가 등록된 `HIGHWAY_API_KEY`로 서버
쪽에서 대신 조회해 주므로, 발급받은 키를 주소창에 직접 붙여넣을 필요가
없습니다):

```
https://honorary-bot.<subdomain>.workers.dev/setup/debug-menu?token=<SETUP_TOKEN>&target=traffic
```

응답에 있는 구간이 10개를 넘으면(정체가 몰리는 시간대, 기능을 처음 켰을
때 등) 디스코드 메시지 하나(임베드 최대 10개)로는 다 못 담아서, 여러
메시지로 나눠 전부 보냅니다 — 뒤쪽 구간이 조용히 누락되지 않습니다.
