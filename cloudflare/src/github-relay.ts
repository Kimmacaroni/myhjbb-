/**
 * 진단 엔드포인트(/setup/debug-menu)의 결과를 GitHub 저장소 파일에 자동으로
 * 기록합니다. 이 프로젝트를 다루는 샌드박스는 외부 네트워크가 막혀 있어
 * 배포된 Worker를 직접 호출해 결과를 못 가져오므로(사용자가 URL을 직접
 * 열어서 응답을 복사해 붙여넣어야 했음), 대신 GitHub API로 읽을 수 있는
 * 파일에 결과를 남겨 둡니다 — 그러면 사람이 결과를 복사해서 붙여넣지
 * 않아도 됩니다.
 *
 * GITHUB_RELAY_TOKEN secret(이 저장소 Contents 읽기/쓰기 권한만 있는
 * fine-grained PAT)이 없으면 이 기능은 조용히 꺼집니다.
 */

const OWNER = "Kimmacaroni";
const REPO = "-";
const DEFAULT_BRANCH = "main";

/** btoa는 Latin1만 다루므로, UTF-8 바이트로 먼저 변환한 뒤 base64로 인코딩합니다. */
function toBase64Utf8(text: string): string {
  return btoa(unescape(encodeURIComponent(text)));
}

/**
 * @param filename cloudflare/debug/ 아래에 만들 파일 이름 (예: "traffic.json").
 * @param branch 기록할 브랜치. 생략하면 저장소 기본 브랜치(main)에 씁니다.
 * @param fetcher 테스트용 fetch 대체. 생략하면 전역 fetch를 씁니다 — Workers
 *   런타임 제약(Illegal invocation)을 피하려고 기본값을 bind로 감쌉니다.
 * @returns 사람이 읽을 결과 메시지(성공/실패 이유).
 */
export async function relayDebugToGithub(
  token: string,
  filename: string,
  content: string,
  branch: string = DEFAULT_BRANCH,
  fetcher: { fetch: typeof fetch } = { fetch: fetch.bind(globalThis) },
): Promise<string> {
  const path = `cloudflare/debug/${filename}`;
  const apiUrl = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${path}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "honorary-bot-worker",
  };

  // 이미 있는 파일을 덮어쓰려면 현재 sha를 같이 보내야 합니다(없으면 새 파일).
  let sha: string | undefined;
  const getRes = await fetcher.fetch(`${apiUrl}?ref=${branch}`, { headers });
  if (getRes.ok) {
    const data = await getRes.json<{ sha: string }>();
    sha = data.sha;
  } else if (getRes.status !== 404) {
    return `GitHub 조회 실패: HTTP ${getRes.status}`;
  }

  const putRes = await fetcher.fetch(apiUrl, {
    method: "PUT",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({
      message: `debug: ${filename} 갱신`,
      content: toBase64Utf8(content),
      branch,
      ...(sha ? { sha } : {}),
    }),
  });

  if (!putRes.ok) {
    const errText = await putRes.text();
    return `GitHub 기록 실패: HTTP ${putRes.status} ${errText.slice(0, 300)}`;
  }
  return `${path} (${branch} 브랜치)에 기록했습니다.`;
}
