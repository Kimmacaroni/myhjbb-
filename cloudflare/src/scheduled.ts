/**
 * 매일 정해진 시각(wrangler.toml의 cron)에 실행되는 식단 자동 전송.
 * GitHub Actions 워크플로가 하던 일을 대신합니다.
 *
 * ⚠️ Cloudflare Workers 무료 요금제는 호출 1회당 하위 요청 50개 제한이
 * 있습니다. 식단 채널을 설정한 서버가 많으면(대략 45개 이상) 이 한도에
 * 걸려 일부 서버는 그날 전송이 안 될 수 있습니다. 개인/소규모 커뮤니티
 * 용도라면 문제되지 않지만, 여러 서버에 배포할 계획이면 유료 요금제나
 * 배치 처리가 필요합니다.
 */
import * as db from "./db";
import { sendChannelMessage } from "./discord";
import { fetchMenu, makeMenuEmbed } from "./menu-source";
import type { Env } from "./types";

export async function sendDailyMenu(env: Env): Promise<void> {
  const targets = await db.allMenuChannels(env.DB);
  if (targets.length === 0) {
    console.log("식단을 보낼 채널이 설정된 서버가 없습니다.");
    return;
  }

  let embed;
  try {
    embed = makeMenuEmbed(await fetchMenu());
  } catch (err) {
    console.error("식단 크롤링 실패 — 오늘 전송을 건너뜁니다.", err);
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
