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
```

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
