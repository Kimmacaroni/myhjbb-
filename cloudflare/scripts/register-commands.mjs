#!/usr/bin/env node
/**
 * 슬래시 명령어를 디스코드에 등록하는 스크립트. Worker와 별개로, 배포 전후에
 * 한 번씩 로컬에서 실행합니다 (Worker 안에서는 실행하지 않습니다).
 *
 * 사용법:
 *   DISCORD_TOKEN=... DISCORD_APPLICATION_ID=... node scripts/register-commands.mjs
 *
 *   GUILD_ID=... 를 함께 주면 그 서버에만 등록되어 반영이 즉시 됩니다 (테스트용).
 *   GUILD_ID 없이 실행하면 전역 등록되어 봇이 들어가 있는 모든 서버에
 *   적용되지만, 디스코드가 반영하는 데 최대 1시간 걸릴 수 있습니다.
 *
 * 로컬에서 discord.com 으로 나가는 네트워크가 막혀 있다면(예: 제한된
 * CI/샌드박스), 대신 배포된 Worker의 GET /setup/register-commands?token=...
 * 엔드포인트를 브라우저로 열어 등록할 수 있습니다 (src/index.ts 참고).
 *
 * ⚠️ 아래 명령어 목록은 src/command-definitions.ts 와 내용이 같아야 합니다.
 *    한쪽만 고치면 Worker 라우트와 이 스크립트의 등록 결과가 달라집니다.
 */

const TOKEN = process.env.DISCORD_TOKEN;
const APPLICATION_ID = process.env.DISCORD_APPLICATION_ID;
const GUILD_ID = process.env.GUILD_ID;

if (!TOKEN || !APPLICATION_ID) {
  console.error("DISCORD_TOKEN, DISCORD_APPLICATION_ID 환경변수가 필요합니다.");
  process.exit(1);
}

const OPTION_TYPE = { STRING: 3, INTEGER: 4, CHANNEL: 7 };
const PERMISSIONS = { MANAGE_GUILD: String(1 << 5), MANAGE_ROLES: String(1 << 28) };
const GUILD_TEXT_CHANNEL = 0;

const commands = [
  {
    name: "도움말",
    description: "사용 가능한 명령어와 설명을 보여줍니다.",
  },
  {
    name: "경험치",
    description: "내 경험치와 레벨을 확인합니다.",
    options: [
      {
        name: "유저",
        description: "확인할 대상 — 멘션(@닉네임) 또는 유저 ID (생략하면 본인)",
        type: OPTION_TYPE.STRING,
        required: false,
      },
    ],
  },
  {
    name: "랭킹",
    description: "서버 경험치 순위를 보여줍니다.",
    options: [
      {
        name: "인원",
        description: "표시할 인원 수 (기본 10명)",
        type: OPTION_TYPE.INTEGER,
        required: false,
        min_value: 1,
        max_value: 25,
      },
    ],
  },
  {
    name: "경험치지급",
    description: "지정한 멤버에게 경험치를 지급합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
    options: [
      { name: "유저", description: "지급 대상 — 멘션(@닉네임) 또는 유저 ID", type: OPTION_TYPE.STRING, required: true },
      { name: "수량", description: "지급할 경험치", type: OPTION_TYPE.INTEGER, required: true, min_value: 1 },
    ],
  },
  {
    name: "경험치차감",
    description: "지정한 멤버의 경험치를 차감합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
    options: [
      { name: "유저", description: "차감 대상 — 멘션(@닉네임) 또는 유저 ID", type: OPTION_TYPE.STRING, required: true },
      { name: "수량", description: "차감할 경험치", type: OPTION_TYPE.INTEGER, required: true, min_value: 1 },
    ],
  },
  {
    name: "경험치설정",
    description: "멤버의 경험치를 특정 값으로 맞춥니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
    options: [
      { name: "유저", description: "대상 — 멘션(@닉네임) 또는 유저 ID", type: OPTION_TYPE.STRING, required: true },
      { name: "수량", description: "설정할 누적 경험치", type: OPTION_TYPE.INTEGER, required: true, min_value: 0 },
    ],
  },
  {
    name: "칭호추가",
    description: "칭호를 만들고 서버 역할로 자동 등록합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
    options: [
      { name: "이름", description: "칭호 이름 (역할 이름으로 그대로 사용)", type: OPTION_TYPE.STRING, required: true },
      { name: "레벨", description: "이 칭호를 획득하는 데 필요한 레벨", type: OPTION_TYPE.INTEGER, required: true, min_value: 0 },
      { name: "색상", description: "역할 색상 (예: #E74C3C)", type: OPTION_TYPE.STRING, required: false },
    ],
  },
  {
    name: "칭호삭제",
    description: "칭호와 해당 역할을 함께 삭제합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
    options: [{ name: "이름", description: "삭제할 칭호 이름", type: OPTION_TYPE.STRING, required: true }],
  },
  {
    name: "칭호목록",
    description: "등록된 칭호를 등급 순으로 보여줍니다.",
  },
  {
    name: "칭호동기화",
    description: "서버 멤버의 칭호를 현재 레벨에 맞게 다시 계산합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
  },
  {
    name: "식단",
    description: "오늘의 식단표를 지금 불러옵니다.",
  },
  {
    name: "식단채널설정",
    description: "식단을 매일 자동으로 올릴 채널을 지정합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_GUILD,
    options: [
      {
        name: "채널",
        description: "식단을 올릴 채널 (생략하면 이 명령어를 쓴 채널)",
        type: OPTION_TYPE.CHANNEL,
        channel_types: [GUILD_TEXT_CHANNEL],
        required: false,
      },
    ],
  },
  {
    name: "식단채널해제",
    description: "식단 자동 전송을 끕니다.",
    default_member_permissions: PERMISSIONS.MANAGE_GUILD,
  },
  {
    name: "식단설정",
    description: "현재 식단 자동 전송 설정을 확인합니다.",
  },
];

const path = GUILD_ID
  ? `/applications/${APPLICATION_ID}/guilds/${GUILD_ID}/commands`
  : `/applications/${APPLICATION_ID}/commands`;

const res = await fetch(`https://discord.com/api/v10${path}`, {
  method: "PUT",
  headers: { Authorization: `Bot ${TOKEN}`, "Content-Type": "application/json" },
  body: JSON.stringify(commands),
});

if (!res.ok) {
  console.error(`등록 실패 (HTTP ${res.status}):`, await res.text());
  process.exit(1);
}

const registered = await res.json();
console.log(`✅ 명령어 ${registered.length}개 등록 완료 (${GUILD_ID ? `서버 ${GUILD_ID}에 즉시 반영` : "전역 등록, 최대 1시간 소요"})`);
for (const c of registered) console.log(`   /${c.name}`);
