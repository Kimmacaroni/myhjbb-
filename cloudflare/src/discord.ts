/**
 * 디스코드 연동 공통 유틸.
 *
 * - verifySignature: 인터랙션 요청이 진짜 디스코드에서 왔는지 확인 (Ed25519).
 *   순수 JS 구현(@noble/ed25519)을 쓰는 이유는 Cloudflare Workers에는
 *   Node의 discord-interactions 패키지가 의존하는 기능이 없기 때문입니다.
 * - rest(): 봇 토큰으로 디스코드 REST API를 호출하는 얇은 래퍼.
 */
import { verifyAsync } from "@noble/ed25519";

const API = "https://discord.com/api/v10";

export async function verifySignature(
  request: Request,
  publicKey: string,
): Promise<{ valid: boolean; body: string }> {
  const signature = request.headers.get("X-Signature-Ed25519");
  const timestamp = request.headers.get("X-Signature-Timestamp");
  const body = await request.text();

  if (!signature || !timestamp) {
    return { valid: false, body };
  }

  const valid = await verifyAsync(
    hexToBytes(signature),
    new TextEncoder().encode(timestamp + body),
    hexToBytes(publicKey),
  );
  return { valid, body };
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}

export class DiscordRestError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`Discord API ${status}: ${body}`);
  }
}

export async function rest(
  token: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bot ${token}`,
      "Content-Type": "application/json",
      "User-Agent": "HonoraryBot (cloudflare-workers, 1.0)",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    throw new DiscordRestError(res.status, await res.text());
  }
  return res;
}

// ── 채널 ──────────────────────────────────────────────

export async function sendChannelMessage(
  token: string,
  channelId: string,
  payload: { embeds?: unknown[]; content?: string },
): Promise<void> {
  await rest(token, "POST", `/channels/${channelId}/messages`, payload);
}

// ── 역할 ──────────────────────────────────────────────

export async function createRole(
  token: string,
  guildId: string,
  params: { name: string; color?: number; hoist?: boolean },
): Promise<{ id: string }> {
  const res = await rest(token, "POST", `/guilds/${guildId}/roles`, {
    name: params.name,
    color: params.color ?? 0,
    hoist: params.hoist ?? true,
  });
  return res.json();
}

export async function deleteRole(token: string, guildId: string, roleId: string): Promise<void> {
  await rest(token, "DELETE", `/guilds/${guildId}/roles/${roleId}`);
}

export async function addRole(
  token: string,
  guildId: string,
  userId: string,
  roleId: string,
): Promise<void> {
  await rest(token, "PUT", `/guilds/${guildId}/members/${userId}/roles/${roleId}`);
}

export async function removeRole(
  token: string,
  guildId: string,
  userId: string,
  roleId: string,
): Promise<void> {
  await rest(token, "DELETE", `/guilds/${guildId}/members/${userId}/roles/${roleId}`);
}

export interface DiscordRole {
  id: string;
  name: string;
  position: number;
}

export async function listRoles(token: string, guildId: string): Promise<DiscordRole[]> {
  const res = await rest(token, "GET", `/guilds/${guildId}/roles`);
  return res.json();
}

export async function editRolePositions(
  token: string,
  guildId: string,
  positions: { id: string; position: number }[],
): Promise<void> {
  await rest(token, "PATCH", `/guilds/${guildId}/roles`, positions);
}

export interface GuildMember {
  user: { id: string; username: string; bot?: boolean };
  roles: string[];
}

/** 서버 멤버 전체 목록. Discord API 한도(1회 최대 1000명)라 페이지네이션합니다. */
export async function listGuildMembers(token: string, guildId: string): Promise<GuildMember[]> {
  const members: GuildMember[] = [];
  let after = "0";
  for (;;) {
    const res = await rest(
      token,
      "GET",
      `/guilds/${guildId}/members?limit=1000&after=${after}`,
    );
    const page: GuildMember[] = await res.json();
    members.push(...page);
    if (page.length < 1000) break;
    after = page[page.length - 1].user.id;
  }
  return members;
}

// ── 인터랙션 응답(webhook) ───────────────────────────

/** 처음 3초 안에 못 끝낼 작업은 defer 후, 완료되면 이걸로 최종 응답을 채웁니다. */
export async function editOriginalResponse(
  applicationId: string,
  interactionToken: string,
  payload: { content?: string; embeds?: unknown[] },
): Promise<void> {
  await fetch(
    `${API}/webhooks/${applicationId}/${interactionToken}/messages/@original`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function createFollowupMessage(
  applicationId: string,
  interactionToken: string,
  payload: { content?: string; embeds?: unknown[]; flags?: number },
): Promise<void> {
  await fetch(`${API}/webhooks/${applicationId}/${interactionToken}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export const EPHEMERAL = 1 << 6;
