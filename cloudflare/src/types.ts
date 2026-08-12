/** 이 프로젝트에서 실제로 쓰는 필드만 담은 최소 타입 정의입니다. */

export interface Env {
  DB: D1Database;
  DISCORD_TOKEN: string;
  DISCORD_PUBLIC_KEY: string;
  DISCORD_APPLICATION_ID: string;
  /** /setup/register-commands 엔드포인트를 보호하는 임의의 비밀값. (선택) */
  SETUP_TOKEN?: string;
  /**
   * daewon-dispatch Worker로의 Service Binding. 같은 Cloudflare 계정 안의
   * *.workers.dev 주소끼리는 일반 fetch()로 서로를 호출할 수 없어(무한 루프
   * 방지를 위한 제한, HTTP 404/오류 코드 1042) Service Binding을 통해서만
   * 호출할 수 있습니다. 대시보드에서 바인딩을 추가하기 전에는 undefined일
   * 수 있으므로 선택 필드로 둡니다.
   */
  DAEWON_API?: Fetcher;
  /** 한국도로공사 Open API(data.ex.co.kr) 인증키. 없으면 교통정보 기능은 조용히 꺼집니다. */
  HIGHWAY_API_KEY?: string;
}

export interface DiscordUser {
  id: string;
  username: string;
  global_name?: string | null;
  avatar?: string | null;
  bot?: boolean;
}

export interface InteractionMember {
  user: DiscordUser;
  roles: string[];
  permissions: string;
  nick?: string | null;
}

export interface InteractionOption {
  name: string;
  type: number;
  value?: string | number | boolean;
  options?: InteractionOption[];
}

export interface Interaction {
  id: string;
  application_id: string;
  type: number;
  token: string;
  guild_id?: string;
  channel_id?: string;
  member?: InteractionMember;
  data?: {
    id: string;
    name: string;
    options?: InteractionOption[];
    resolved?: {
      users?: Record<string, DiscordUser>;
      members?: Record<string, { roles: string[]; nick?: string | null }>;
      channels?: Record<string, { id: string; name: string; type: number }>;
    };
  };
}

/** https://discord.com/developers/docs/interactions/receiving-and-responding */
export interface InteractionResponse {
  type: number;
  data?: {
    content?: string;
    embeds?: unknown[];
    flags?: number;
    choices?: { name: string; value: string }[];
  };
}
