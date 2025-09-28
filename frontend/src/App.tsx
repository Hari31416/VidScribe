import { FormEvent } from "react";
import { ConfigurationPanel } from "./components/ConfigurationPanel";
import { MonitoringPanel } from "./components/MonitoringPanel";
import { DetailedResults } from "./components/DetailedResults";
import { useFormState } from "./hooks/useFormState";
import { useStreamingState } from "./hooks/useStreamingState";

export default function App() {
  // hooks for form and streaming state
  const {
    form,
    setForm,
    compactMode,
    setCompactMode,
    includeFields,
    setIncludeFields,
    maxItems,
    setMaxItems,
    maxChars,
    setMaxChars,
    refreshNotes,
    setRefreshNotes,
    advancedOpen,
    setAdvancedOpen,
    buildStreamConfig,
    makeRunBody,
  } = useFormState();

  const {
    latestEvent,
    events,
    snapshot,
    counters,
    error,
    isStreaming,
    isSubmittingFinal,
    streamMode,
    activeEvents,
    startStreaming,
    cancelStreaming,
    runFinalStage,
  } = useStreamingState();

  const handleSubmitStream = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = makeRunBody({ includeStreamConfig: true });
    startStreaming(body);
  };

  const handleCancel = () => cancelStreaming();

  const handleRunFinal = async () => {
    const body = makeRunBody({ includeStreamConfig: true });
    await runFinalStage(body);
  };

  return (
    <div className="max-w-[1400px] mx-auto px-4 py-8 space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">
          VidScribe Orchestration Dashboard
        </h1>
        <p className="text-slate-600">
          Drive the LangGraph pipeline via the FastAPI backend, monitor progress
          in real time, and inspect the generated notes.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:[grid-template-columns:1fr_1.8fr_1.2fr] gap-6">
        {/* Left: Configuration */}
        <ConfigurationPanel
          form={form}
          setForm={setForm}
          compactMode={compactMode}
          setCompactMode={setCompactMode}
          includeFields={includeFields}
          setIncludeFields={setIncludeFields}
          maxItems={maxItems}
          setMaxItems={setMaxItems}
          maxChars={maxChars}
          setMaxChars={setMaxChars}
          refreshNotes={refreshNotes}
          setRefreshNotes={setRefreshNotes}
          advancedOpen={advancedOpen}
          setAdvancedOpen={setAdvancedOpen}
          onSubmit={handleSubmitStream}
          onRunFinal={handleRunFinal}
          onCancel={handleCancel}
          isStreaming={isStreaming}
          isSubmittingFinal={isSubmittingFinal}
        />

        {/* Center: Monitoring & Key Output */}
        <MonitoringPanel
          latest={latestEvent}
          streamMode={streamMode}
          isStreaming={isStreaming}
          counters={counters}
          snapshot={snapshot}
          error={error}
        />

        {/* Right: Detailed Results & Logs */}
        <DetailedResults snapshot={snapshot} events={activeEvents} />
      </div>
    </div>
  );
}
