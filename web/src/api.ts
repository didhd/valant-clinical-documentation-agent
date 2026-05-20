import type { TranscriptDetail, TranscriptSummary } from "./types";

async function fetchWithFallback(
  primary: string,
  fallback: string,
): Promise<Response> {
  try {
    const res = await fetch(primary);
    if (res.ok) {
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("json")) return res;
    }
  } catch {
    // backend unreachable
  }
  const res = await fetch(fallback);
  if (!res.ok) throw new Error(`Fetch failed: ${fallback} (${res.status})`);
  return res;
}

export async function listTranscripts(): Promise<TranscriptSummary[]> {
  const res = await fetchWithFallback("/transcripts", "/api/transcripts.json");
  const json = await res.json();
  return json.transcripts;
}

export async function getTranscript(
  transcriptId: string,
): Promise<TranscriptDetail> {
  const res = await fetchWithFallback(
    `/transcripts/${transcriptId}`,
    `/api/transcripts-${transcriptId}.json`,
  );
  return await res.json();
}

export function isBackendAvailable(): Promise<boolean> {
  return fetch("/transcripts")
    .then((r) => r.ok && (r.headers.get("content-type") || "").includes("json"))
    .catch(() => false);
}

/**
 * Stream the orchestrator response as SSE-style `data: ...` lines.
 * Yields each text chunk as it arrives.
 */
export async function* streamInvocation(
  prompt: string,
  signal?: AbortSignal,
): AsyncGenerator<string, void, void> {
  const res = await fetch("/invocations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`POST /invocations failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let nlIdx;
    while ((nlIdx = buffer.indexOf("\n")) !== -1) {
      const line = buffer.slice(0, nlIdx).trim();
      buffer = buffer.slice(nlIdx + 1);
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      try {
        const parsed = JSON.parse(raw);
        if (typeof parsed === "string") {
          yield parsed;
        } else {
          yield JSON.stringify(parsed);
        }
      } catch {
        yield raw;
      }
    }
  }
}
