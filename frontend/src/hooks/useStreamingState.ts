import { useCallback, useMemo, useRef, useState } from "react";
import { runFinal, streamRun } from "../api/runGraph";
import { streamDownload } from "../api/download";
import type {
  Counters,
  ProgressEventPayload,
  RunRequestBody,
  StateSnapshot,
} from "../types";

const TERMINAL_PHASES = new Set(["done", "error", "cancelled"]);

type StreamHandle = { abort: () => void } | null;

export function useStreamingState() {
  const [latestEvent, setLatestEvent] = useState<ProgressEventPayload>();
  const [events, setEvents] = useState<ProgressEventPayload[]>([]);
  const [snapshot, setSnapshot] = useState<StateSnapshot>();
  const [counters, setCounters] = useState<Counters>();
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSubmittingFinal, setIsSubmittingFinal] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<{
    percent: number;
    message: string;
    status?: string;
  } | null>(null);
  const [downloadFilePath, setDownloadFilePath] = useState<string | null>(null);
  const [runId, setRunId] = useState(0);

  const streamHandleRef = useRef<StreamHandle>(null);
  const streamMode = latestEvent?.stream?.mode;

  const handleStreamProgress = useCallback((event: ProgressEventPayload) => {
    const stamped: ProgressEventPayload = {
      ...event,
      timestamp: event.timestamp ?? new Date().toISOString(),
    };
    setLatestEvent(stamped);
    setEvents((prev) => [...prev.slice(-98), stamped]);
    if (stamped.data) setSnapshot(stamped.data);
    if (stamped.counters) setCounters(stamped.counters);
    if (TERMINAL_PHASES.has(stamped.phase)) {
      setIsStreaming(false);
      streamHandleRef.current = null;
    }
  }, []);

  const handleStreamError = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : String(err));
    setIsStreaming(false);
    streamHandleRef.current = null;
  }, []);

  const startStreaming = useCallback(
    async (body: RunRequestBody) => {
      setError(null);
      if (streamHandleRef.current) {
        streamHandleRef.current.abort();
        streamHandleRef.current = null;
      }
      setEvents([]);
      setLatestEvent(undefined);
      setSnapshot(undefined);
      setCounters(undefined);
      setDownloadFilePath(null);
      setRunId((r) => r + 1);
      setIsStreaming(true);
      try {
        const handle = await streamRun(
          body,
          handleStreamProgress,
          handleStreamError
        );
        streamHandleRef.current = handle;
      } catch (err) {
        handleStreamError(err);
      }
    },
    [handleStreamError, handleStreamProgress]
  );

  const startStreamingAuto = useCallback(
    async (body: RunRequestBody & { video_path?: string }) => {
      setError(null);
      if (streamHandleRef.current) {
        streamHandleRef.current.abort();
        streamHandleRef.current = null;
      }
      setEvents([]);
      setLatestEvent(undefined);
      setSnapshot(undefined);
      setCounters(undefined);
      setDownloadProgress({
        percent: 0,
        message: "Preparing download…",
        status: "started",
      });
      setDownloadFilePath(null);
      setIsStreaming(true);
      try {
        // 1) Download the video via SSE and mirror progress in UI
        const dl = await streamDownload({ video_id: body.video_id }, (ui) => {
          setDownloadProgress({
            percent: ui.percent,
            message: ui.message,
            status: ui.status,
          });
        });
        const video_path = await dl.done;
        setDownloadFilePath(video_path);
        setDownloadProgress({
          percent: 100,
          message: "Download complete",
          status: "success",
        });
        // 2) Start the graph stream as usual; reset run progress (keep download card visible)
        setRunId((r) => r + 1);
        const handle = await streamRun(
          { ...body, video_path },
          handleStreamProgress,
          handleStreamError
        );
        streamHandleRef.current = handle;
      } catch (err) {
        handleStreamError(err);
      }
    },
    [handleStreamError, handleStreamProgress]
  );

  const cancelStreaming = useCallback(() => {
    // Abort the network stream
    streamHandleRef.current?.abort();
    streamHandleRef.current = null;
    // Reflect cancellation immediately in UI (like Gradio)
    const stamped: ProgressEventPayload = {
      phase: "cancelled",
      progress: 0,
      message: "Execution cancelled",
      timestamp: new Date().toISOString(),
      data: snapshot,
      counters,
    };
    setLatestEvent(stamped);
    setEvents((prev) => [...prev.slice(-98), stamped]);
    setIsStreaming(false);
  }, [snapshot, counters]);

  const runFinalStage = useCallback(async (body: RunRequestBody) => {
    setIsSubmittingFinal(true);
    setError(null);
    try {
      // If video_path is missing, download first quickly via non-streaming path
      let toSend = body;
      if (!body.video_path) {
        try {
          const { downloadOnce } = await import("../api/download");
          const path = await downloadOnce({ video_id: body.video_id });
          setDownloadFilePath(path);
          setDownloadProgress({
            percent: 100,
            message: "Download complete",
            status: "success",
          });
          toSend = { ...body, video_path: path };
        } catch (e) {
          // Fall back to original body if download fails
          console.error("Pre-download for final failed", e);
        }
      }
      const result = await runFinal(toSend);
      const stamped: ProgressEventPayload = {
        ...result,
        timestamp: result.timestamp ?? new Date().toISOString(),
      };
      setLatestEvent(stamped);
      setSnapshot(stamped.data);
      setCounters(stamped.counters);
      setEvents((prev) => [...prev.slice(-98), stamped]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingFinal(false);
    }
  }, []);

  const activeEvents = useMemo(
    () =>
      events.map((evt, index) => ({
        id: `${index}-${evt.phase}-${evt.progress}`,
        phase: evt.phase,
        progress: evt.progress,
        message: evt.message,
        timestamp: evt.timestamp,
      })),
    [events]
  );

  return {
    // state
    latestEvent,
    events,
    snapshot,
    counters,
    error,
    isStreaming,
    isSubmittingFinal,
    streamMode,
    activeEvents,
    downloadProgress,
    downloadFilePath,
    runId,
    // actions
    startStreaming,
    startStreamingAuto,
    cancelStreaming,
    runFinalStage,
  } as const;
}
