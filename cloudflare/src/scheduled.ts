/**
 * wrangler.toml의 cron 설정대로 실행되는 자동 전송 두 가지:
 * - sendDailyMenu: 매일 정해진 시각에 식단표 전송 (GitHub Actions 워크플로 대체)
 * - sendTrafficAlerts: 5분마다 고속도로 정체 구간 중 새로 정체가 시작된 곳만 전송
 *
 * ⚠️ Cloudflare Workers 무료 요금제는 호출 1회당 하위 요청 50개 제한이
 * 있습니다. 채널을 설정한 서버가 많으면(대략 45개 이상) 이 한도에 걸려
 * 일부 서버는 그날 전송이 안 될 수 있습니다. 개인/소규모 커뮤니티
 * 용도라면 문제되지 않지만, 여러 서버에 배포할 계획이면 유료 요금제나
 * 배치 처리가 필요합니다.
 */
import * as db from "./db";
import { sendChannelMessage } from "./discord";
import { fetchMenu, makeMenuEmbed } from "./menu-source";
import { fetchIncidents, makeIncidentEmbed } from "./traffic-source";
import type { Env } from "./types";

const MAX_EMBEDS = 10; // 디스코드 메시지 하나에 넣을 수 있는 임베드 최대 개수

export async function sendDailyMenu(env: Env): Promise<void> {
  const targets = await db.allMenuChannels(env.DB);
  if (targets.length === 0) {
    console.log("식단을 보낼 채널이 설정된 서버가 없습니다.");
    return;
  }

  let embed;
  try {
    embed = makeMenuEmbed(await fetchMenu(env.DAEWON_API));
  } catch (err) {
    console.error("식단 조회 실패 — 오늘 전송을 건너뜁니다.", err);
    return;
  }

  for (const { guildId, channelId } of targets) {
    try {
      await sendChannelMessage(env.DISCORD_TOKEN, channelId, { embeds: [embed] });
    } catch (err) {
      console.error(`식단 전송 실패 (guild ${guildId}, channel ${channelId})`, err);
    }
  }
}

/** 새로 정체가 시작된 구간만 골라 설정된 모든 채널에 알립니다. */
export async function sendTrafficAlerts(env: Env): Promise<void> {
  if (!env.HIGHWAY_API_KEY) return; // 키 미설정 시 조용히 건너뜁니다 (cron은 계속 돕니다)

  const targets = await db.allTrafficChannels(env.DB);
  if (targets.length === 0) return;

  let incidents;
  try {
    incidents = await fetchIncidents(env.HIGHWAY_API_KEY);
  } catch (err) {
    console.error("교통정보 조회 실패", err);
    return;
  }

  // 정체가 하나도 없어도(빈 배열) 반드시 호출해야 합니다 — 그래야 이전에
  // 정체였다가 지금은 풀린 구간이 기록에서 지워지고, 나중에 다시
  // 정체되면 새 알림으로 잡힙니다.
  const newKeys = new Set(await db.syncActiveIncidents(env.DB, incidents.map((i) => i.key)));
  if (newKeys.size === 0) return;

  const embeds = incidents.filter((i) => newKeys.has(i.key)).slice(0, MAX_EMBEDS).map(makeIncidentEmbed);
  for (const { guildId, channelId } of targets) {
    try {
      await sendChannelMessage(env.DISCORD_TOKEN, channelId, { embeds });
    } catch (err) {
      console.error(`교통정보 알림 실패 (guild ${guildId}, channel ${channelId})`, err);
    }
  }
}
