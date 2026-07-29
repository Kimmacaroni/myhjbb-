import { EPHEMERAL } from "./discord";
import type { Interaction, InteractionResponse } from "./types";

export const PERMISSIONS = {
  MANAGE_ROLES: 1n << 28n,
  MANAGE_GUILD: 1n << 5n,
} as const;

const LABELS = new Map<bigint, string>([
  [PERMISSIONS.MANAGE_ROLES, "역할 관리"],
  [PERMISSIONS.MANAGE_GUILD, "서버 관리"],
]);

/** 권한이 없으면 안내 메시지를 반환하고, 있으면 null을 반환합니다. */
export function requirePermission(
  interaction: Interaction,
  bit: bigint,
): InteractionResponse | null {
  const perms = BigInt(interaction.member?.permissions ?? "0");
  if ((perms & bit) === 0n) {
    return {
      type: 4,
      data: {
        content: `이 명령어는 \`${LABELS.get(bit)}\` 권한이 있는 사람만 사용할 수 있습니다.`,
        flags: EPHEMERAL,
      },
    };
  }
  return null;
}
