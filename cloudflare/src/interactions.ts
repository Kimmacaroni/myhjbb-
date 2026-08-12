import type { Interaction, InteractionOption } from "./types";

export function getOption(interaction: Interaction, name: string): InteractionOption | undefined {
  return interaction.data?.options?.find((o) => o.name === name);
}

// 자릿수를 실제 스노우플레이크 길이(17~19자리)로 엄격히 제한하지 않습니다 —
// 잘못된 ID는 어차피 getMember()의 REST 조회에서 404로 걸러지므로, 여기서는
// "숫자로만 이루어졌는지"만 확인합니다.
const MENTION_RE = /^<@!?(\d{1,20})>$/;
const ID_RE = /^\d{1,20}$/;

/**
 * 유저 지정 옵션(멘션 또는 ID 텍스트)에서 유저 ID를 뽑아냅니다.
 *
 * 디스코드 기본 USER 타입 옵션을 쓰지 않는 이유: USER 타입의 선택 목록은
 * 명령어를 입력하는 채널을 볼 수 있는 사람만 후보로 보여주는 디스코드
 * 클라이언트 제약이 있습니다. 관리자 전용 채널에서 일반 멤버를 대상으로
 * 지정해야 하는 경우 후보에 아예 뜨지 않으므로, 대신 멘션/ID를 텍스트로
 * 받아 여기서 직접 파싱합니다.
 */
export function parseUserId(input: string): string | null {
  const trimmed = input.trim();
  const mentionMatch = trimmed.match(MENTION_RE);
  if (mentionMatch) return mentionMatch[1];
  return ID_RE.test(trimmed) ? trimmed : null;
}

export function mention(userId: string): string {
  return `<@${userId}>`;
}
