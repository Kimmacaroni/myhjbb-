/**
 * Cloudflare Workers 진입점.
 *
 * fetch(): 디스코드가 슬래시 명령어를 칠 때마다 호출하는 HTTP 엔드포인트
 *          (Interactions Endpoint URL). 서명을 검증한 뒤 명령어 이름으로
 *          라우팅합니다.
 * scheduled(): wrangler.toml의 cron 설정대로 매일 실행되는 식단 자동 전송.
 */
import { verifySignature, rest } from "./discord";
import { sendDailyMenu } from "./scheduled";
import { COMMAND_DEFINITIONS } from "./command-definitions";
import type { Env, Interaction, InteractionResponse } from "./types";

import * as leveling from "./commands/leveling";
import * as titles from "./commands/titles";
import * as menu from "./commands/menu";
import * as help from "./commands/help";

const InteractionType = { PING: 1, APPLICATION_COMMAND: 2 } as const;

type Handler = (env: Env, interaction: Interaction) => Promise<InteractionResponse>;

const HANDLERS: Record<string, Handler> = {
  도움말: help.handleHelp,
  경험치: leveling.handleShowXp,
  랭킹: leveling.handleLeaderboard,
  경험치지급: leveling.handleGiveXp,
  경험치차감: leveling.handleTakeXp,
  경험치설정: leveling.handleSetXp,
  칭호추가: titles.handleAddTitle,
  칭호삭제: titles.handleRemoveTitle,
  칭호목록: titles.handleListTitles,
  칭호동기화: titles.handleResyncTitles,
  식단채널설정: menu.handleSetMenuChannel,
  식단채널해제: menu.handleUnsetMenuChannel,
  식단설정: menu.handleMenuSettings,
};

export function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
}

/**
 * 슬래시 명령어를 디스코드에 등록합니다. 로컬에서 `scripts/register-commands.mjs`
 * 를 돌릴 네트워크 접근이 없는 환경(예: 제한된 CI/새드박스)에서 배포된 Worker가
 * 대신 등록하도록 만든 엔드포인트입니다. Worker는 항상 디스코드 API에 나갈 수
 * 있으므로 브라우저의 CORS/CSP 제약도 받지 않습니다.
 *
 * `SETUP_TOKEN` secret을 설정한 뒤 브라우저로
 * `/setup/register-commands?token=그값` 을 열면 됩니다. 한 번 등록한 뒤에는
 * `SETUP_TOKEN` secret을 지워서 이 엔드포인트를 다시 잠가도 됩니다.
 */
async function handleRegisterCommands(request: Request, env: Env): Promise<Response> {
  const token = new URL(request.url).searchParams.get("token");
  if (!env.SETUP_TOKEN || token !== env.SETUP_TOKEN) {
    return new Response("권한이 없습니다.", { status: 403 });
  }

  const res = await rest(
    env.DISCORD_TOKEN,
    "PUT",
    `/applications/${env.DISCORD_APPLICATION_ID}/commands`,
    COMMAND_DEFINITIONS,
  );
  const registered = await res.json<{ name: string }[]>();
  return json({
    message: `${registered.length}개 명령어 등록 완료 (전역 등록 — 반영까지 최대 1시간)`,
    commands: registered.map((c) => c.name),
  });
}

/** 요청을 받아 처리하는 본체. fetch()에서 분리해 둔 이유는 Node에서 직접 테스트하기 위해서입니다. */
export async function handleRequest(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/setup/register-commands") {
    return handleRegisterCommands(request, env);
  }

  if (request.method !== "POST") {
    return new Response("이 엔드포인트는 디스코드 Interactions 전용입니다.", { status: 405 });
  }

  const { valid, body } = await verifySignature(request, env.DISCORD_PUBLIC_KEY);
  if (!valid) {
    return new Response("서명이 유효하지 않습니다.", { status: 401 });
  }

  const interaction: Interaction = JSON.parse(body);

  if (interaction.type === InteractionType.PING) {
    return json({ type: 1 }); // PONG
  }

  if (interaction.type === InteractionType.APPLICATION_COMMAND) {
    const name = interaction.data?.name ?? "";

    // /식단 은 크롤링에 3초 넘게 걸릴 수 있어 별도 경로로 처리합니다:
    // 먼저 "생각 중" 응답을 보내고, 실제 작업은 백그라운드(ctx.waitUntil)에서
    // 끝낸 뒤 결과로 편집합니다.
    if (name === "식단") {
      ctx.waitUntil(menu.performMenuNow(env, interaction));
      return json(menu.handleMenuNowDefer());
    }

    const handler = HANDLERS[name];
    if (!handler) {
      return json({ type: 4, data: { content: `알 수 없는 명령어입니다: /${name}` } });
    }

    try {
      const response = await handler(env, interaction);
      return json(response);
    } catch (err) {
      console.error(`/${name} 처리 중 오류`, err);
      return json({
        type: 4,
        data: { content: "명령어를 처리하는 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요." },
      });
    }
  }

  return new Response("지원하지 않는 인터랙션 타입입니다.", { status: 400 });
}

export default {
  fetch: handleRequest,
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(sendDailyMenu(env));
  },
};
