/**
 * 교통정보(고속도로 정체 구간) 명령어. 채널 설정 시 실제로 메시지를 보내볼
 * 수 있는지 즉시 테스트합니다 — cogs/menu.py·commands/menu.ts와 같은
 * 이유입니다.
 */
import * as db from "../db";
import { sendChannelMessage, editOriginalResponse, createFollowupMessage, DiscordRestError, EPHEMERAL } from "../discord";
import { requirePermission, PERMISSIONS } from "../permissions";
import { fetchIncidents, formatIncidentLinesByRoad, chunkLines } from "../traffic-source";
import type { Env, Interaction, InteractionResponse } from "../types";
import { getOption } from "../interactions";

const MAX_MESSAGE_LENGTH = 2000; // 디스코드 메시지 하나의 최대 글자 수
const MIN_POLL_INTERVAL_MINUTES = 5; // cron 하트비트(5분)보다 짧게는 설정할 수 없음
const MAX_POLL_INTERVAL_MINUTES = 360; // 6시간

/** 3초 안에 못 끝낼 수 있는 작업이라 index.ts가 먼저 "생각 중" 응답을 보낸 뒤 이 함수로 마무리합니다. */
export async function performTrafficNow(env: Env, interaction: Interaction): Promise<void> {
  if (!env.HIGHWAY_API_KEY) {
    await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, {
      content: "❌ 교통정보 API 키(HIGHWAY_API_KEY)가 아직 설정되지 않았습니다.",
    });
    return;
  }

  try {
    const incidents = await fetchIncidents(env.HIGHWAY_API_KEY);
    if (incidents.length === 0) {
      await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, {
        content: "✅ 현재 심한 정체 구간이 없습니다.",
      });
      return;
    }

    // 도로별로 나누지 않고 한 메시지 안에 고속도로별로 묶어 텍스트로
    // 모아 보여줍니다 — 그대로 복사해서 다른 곳에 전달하기 좋도록
    // 자동 알림(scheduled.ts)도 같은 텍스트 형식을 씁니다. 디스코드
    // 메시지 글자 수 제한(2000자)을 넘을 만큼 구간이 많을 때만 예외적으로
    // 여러 메시지로 나눠 보냅니다.
    const lines = [`현재 심한 정체 구간 (${incidents.length}건)`, ...formatIncidentLinesByRoad(incidents)];
    const [first, ...rest] = chunkLines(lines, MAX_MESSAGE_LENGTH);
    await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, { content: first });
    for (const content of rest) {
      await createFollowupMessage(env.DISCORD_APPLICATION_ID, interaction.token, { content });
    }
  } catch (err) {
    await editOriginalResponse(env.DISCORD_APPLICATION_ID, interaction.token, {
      content: `❌ 교통정보를 불러오지 못했습니다: ${(err as Error).message}`,
    });
  }
}

export async function handleSetTrafficChannel(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_GUILD);
  if (denied) return denied;

  const channelOption = getOption(interaction, "채널");
  const channelId = (channelOption?.value as string) ?? interaction.channel_id!;

  const intervalMinutes = await db.getTrafficPollIntervalMinutes(env.DB);
  try {
    await sendChannelMessage(env.DISCORD_TOKEN, channelId, {
      content: `✅ 이 채널에 고속도로 심한 정체 구간이 새로 생기면 ${intervalMinutes}분 이내로 알려드립니다. (설정 확인 메시지)`,
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

  await db.setTrafficChannel(env.DB, interaction.guild_id!, channelId);
  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "✅ 교통정보 채널이 설정되었습니다",
          description: `이제 <#${channelId}> 로 새로 시작된 고속도로 정체 구간을 자동으로 알려드립니다.`,
          color: 0x57f287,
        },
      ],
    },
  };
}

export async function handleUnsetTrafficChannel(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_GUILD);
  if (denied) return denied;

  await db.setTrafficChannel(env.DB, interaction.guild_id!, null);
  return {
    type: 4,
    data: { content: "🔕 교통정보 자동 알림을 껐습니다. `/교통정보채널설정` 으로 다시 켤 수 있습니다." },
  };
}

export async function handleTrafficSettings(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const guildId = interaction.guild_id!;
  const channelId = await db.getTrafficChannel(env.DB, guildId);
  const status = channelId ? `✅ 켜짐 — <#${channelId}>` : "🔕 꺼짐 — `/교통정보채널설정` 으로 켜세요.";
  const intervalMinutes = await db.getTrafficPollIntervalMinutes(env.DB);

  return {
    type: 4,
    data: {
      embeds: [
        {
          title: "🚧 교통정보 자동 알림 설정",
          color: 0xe67e22,
          fields: [
            { name: "상태", value: status, inline: false },
            { name: "확인 주기", value: `${intervalMinutes}분마다 (모든 서버 공통 — /교통정보주기설정 으로 변경)`, inline: false },
          ],
        },
      ],
      flags: EPHEMERAL,
    },
  };
}

export async function handleSetTrafficInterval(env: Env, interaction: Interaction): Promise<InteractionResponse> {
  const denied = requirePermission(interaction, PERMISSIONS.MANAGE_GUILD);
  if (denied) return denied;

  const minutes = Number(getOption(interaction, "분")!.value);
  if (!Number.isInteger(minutes) || minutes < MIN_POLL_INTERVAL_MINUTES || minutes > MAX_POLL_INTERVAL_MINUTES) {
    return {
      type: 4,
      data: {
        content: `❌ 분은 ${MIN_POLL_INTERVAL_MINUTES}~${MAX_POLL_INTERVAL_MINUTES} 사이의 정수여야 합니다.`,
        flags: EPHEMERAL,
      },
    };
  }

  await db.setTrafficPollIntervalMinutes(env.DB, minutes);
  return {
    type: 4,
    data: {
      content:
        `✅ 교통정보 확인 주기를 ${minutes}분으로 설정했습니다.\n` +
        "이 설정은 서버별이 아니라 봇 전체에 공통으로 적용됩니다(교통정보 조회 자체가 서버 구분 없이 한 번에 이뤄지기 때문입니다).",
    },
  };
}
