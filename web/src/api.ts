import type { TranscriptDetail, TranscriptSummary } from "./types";

export async function listTranscripts(): Promise<TranscriptSummary[]> {
  const res = await fetch("/transcripts");
  if (!res.ok) throw new Error(`GET /transcripts failed: ${res.status}`);
  const json = await res.json();
  return json.transcripts;
}

export async function getTranscript(
  transcriptId: string,
): Promise<TranscriptDetail> {
  const res = await fetch(`/transcripts/${transcriptId}`);
  if (!res.ok)
    throw new Error(`GET /transcripts/${transcriptId} failed: ${res.status}`);
  return await res.json();
}

/**
 * Stream the orchestrator response as SSE-style `data: ...` lines.
 * Yields each text chunk as it arrives. The agent emits both literal text
 * deltas (JSON-encoded strings) and structural markers like `[tool] name`.
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
        // The agent yields strings — JSON-decode them so escapes resolve.
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
