import type { Interaction, InteractionOption, ResolvedMember } from "./types";

export function getOption(interaction: Interaction, name: string): InteractionOption | undefined {
  return interaction.data?.options?.find((o) => o.name === name);
}

/**
 * 명령어에 딸려온 유저 정보를 찾습니다. 명령어를 친 본인이면 interaction.member
 * 에 이미 있고, `/경험치 유저:@누구` 처럼 다른 사람을 지정했으면 디스코드가
 * interaction.data.resolved 에 그 사람 정보를 함께 넣어 보내줍니다.
 */
export function resolvedMember(interaction: Interaction, userId: string): ResolvedMember | undefined {
  if (interaction.member && interaction.member.user.id === userId) {
    return { user: interaction.member.user, roles: interaction.member.roles };
  }
  const user = interaction.data?.resolved?.users?.[userId];
  if (!user) return undefined;
  const roles = interaction.data?.resolved?.members?.[userId]?.roles ?? [];
  return { user, roles };
}

export function mention(userId: string): string {
  return `<@${userId}>`;
}
