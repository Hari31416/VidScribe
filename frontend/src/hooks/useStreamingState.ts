import { useCallback, useMemo, useRef, useState } from "react";
import { runFinal, streamRun } from "../api/runGraph";
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

  const cancelStreaming = useCallback(() => {
    streamHandleRef.current?.abort();
    streamHandleRef.current = null;
    setIsStreaming(false);
  }, []);

  const runFinalStage = useCallback(async (body: RunRequestBody) => {
    setIsSubmittingFinal(true);
    setError(null);
    try {
      const result = await runFinal(body);
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
    // actions
    startStreaming,
    cancelStreaming,
    runFinalStage,
  } as const;
}
