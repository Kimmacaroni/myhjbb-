/**
 * 슬래시 명령어 정의. `scripts/register-commands.mjs`(로컬 실행용)와
 * `src/index.ts`의 `/setup/register-commands` 라우트(Worker 자체 실행용)가
 * 같은 정의를 씁니다.
 */

const OPTION_TYPE = { STRING: 3, INTEGER: 4, CHANNEL: 7 } as const;
const PERMISSIONS = { MANAGE_GUILD: String(1 << 5), MANAGE_ROLES: String(1 << 28) };
const GUILD_TEXT_CHANNEL = 0;

export const COMMAND_DEFINITIONS = [
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
    options: [{ name: "이름", description: "삭제할 칭호 이름", type: OPTION_TYPE.STRING, required: true }],
    default_member_permissions: PERMISSIONS.MANAGE_ROLES,
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
  {
    name: "교통정보",
    description: "현재 고속도로 돌발상황(사고/정체/통제)을 지금 불러옵니다.",
  },
  {
    name: "교통정보채널설정",
    description: "고속도로 돌발상황을 자동으로 알릴 채널을 지정합니다.",
    default_member_permissions: PERMISSIONS.MANAGE_GUILD,
    options: [
      {
        name: "채널",
        description: "알림을 보낼 채널 (생략하면 이 명령어를 쓴 채널)",
        type: OPTION_TYPE.CHANNEL,
        channel_types: [GUILD_TEXT_CHANNEL],
        required: false,
      },
    ],
  },
  {
    name: "교통정보채널해제",
    description: "고속도로 돌발상황 자동 알림을 끕니다.",
    default_member_permissions: PERMISSIONS.MANAGE_GUILD,
  },
  {
    name: "교통정보설정",
    description: "현재 교통정보 자동 알림 설정을 확인합니다.",
  },
];
