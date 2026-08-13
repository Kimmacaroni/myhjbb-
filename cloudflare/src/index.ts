/**
 * Cloudflare Workers 진입점.
 *
 * fetch(): 디스코드가 슬래시 명령어를 칠 때마다 호출하는 HTTP 엔드포인트
 *          (Interactions Endpoint URL). 서명을 검증한 뒤 명령어 이름으로
 *          라우팅합니다.
 * scheduled(): wrangler.toml의 cron 설정대로 실행되는 자동 전송 —
 *          매일 식단표 전송과 30분 간격 교통정보 확인, 두 가지 스케줄을
 *          event.cron으로 구분합니다.
 */
import { verifySignature, rest } from "./discord";
import { sendDailyMenu, sendTrafficAlerts } from "./scheduled";
import { COMMAND_DEFINITIONS } from "./command-definitions";
import { DAEWON_API_URL } from "./menu-source";
import { HIGHWAY_API_URL } from "./traffic-source";
import type { Env, Interaction, InteractionResponse } from "./types";

import * as leveling from "./commands/leveling";
import * as titles from "./commands/titles";
import * as menu from "./commands/menu";
import * as traffic from "./commands/traffic";
import * as help from "./commands/help";

const InteractionType = { PING: 1, APPLICATION_COMMAND: 2 } as const;

/** wrangler.toml [triggers].crons 의 30분 간격 교통정보 스케줄과 같아야 합니다. */
const TRAFFIC_CRON = "*/30 * * * *";

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
  교통정보채널설정: traffic.handleSetTrafficChannel,
  교통정보채널해제: traffic.handleUnsetTrafficChannel,
  교통정보설정: traffic.handleTrafficSettings,
};

/** 3초 안에 못 끝낼 수 있어 defer 후 백그라운드로 처리하는 명령어들. */
const DEFERRED_HANDLERS: Record<string, (env: Env, interaction: Interaction) => Promise<void>> = {
  식단: menu.performMenuNow,
  교통정보: traffic.performTrafficNow,
};

export function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
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

/**
 * 한국도로공사 교통정보 API를 서버(env.HIGHWAY_API_KEY) 쪽 키로 대신
 * 호출해 원본 응답을 그대로 보여줍니다. `handleDebugMenu`의 `url`
 * 파라미터로도 같은 걸 확인할 수 있지만, 그러면 발급받은 키를 URL에 직접
 * 붙여넣어야 해서 주소창/로그에 노출됩니다 — 이 경로는 키를 노출하지 않고
 * 확인할 수 있게 만든 것입니다 (`?target=traffic`).
 */
async function handleDebugTraffic(env: Env): Promise<Response> {
  if (!env.HIGHWAY_API_KEY) {
    return new Response("HIGHWAY_API_KEY secret이 설정되지 않았습니다.", { status: 400 });
  }

  const url = new URL(HIGHWAY_API_URL);
  url.searchParams.set("key", env.HIGHWAY_API_KEY);
  url.searchParams.set("type", "json");

  const res = await fetch(url.toString(), { headers: { "User-Agent": "Mozilla/5.0" } });
  const body = await res.text();
  return new Response(`HTTP ${res.status} ${res.statusText}\n\n${body}`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

/**
 * 임의의 주소를 Worker가 대신 가져와 응답을 그대로 보여주는 진단용
 * 엔드포인트입니다. 개발 환경은 여러 외부 사이트로 나가는 네트워크가 막혀
 * 있어 직접 확인할 수 없으므로, 실제 봇과 같은 네트워크 경로로 대신
 * 가져옵니다. `url` 파라미터를 생략하면 식단 API 주소(DAEWON_API_URL)를
 * fetchMenu()와 똑같은 방식(가능하면 Service Binding)으로 POST 조회합니다.
 * `target=traffic` 이면 대신 교통정보 API를 서버 쪽 키로 조회합니다
 * (`handleDebugTraffic` 참고). 다 쓰신 뒤에는 SETUP_TOKEN secret을 지워서
 * 잠가 두셔도 됩니다.
 */
async function handleDebugMenu(request: Request, env: Env): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const token = params.get("token");
  if (!env.SETUP_TOKEN || token !== env.SETUP_TOKEN) {
    return new Response("권한이 없습니다.", { status: 403 });
  }

  if (params.get("target") === "traffic") {
    return handleDebugTraffic(env);
  }

  const target = params.get("url") || DAEWON_API_URL;
  let targetUrl: URL;
  try {
    targetUrl = new URL(target);
  } catch {
    return new Response("url 파라미터가 올바른 주소가 아닙니다.", { status: 400 });
  }
  if (targetUrl.protocol !== "https:") {
    return new Response("https 주소만 확인할 수 있습니다.", { status: 400 });
  }

  const isDaewonApi = target === DAEWON_API_URL;
  // Workers 런타임에서는 { fetch } 처럼 객체에 담아 fetcher.fetch(...)로
  // 부르면 "Illegal invocation" 오류가 납니다(전역 fetch는 자기 자신이
  // 아닌 다른 객체를 통해 호출되면 안 되는 내부 제약이 있음) — bind로
  // 감싸야 객체 메서드 형태로 호출해도 안전합니다.
  const fetcher = isDaewonApi && env.DAEWON_API ? env.DAEWON_API : { fetch: fetch.bind(globalThis) };
  const bindingNote = isDaewonApi
    ? `[Service Binding: ${env.DAEWON_API ? "사용함" : "설정 안 됨 — 계정 내 Worker 간 요청은 fetch()로 안 되어 아래도 404가 뜰 수 있습니다"}]\n\n`
    : "";
  const res = await fetcher.fetch(
    targetUrl.toString(),
    isDaewonApi
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "foodmenu" }) }
      : { headers: { "User-Agent": "Mozilla/5.0" } },
  );
  const body = await res.text();
  return new Response(`${bindingNote}HTTP ${res.status} ${res.statusText}\n\n${body}`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

/** 요청을 받아 처리하는 본체. fetch()에서 분리해 둔 이유는 Node에서 직접 테스트하기 위해서입니다. */
export async function handleRequest(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/setup/register-commands") {
    return handleRegisterCommands(request, env);
  }
  if (request.method === "GET" && url.pathname === "/setup/debug-menu") {
    return handleDebugMenu(request, env);
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

    // /식단, /교통정보 처럼 API 조회에 3초 넘게 걸릴 수 있는 명령어는 별도
    // 경로로 처리합니다: 먼저 "생각 중" 응답을 보내고, 실제 작업은
    // 백그라운드(ctx.waitUntil)에서 끝낸 뒤 결과로 편집합니다.
    const deferredHandler = DEFERRED_HANDLERS[name];
    if (deferredHandler) {
      ctx.waitUntil(deferredHandler(env, interaction));
      return json({ type: 5 });
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
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    if (event.cron === TRAFFIC_CRON) {
      ctx.waitUntil(sendTrafficAlerts(env));
    } else {
      ctx.waitUntil(sendDailyMenu(env));
    }
  },
};
