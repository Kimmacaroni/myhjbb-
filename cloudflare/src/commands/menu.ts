/**
 * 식단 명령어. Python 버전(cogs/menu.py)의 이식이지만, 채널 설정 시 실제로
 * 메시지를 보내볼 수 있는지 즉시 테스트합니다 — 상시 연결이 없는 서버리스라
 * 캐시된 권한 정보가 없으므로, "될지 안 될지 계산"하는 대신 "실제로 보내보고
 * 확인"하는 방식이 더 정확합니다.
 */
import * as db from "../db";
import { sendChannelMessage, editOriginalResponse, DiscordRestError, EPHEMERAL } from "../discord";
import { requirePermission, PERMISSIONS } from "../permissions";
import { fetchMenu, makeMenuEmbed, MENU_HOUR_KST } from "../menu-source";
import type { Env, Interaction, InteractionResponse } from "../types";
import { getOption } from "../interactions";

/** 3초 안에 못 끝낼 수 있는 작업이라 일단 "생각 중" 응답을 보냅니다. */
export function handleMenuNowDefer(): InteractionResponse {
  return { type: 5 };
}

/** 위 defer 이후 실제 크롤링을 마치고 최종 응답으로 편집합니다. */
export async function performMenuNow(env: Env, interaction: Interaction): Promise<void> {
  try {
    const menuText = await fetchMenu();
    await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, {
      embeds: [makeMenuEmbed(menuText)],
    });
  } catch (err) {
    await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, {
      content: `❌ 식단을 불러오지 못했습니다: ${(err as Error).message}`,
    });
  }
}

export async function handleSetMenuChannel(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_GUILD);
  if (denied) return denied;

  const channelOption = getOption(interaction, "채널");
  const channelId = (channelOption?.value as string) ?? interaction.channel_id!;

  try {
    await sendChannelMessage(env.DISCORD_TOKEN, channelId, {
      content: `✅ 이 채널에 매일 ${MENU_HOUR_KST}시(KST) 식단표를 자동으로 보냅니다. (설정 확인 메시지)`,
    });
  } catch (err) {
    const reason =
      err instanceof DiscordRestError && err.status === 403
        ? "봇에게 이 채널의 `메시지 보내기`/`링크 첨부` 권한이 없습니다."
        : `${(err as Error).message}`;
    return {
      type: 4,
      data: { content: `❌ <#${channelId}> 에 메시지를 보낼 수 없습니다: ${reason}`, flags: EPHEMERAL },
    };
  }

  await db.setMenuChannel(env.DB, interaction.guild_id!, channelId);
  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "✅ 식단 채널이 설정되었습니다",
          description: `이제 매일 **${MENU_HOUR_KST}시(KST)** 에 <#${channelId}> 로 식단표를 보냅니다.`,
          color: 0x57f287,
        },
      ],
    },
  };
}

export async function handleUnsetMenuChannel(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_GUILD);
  if (denied) return denied;

  await db.setMenuChannel(env.DB, interaction.guild_id!, null);
  return {
    type: 4,
    data: { content: "🔕 식단 자동 전송을 껐습니다. `/식단채널설정` 으로 다시 켤 수 있습니다." },
  };
}

export async function handleMenuSettings(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const guildId = interaction.guild_id!;
  const channelId = await db.getMenuChannel(env.DB, guildId);
  const status = channelId ? `✅ 켜짐 — <#${channelId}>` : "🔕 꺼짐 — `/식단채널설정` 으로 켜세요.";

  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "🍚 식단 자동 전송 설정",
          color: 0xe67e22,
          fields: [
            { name: "상태", value: status, inline: false },
            { name: "전송 시각", value: `매일 ${MENU_HOUR_KST}시 (KST)`, inline: false },
          ],
        },
      ],
      flags: EPHEMERAL,
    },
  };
}
