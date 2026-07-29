/** 이 프로젝트에서 실제로 쓰는 필드만 담은 최소 타입 정의입니다. */

export interface Env {
  DB: D1Database;
  DISCORD_TOKEN: string;
  DISCORD_PUBLIC_KEY: string;
  DISCORD_APPLICATION_ID: string;
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

export interface ResolvedMember {
  user: DiscordUser;
  roles: string[];
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
