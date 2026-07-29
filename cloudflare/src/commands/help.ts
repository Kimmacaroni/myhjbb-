/**
 * /도움말. command-definitions.ts를 그대로 읽어서 목록을 만들기 때문에,
 * 명령어가 추가/변경돼도 이 파일을 따로 고칠 필요가 없습니다.
 */
import { COMMAND_DEFINITIONS } from "../command-definitions";
import type { Interaction, InteractionResponse } from "../types";

const PERMISSION_LABELS: Record<string, string> = {
  [String(1 << 28)]: "역할 관리",
  [String(1 << 5)]: "서버 관리",
};

interface CommandOption {
  name: string;
  required?: boolean;
}

function usageSignature(options: CommandOption[] | undefined): string {
  if (!options || options.length === 0) return "";
  return " " + options.map((o) => (o.required ? `<${o.name}>` : `[${o.name}]`)).join(" ");
}

export async function handleHelp(_env: unknown, _interaction: Interaction): Promise<InteractionResponse> {
  const everyone: string[] = [];
  const admin: string[] = [];

  for (const cmd of COMMAND_DEFINITIONS) {
    const line = `**/${cmd.name}${usageSignature(cmd.options)}** — ${cmd.description}`;
    const permissions = (cmd as { default_member_permissions?: string }).default_member_permissions;
    if (permissions) {
      const label = PERMISSION_LABELS[permissions] ?? "관리자";
      admin.push(`${line} *(${label} 권한 필요)*`);
    } else {
      everyone.push(line);
    }
  }

  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "📖 명령어 도움말",
          color: 0x5865f2,
          fields: [
            { name: "누구나 사용 가능", value: everyone.join("\n"), inline: false },
            { name: "관리자 전용", value: admin.join("\n"), inline: false },
          ],
          footer: { text: "<필수> · [생략 가능]" },
        },
      ],
    },
  };
}
