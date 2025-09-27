import type {
  ProgressEventPayload,
  RunRequestBody,
  FinalRunResponse,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type ProgressCallback = (event: ProgressEventPayload) => void;
type ErrorCallback = (error: unknown) => void;

const decoder = new TextDecoder("utf-8");

interface StreamHandle {
  abort: () => void;
}

export function getFileDownloadUrl(filePath: string): string {
  const normalized = filePath?.trim();
  if (!normalized) {
    throw new Error(
      "A non-empty file path is required to build the download URL."
    );
  }

  return `${API_BASE_URL}/files/download?path=${encodeURIComponent(
    normalized
  )}`;
}

function parseSSEChunk(chunk: string): ProgressEventPayload | null {
  const lines = chunk.split(/\n/).filter(Boolean);
  let eventType: string | null = null;
  let dataPayload = "";

  for (const line of lines) {
    if (line.startsWith(":")) {
      continue; // comment
    }
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataPayload += line.slice("data:".length).trim();
    }
  }

  if (!dataPayload) {
    return null;
  }

  if (eventType && eventType !== "progress") {
    return null;
  }

  try {
    return JSON.parse(dataPayload) as ProgressEventPayload;
  } catch (error) {
    console.error("Failed to parse SSE payload", error, chunk);
    return null;
  }
}

export async function streamRun(
  body: RunRequestBody,
  onProgress: ProgressCallback,
  onError?: ErrorCallback
): Promise<StreamHandle> {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/run/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        const text = await response.text();
        throw new Error(
          `Stream request failed with status ${response.status}: ${text}`
        );
      }

      const reader = response.body.getReader();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        let delimiterIndex = buffer.indexOf("\n\n");
        while (delimiterIndex !== -1) {
          const rawEvent = buffer.slice(0, delimiterIndex);
          buffer = buffer.slice(delimiterIndex + 2);
          const parsed = parseSSEChunk(rawEvent);
          if (parsed) {
            onProgress(parsed);
          }
          delimiterIndex = buffer.indexOf("\n\n");
        }
      }
    } catch (error) {
      if ((error as DOMException)?.name === "AbortError") {
        return;
      }
      console.error("Streaming error", error);
      onError?.(error);
    }
  })();

  return {
    abort: () => controller.abort(),
  };
}

export async function runFinal(
  body: RunRequestBody
): Promise<FinalRunResponse> {
  const response = await fetch(`${API_BASE_URL}/run/final`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Final run failed with status ${response.status}: ${text}`);
  }

  return (await response.json()) as FinalRunResponse;
}
