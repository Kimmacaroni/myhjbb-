/**
 * 칭호(역할) 명령어. Python 버전(cogs/titles.py)의 이식입니다.
 *
 * ⚠️ Cloudflare Workers 무료 요금제는 호출 1회당 하위 요청(subrequest, 즉
 * 이 파일에서 만드는 fetch 호출 수)이 50개로 제한됩니다. `/칭호동기화`는
 * 멤버 1명당 최대 2개(역할 지급/회수)를 쓰므로, 멤버가 많은 서버에서는
 * 한 번에 다 못 끝낼 수 있습니다. 그래서 안전하게 한 번에 처리할 인원수를
 * 제한하고, 남은 인원이 있으면 다시 실행하라고 안내합니다.
 */
import * as db from "../db";
import {
  createRole,
  deleteRole,
  listRoles,
  editRolePositions,
  listGuildMembers,
  rest,
  EPHEMERAL,
} from "../discord";
import { requirePermission, PERMISSIONS } from "../permissions";
import { applyTitleSync } from "./leveling";
import type { Env, Interaction, InteractionResponse } from "../types";
import { getOption } from "../interactions";

const MAX_MEMBERS_PER_SYNC = 20;

export function parseColour(value: string | undefined): number {
  if (!value) return 0;
  const hex = value.replace(/^#/, "");
  const parsed = parseInt(hex, 16);
  return Number.isNaN(parsed) ? 0 : parsed;
}

async function getBotTopRolePosition(env: Env, guildId: string): Promise<number> {
  const me = await rest(env.DISCORD_TOKEN, "GET", "/users/@me").then((r) => r.json<{ id: string }>());
  const member = await rest(env.DISCORD_TOKEN, "GET", `/guilds/${guildId}/members/${me.id}`).then((r) =>
    r.json<{ roles: string[] }>(),
  );
  const roles = await listRoles(env.DISCORD_TOKEN, guildId);
  const positions = roles.filter((r) => member.roles.includes(r.id)).map((r) => r.position);
  return positions.length > 0 ? Math.max(...positions) : 0;
}

/** 요구 레벨이 높은 칭호일수록 역할 목록 위쪽에 오도록 정렬합니다. */
export async function reorderTitleRoles(env: Env, guildId: string): Promise<void> {
  const titles = await db.getTitles(env.DB, guildId); // 레벨 오름차순
  if (titles.length === 0) return;

  const guildRoles = await listRoles(env.DISCORD_TOKEN, guildId);
  const guildRoleIds = new Set(guildRoles.map((r) => r.id));
  const botTop = await getBotTopRolePosition(env, guildId);

  // 봇이 실제로 옮길 수 있는 역할만 남깁니다 (존재하고, 봇보다 아래인 것).
  const movable = titles.filter((t) => {
    const role = guildRoles.find((r) => r.id === t.role_id);
    return guildRoleIds.has(t.role_id) && role !== undefined && role.position < botTop;
  });
  if (movable.length === 0) return;

  const base = Math.max(1, botTop - movable.length);
  const positions = movable.map((t, idx) => ({ id: t.role_id, position: base + idx }));
  await editRolePositions(env.DISCORD_TOKEN, guildId, positions);
}

export async function handleAddTitle(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_ROLES);
  if (denied) return denied;

  const guildId = interaction.guild_id!;
  const name = getOption(interaction, "이름")!.value as string;
  const level = Number(getOption(interaction, "레벨")!.value);
  const colourInput = getOption(interaction, "색상")?.value as string | undefined;

  if (await db.findTitleByName(env.DB, guildId, name)) {
    return { type: 4, data: { content: `이미 \`${name}\` 칭호가 있습니다.`, flags: EPHEMERAL } };
  }

  const role = await createRole(env.DISCORD_TOKEN, guildId, {
    name,
    color: parseColour(colourInput),
    hoist: true,
  });
  await db.addTitle(env.DB, guildId, role.id, name, level);
  await reorderTitleRoles(env, guildId);

  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "✅ 칭호가 추가되었습니다",
          description: `<@&${role.id}> · 필요 레벨 **${level}**\n\n새 칭호를 기존 멤버에게도 반영하려면 \`/칭호동기화\` 를 실행하세요.`,
          color: parseColour(colourInput),
        },
      ],
    },
  };
}

export async function handleRemoveTitle(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_ROLES);
  if (denied) return denied;

  const guildId = interaction.guild_id!;
  const name = getOption(interaction, "이름")!.value as string;
  const title = await db.findTitleByName(env.DB, guildId, name);
  if (!title) {
    return { type: 4, data: { content: `\`${name}\` 칭호를 찾을 수 없습니다.`, flags: EPHEMERAL } };
  }

  await deleteRole(env.DISCORD_TOKEN, guildId, title.role_id).catch(() => {
    // 역할이 이미 지워졌을 수도 있습니다. DB 기록은 어차피 마저 정리합니다.
  });
  await db.deleteTitle(env.DB, guildId, title.role_id);
  await reorderTitleRoles(env, guildId);

  return { type: 4, data: { content: `🗑️ \`${name}\` 칭호를 삭제했습니다.` } };
}

export async function handleListTitles(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const guildId = interaction.guild_id!;
  const titles = await db.getTitles(env.DB, guildId);
  if (titles.length === 0) {
    return {
      type: 4,
      data: { content: "아직 등록된 칭호가 없습니다. `/칭호추가` 로 만들어 보세요.", flags: EPHEMERAL },
    };
  }

  const lines = [...titles]
    .reverse() // 높은 등급이 위로
    .map((t) => `**Lv.${t.level}** — <@&${t.role_id}>`);

  return {
    type: 4,
    data: { embeds: [{ title: "🏅 칭호 목록", description: lines.join("\n"), color: 0xf1c40f }] },
  };
}

export async function handleResyncTitles(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_ROLES);
  if (denied) return denied;

  const guildId = interaction.guild_id!;
  await reorderTitleRoles(env, guildId);

  const members = (await listGuildMembers(env.DISCORD_TOKEN, guildId)).filter((m) => !m.user.bot);
  const batch = members.slice(0, MAX_MEMBERS_PER_SYNC);

  for (const member of batch) {
    const row = await db.getUser(env.DB, guildId, member.user.id);
    await applyTitleSync(env, guildId, member.user.id, member.roles, row.level);
  }

  const remaining = members.length - batch.length;
  const note =
    remaining > 0
      ? `\n\n⚠️ 이번에 ${batch.length}명 처리했고 ${remaining}명이 남았습니다. \`/칭호동기화\` 를 다시 실행해 주세요.\n(Cloudflare Workers 무료 요금제의 요청 수 제한 때문에 한 번에 처리 가능한 인원이 제한됩니다.)`
      : "";

  return {
    type: 4,
    data: { content: `✅ 멤버 ${batch.length}명의 칭호를 동기화했습니다.${note}` },
  };
}
