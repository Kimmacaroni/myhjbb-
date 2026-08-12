/**
 * 경험치 · 레벨 명령어. Python 버전(cogs/leveling.py)에서 자동 채팅/통화방
 * 적립 로직만 뺀 것입니다 — 서버리스는 상시 연결이 없어 그 이벤트를 볼 수
 * 없으므로, 경험치는 이제 관리자가 명령어로만 지급/차감합니다.
 */
import * as db from "../db";
import { progress, progressBar } from "../levels";
import { addRole, removeRole, getMember, EPHEMERAL } from "../discord";
import type { Env, Interaction, InteractionResponse } from "../types";
import { getOption, parseUserId, mention } from "../interactions";
import { requirePermission, PERMISSIONS } from "../permissions";

const INVALID_USER_INPUT: InteractionResponse = {
  type: 4,
  data: { content: "유저를 멘션(@닉네임)하거나 유저 ID를 입력해 주세요.", flags: EPHEMERAL },
};

const MEMBER_NOT_FOUND: InteractionResponse = {
  type: 4,
  data: { content: "이 서버에서 해당 유저를 찾을 수 없습니다.", flags: EPHEMERAL },
};

/**
 * 레벨이 바뀌면 칭호(역할)를 다시 계산해 지급/회수합니다.
 * cogs/titles.py의 sync_member를 이식한 것으로, KEEP_ONLY_HIGHEST_TITLE=1과
 * 동일하게 최고 등급 칭호 하나만 유지합니다.
 */
export async function applyTitleSync(
  env: Env,
  guildId: string,
  userId: string,
  currentRoleIds: string[],
  level: number,
): Promise<void> {
  const titles = await db.getTitles(env.DB, guildId);
  if (titles.length === 0) return;

  const managedIds = new Set(titles.map((t) => t.role_id));
  const earned = titles.filter((t) => level >= t.level);
  const keep = earned.length > 0 ? new Set([earned[earned.length - 1].role_id]) : new Set<string>();
  const current = new Set(currentRoleIds.filter((id) => managedIds.has(id)));

  const toAdd = [...keep].filter((id) => !current.has(id));
  const toRemove = [...current].filter((id) => !keep.has(id));

  for (const roleId of toAdd) await addRole(env.DISCORD_TOKEN, guildId, userId, roleId);
  for (const roleId of toRemove) await removeRole(env.DISCORD_TOKEN, guildId, userId, roleId);
}

export async function handleShowXp(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const targetOption = getOption(interaction, "유저");
  const guildId = interaction.guild_id!;

  let targetId: string;
  let avatarHash: string | null | undefined;
  if (targetOption) {
    const parsed = parseUserId(targetOption.value as string);
    if (!parsed) return INVALID_USER_INPUT;
    const member = await getMember(env.DISCORD_TOKEN, guildId, parsed);
    if (!member) return MEMBER_NOT_FOUND;
    targetId = parsed;
    avatarHash = member.user.avatar;
  } else {
    targetId = interaction.member!.user.id;
    avatarHash = interaction.member!.user.avatar;
  }
  const avatarUrl = avatarHash
    ? `https://cdn.discordapp.com/avatars/${targetId}/${avatarHash}.png`
    : undefined;

  const row = await db.getUser(env.DB, guildId, targetId);
  const rank = await db.rankOf(env.DB, guildId, targetId);
  const p = progress(row.xp);

  return {
    type: 4,
    data: {
      embeds: [
        {
          title: `${mention(targetId)} 님의 활동 기록`,
          color: 0x5865f2,
          thumbnail: avatarUrl ? { url: avatarUrl } : undefined,
          fields: [
            { name: "레벨", value: `**${p.level}**`, inline: true },
            { name: "누적 경험치", value: row.xp.toLocaleString("ko-KR"), inline: true },
            { name: "순위", value: rank ? `${rank}위` : "—", inline: true },
            {
              name: `다음 레벨까지 (${p.earned.toLocaleString("ko-KR")} / ${p.needed.toLocaleString("ko-KR")})`,
              value: progressBar(p.earned, p.needed),
              inline: false,
            },
          ],
        },
      ],
    },
  };
}

export async function handleLeaderboard(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const countOption = getOption(interaction, "인원");
  const limit = Math.min(25, Math.max(1, Number(countOption?.value ?? 10)));
  const guildId = interaction.guild_id!;
  const rows = await db.leaderboard(env.DB, guildId, limit);

  if (rows.length === 0) {
    return {
      type: 4,
      data: { content: "아직 경험치를 쌓은 사람이 없습니다.", flags: EPHEMERAL },
    };
  }

  const medals: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };
  const lines = rows.map((row, idx) => {
    const rank = idx + 1;
    const prefix = medals[rank] ?? `\`${rank}.\``;
    return `${prefix} ${mention(row.user_id)} — Lv.${row.level} (${row.xp.toLocaleString("ko-KR")} XP)`;
  });

  return {
    type: 4,
    data: { embeds: [{ title: "📊 경험치 랭킹", description: lines.join("\n"), color: 0x5865f2 }] },
  };
}

async function adjustXp(
  env: Env,
  interaction: Interaction,
  targetInput: string,
  delta: number,
): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_ROLES);
  if (denied) return denied;

  const targetId = parseUserId(targetInput);
  if (!targetId) return INVALID_USER_INPUT;

  const guildId = interaction.guild_id!;
  const member = await getMember(env.DISCORD_TOKEN, guildId, targetId);
  if (!member) return MEMBER_NOT_FOUND;
  if (member.user.bot) {
    return { type: 4, data: { content: "봇에게는 경험치를 줄 수 없습니다.", flags: EPHEMERAL } };
  }

  const { before, after, xp } = await db.addXp(env.DB, guildId, targetId, delta);

  if (before !== after) {
    await applyTitleSync(env, guildId, targetId, member.roles, after);
  }

  const verb = delta >= 0 ? "지급" : "차감";
  return {
    type: 4,
    data: {
      embeds: [
        {
          title: `경험치 ${verb} 완료`,
          description: `${mention(targetId)} · **${Math.abs(delta).toLocaleString("ko-KR")} XP** ${verb}\n누적 **${xp.toLocaleString("ko-KR")} XP** · 레벨 **${before} → ${after}**`,
          color: delta >= 0 ? 0x57f287 : 0xed4245,
        },
      ],
    },
  };
}

export async function handleGiveXp(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const target = getOption(interaction, "유저")!.value as string;
  const amount = Number(getOption(interaction, "수량")!.value);
  return adjustXp(env, interaction, target, amount);
}

export async function handleTakeXp(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const target = getOption(interaction, "유저")!.value as string;
  const amount = Number(getOption(interaction, "수량")!.value);
  return adjustXp(env, interaction, target, -amount);
}

export async function handleSetXp(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_ROLES);
  if (denied) return denied;

  const targetInput = getOption(interaction, "유저")!.value as string;
  const targetId = parseUserId(targetInput);
  if (!targetId) return INVALID_USER_INPUT;

  const value = Number(getOption(interaction, "수량")!.value);
  const guildId = interaction.guild_id!;
  const current = await db.getUser(env.DB, guildId, targetId);
  return adjustXp(env, interaction, targetId, value - current.xp);
}
