import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Play, RotateCcw, AlertTriangle, CheckCircle, Loader2, FileText, ChevronDown, ChevronRight, History, Clock } from "lucide-react";

import { api, endpoints } from "@/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { LogViewer } from "@/components/LogViewer";
import { NotesViewer } from "@/components/NotesViewer";
import { DeleteProjectDialog } from "@/components/DeleteProjectDialog";
import { StorageStatsCard } from "@/components/StorageStatsCard";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/utils";
import { formatDistanceToNow } from "date-fns";

export function ProjectDetail() {
    const { videoId } = useParams<{ videoId: string }>();
    const navigate = useNavigate();
    const [logs, setLogs] = useState<string[]>([]);
    const [isRunning, setIsRunning] = useState(false);
    const [runStatus, setRunStatus] = useState<"idle" | "running" | "completed" | "error">("idle");
    const [progress, setProgress] = useState(0);
    const [progressMessage, setProgressMessage] = useState("");
    const [counters, setCounters] = useState<Record<string, number>>({});
    const [isLogsOpen, setIsLogsOpen] = useState(false);
    const [currentRunId, setCurrentRunId] = useState<string | null>(null);

    // Check project status
    const { data: projectData, isLoading, error, refetch: refetchProject } = useQuery({
        queryKey: ["project", videoId],
        queryFn: async () => {
            const res = await api.get(endpoints.uploads.check(videoId!));
            return res.data;
        },
        enabled: !!videoId && videoId !== "undefined",
        retry: false,
    });

    // Fetch runs
    const { data: runsData = [], refetch: refetchRuns } = useQuery({
        queryKey: ["runs", videoId],
        queryFn: async () => {
            if (!videoId) return [];
            try {
                const res = await api.get(endpoints.runs.list(videoId));
                return res.data;
            } catch (err) {
                console.warn("Failed to fetch runs:", err);
                return [];
            }
        },
        enabled: !!videoId && videoId !== "undefined",
    });

    // Set initial run ID when project or runs load - default to latest run
    useEffect(() => {
        if (currentRunId) return; // Already set

        // If we have runs, select the latest one (sorted by created_at descending)
        if (runsData && runsData.length > 0) {
            const sortedRuns = [...runsData].sort((a: any, b: any) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setCurrentRunId(sortedRuns[0].run_id);
        } else if (projectData?.current_run_id) {
        // Fallback to project's current_run_id
            setCurrentRunId(projectData.current_run_id);
        }
    }, [projectData, runsData, currentRunId]);

    const [config, setConfig] = useState({
        provider: "google",
        model: "gemini-2.0-flash",
        numChunks: 2,
        isCustomModel: false,
        userFeedback: ""
    });

    // Preview mode state
    const [previewMode, setPreviewMode] = useState<"final" | "summary">("final");

    const abortControllerRef = useRef<AbortController | null>(null);

    const handleStop = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setLogs(prev => [...prev, "[INFO] Pipeline stopped by user."]);
            setRunStatus("idle");
            setIsRunning(false);
        }
    };

    const handleRunChange = async (runId: string) => {
        setCurrentRunId(runId);
        // Optionally update current run on backend
        // await api.put(endpoints.runs.setCurrent(videoId!, runId));
        // refetchProject();
    };

    const handleRun = async () => {
        if (!videoId) return;
        setIsRunning(true);
        setRunStatus("running");
        setLogs(["Starting pipeline service...", "Initializing graph connection..."]);
        setProgress(0);
        setProgressMessage("Initializing...");
        setCounters({});
        setIsLogsOpen(false); // Close logs by default on run

        // Create new AbortController
        abortControllerRef.current = new AbortController();

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/run/stream`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${localStorage.getItem("token") || ""}`
                },
                body: JSON.stringify({
                    project_id: videoId,
                    num_chunks: config.numChunks,
                    provider: config.provider === "custom" ? "litellm" : config.provider,
                    model: config.model,
                    show_graph: false,
                    refresh_notes: true,
                    add_images: projectData.video_exists,
                    user_feedback: config.userFeedback || null,
                    stream_config: {
                        include_data: true,
                        include_fields: ["formatted_notes", "summary", "timestamps_output", "collected_notes_pdf_path", "summary_pdf_path"]
                    }
                }),
                signal: abortControllerRef.current.signal
            });

            if (!response.ok) throw new Error("Failed to start run");

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) throw new Error("No reader");

            let newRunId = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split("\n");
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            // Capture new run ID if emitted
                            if (data.run_id && !newRunId) {
                                newRunId = data.run_id;
                                setCurrentRunId(newRunId);
                            }

                            // Update progress
                            if (typeof data.progress === 'number') {
                                setProgress(data.progress);
                            }
                            if (data.message) {
                                setProgressMessage(data.message);
                                setLogs(prev => [...prev, `[INFO] ${data.message}`]);
                            }
                            if (data.counters) {
                                setCounters(data.counters);
                            }

                            if (data.phase === "done" || data.event === "complete" || data.status === "completed") {
                                setRunStatus("completed");
                                setIsRunning(false);
                                setProgress(100);
                                setProgressMessage("Pipeline Completed Successfully");
                                refetchProject();
                                refetchRuns();
                            }
                            if (data.phase === "error" || data.event === "error" || data.status === "failed") {
                                setRunStatus("error");
                                setIsRunning(false);
                                // Extract error message
                                const errorMsg = data.message || data.error || "Unknown error occurred";
                                setLogs(prev => [...prev, `[ERROR] ${errorMsg}`]);
                                setProgressMessage(`Error: ${errorMsg}`);
                                alert(`Pipeline Failed: ${errorMsg}`);
                            }
                        } catch (e) {
                            // ignore parse error
                        }
                    }
                }
            }

        } catch (err: any) {
            if (err.name === 'AbortError') {
                console.log('Fetch aborted');
            } else {
                setLogs(prev => [...prev, `[ERROR] ${err}`]);
                setRunStatus("error");
            }
            setIsRunning(false);
        } finally {
            abortControllerRef.current = null;
        }
    };

    if (isLoading) {
        return <div className="flex h-screen items-center justify-center"><Loader2 className="animate-spin w-8 h-8" /></div>;
    }

    if (error || !projectData) {
        return (
            <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
                <AlertTriangle className="w-12 h-12 text-destructive" />
                <h2 className="text-xl font-bold">Project Not Found</h2>
                <Button onClick={() => navigate("/")}>Go Back</Button>
            </div>
        )
    }



    // Note: Paths are now constructed directly in the download button onClick handlers using videoId and currentRunId

    const handleDownload = async (url: string, filename: string) => {
        try {
            const response = await api.get(url, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: response.headers['content-type'] });
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error("Download failed:", error);
            alert("Failed to download file. Please try again.");
        }
    };

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{projectData.name || videoId}</h1>
                    <div className="flex items-center gap-2 mt-2">
                        <span className="text-muted-foreground text-sm font-mono bg-muted/50 px-2 py-0.5 rounded">ID: {videoId}</span>
                        {projectData.video_exists && <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Video</span>}
                        {projectData.transcript_exists && <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Transcript</span>}
                    </div>
                </div>
                <div>
                    <DeleteProjectDialog videoId={videoId!} />
                </div>
            </div>

            <Tabs defaultValue="run" className="w-full">
                <TabsList>
                    <TabsTrigger value="run">Pipeline</TabsTrigger>
                    <TabsTrigger value="results">Results</TabsTrigger>
                    <TabsTrigger value="settings">Settings</TabsTrigger>
                </TabsList>

                <TabsContent value="run" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle>Run Generation Pipeline</CardTitle>
                                    <CardDescription>Generate structured notes from your video and transcript.</CardDescription>
                                </div>
                                {runStatus !== "idle" && (
                                    <div className={cn(
                                        "px-2 py-1 rounded text-xs font-medium uppercase",
                                        runStatus === "running" && "bg-blue-100 text-blue-800",
                                        runStatus === "completed" && "bg-green-100 text-green-800",
                                        runStatus === "error" && "bg-red-100 text-red-800",
                                    )}>
                                        {runStatus}
                                    </div>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-col space-y-4">
                                <div className="flex flex-wrap gap-4 items-end bg-muted/30 p-4 rounded-lg border">
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium">Provider</label>
                                        <select
                                            className="flex h-10 w-32 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:opacity-50"
                                            value={config.provider}
                                            onChange={(e) => {
                                                const p = e.target.value;
                                                let m = config.model;
                                                if (p === "google") m = "gemini-2.0-flash";
                                                if (p === "openrouter") m = "openai/gpt-oss-120b";
                                                if (p === "custom") m = "";
                                                setConfig({ ...config, provider: p, model: m, isCustomModel: p === "custom" });
                                            }}
                                            disabled={isRunning}
                                        >
                                            <option value="google">Google</option>
                                            <option value="openrouter">OpenRouter</option>
                                            <option value="custom">Custom</option>
                                        </select>
                                    </div>

                                    <div className="space-y-1 flex-1 min-w-[200px]">
                                        <label className="text-sm font-medium">Model</label>
                                        {config.isCustomModel ? (
                                            <input
                                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                                                placeholder="e.g. anthropic/claude-3-opus"
                                                value={config.model}
                                                onChange={(e) => setConfig({ ...config, model: e.target.value })}
                                                disabled={isRunning}
                                            />
                                        ) : (
                                            <select
                                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:opacity-50"
                                                value={config.model}
                                                onChange={(e) => {
                                                    const val = e.target.value;
                                                    if (val === "custom_override") {
                                                        setConfig({ ...config, isCustomModel: true, model: "" });
                                                    } else {
                                                        setConfig({ ...config, model: val });
                                                    }
                                                }}
                                                disabled={isRunning}
                                            >
                                                {config.provider === "google" && (
                                                    <>
                                                        <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                                                        <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                                        <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                                    </>
                                                )}
                                                {config.provider === "openrouter" && (
                                                    <>
                                                        <option value="openai/gpt-oss-120b">GPT-OSS 120b</option>
                                                    </>
                                                )}
                                                <option value="custom_override">Custom...</option>
                                            </select>
                                        )}
                                    </div>

                                    <div className="space-y-1">
                                        <label className="text-sm font-medium">Chunks</label>
                                        <input
                                            type="number"
                                            className="flex h-10 w-24 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                            value={config.numChunks}
                                            onChange={(e) => setConfig({ ...config, numChunks: parseInt(e.target.value) || 1 })}
                                            min={1}
                                            max={20}
                                            disabled={isRunning}
                                        />
                                    </div>

                                    <div className="flex gap-2">
                                        <Button
                                            className="gap-2"
                                            size="default"
                                            onClick={handleRun}
                                            disabled={isRunning}
                                        >
                                            {isRunning ? (
                                                <Loader2 className="animate-spin" />
                                            ) : (projectData.has_notes || runStatus === "completed") ? (
                                                <RotateCcw className="w-4 h-4" />
                                            ) : (
                                                <Play className="fill-current w-4 h-4" />
                                            )}
                                            {isRunning ? "Running..." : (projectData.has_notes || runStatus === "completed") ? "Restart Pipeline" : "Start Pipeline"}
                                        </Button>

                                        {isRunning && (
                                            <Button variant="destructive" onClick={handleStop} className="gap-2">
                                                Stop
                                            </Button>
                                        )}
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">User Feedback / Instructions (Optional)</label>
                                    <textarea
                                        className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                        placeholder="e.g., 'Focus on practical examples', 'Include code snippets', 'Make the summary concise', 'Use bullet points instead of paragraphs'..."
                                        value={config.userFeedback}
                                        onChange={(e) => setConfig({ ...config, userFeedback: e.target.value })}
                                        disabled={isRunning}
                                        rows={3}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        These instructions will be sent to the LLM when generating final notes and summary.
                                    </p>
                                </div>
                                <div className="space-y-4 pt-4 border-t">
                                    <div className="space-y-2">
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium">{progressMessage || "Ready to start"}</span>
                                            <span className="text-muted-foreground">{progress}%</span>
                                        </div>
                                        <Progress value={progress} className="h-2" />
                                    </div>

                                    {Object.keys(counters).length > 0 && (
                                        <div className="flex gap-4 flex-wrap text-sm">
                                            {Object.entries(counters).map(([key, value]) => {
                                                let displayValue: string | number = "";
                                                if (typeof value === "object" && value !== null) {
                                                    const obj = value as any;
                                                    // Handle {current, total} format
                                                    if (obj.current !== undefined && obj.total !== undefined) {
                                                        displayValue = `${obj.current} / ${obj.total}`;
                                                    }
                                                    // Handle {current_items, total_chunks} format
                                                    else if (obj.current_items !== undefined && obj.total_chunks !== undefined) {
                                                        displayValue = `${obj.chunks_completed || 0} / ${obj.total_chunks}`;
                                                    }
                                                    // Handle boolean status objects (finalization)
                                                    else if (Object.values(obj).every(v => typeof v === "boolean")) {
                                                        const completed = Object.values(obj).filter(v => v === true).length;
                                                        const total = Object.keys(obj).length;
                                                        displayValue = `${completed} / ${total}`;
                                                    }
                                                    // Handle count objects (notes_by_type)
                                                    else if (Object.values(obj).every(v => typeof v === "number")) {
                                                        const total = Object.values(obj).reduce((a, b) => (a as number) + (b as number), 0);
                                                        displayValue = `${total}`;
                                                    }
                                                    // Fallback: just show count of keys
                                                    else {
                                                        displayValue = `${Object.keys(obj).length} items`;
                                                    }
                                                } else {
                                                    displayValue = value;
                                                }

                                                return (
                                                    <div key={key} className="flex flex-col bg-background border px-3 py-1.5 rounded shadow-sm min-w-[100px]">
                                                        <span className="text-xs text-muted-foreground uppercase">{key}</span>
                                                        <span className="font-bold text-lg">{displayValue}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    <div className="border rounded-md">
                                        <div
                                            className="flex items-center justify-between p-3 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
                                            onClick={() => setIsLogsOpen(!isLogsOpen)}
                                        >
                                            <h3 className="text-sm font-medium flex items-center gap-2">
                                                {isLogsOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                                Raw Logs
                                            </h3>
                                            <span className="text-xs text-muted-foreground">{logs.length} events</span>
                                        </div>
                                        {isLogsOpen && (
                                            <div className="border-t p-2 bg-black/95">
                                                <LogViewer logs={logs} />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="results">
                    <Card>
                        <CardHeader>
                            <div className="flex justify-between items-start">
                                <div>
                                    <CardTitle>Generated Artifacts</CardTitle>
                                    <CardDescription>Download your processing results here.</CardDescription>
                                </div>
                                {runsData && runsData.length > 0 && (
                                    <div className="flex items-center gap-2">
                                        <History className="w-4 h-4 text-muted-foreground" />
                                        <Select value={currentRunId || ""} onValueChange={handleRunChange}>
                                            <SelectTrigger className="w-[200px]">
                                                <SelectValue placeholder="Select version" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {runsData.map((run: any) => (
                                                    <SelectItem key={run.run_id} value={run.run_id}>
                                                        <div className="flex flex-col">
                                                            <span className="font-medium">Version {run.run_id.substring(0, 6)}</span>
                                                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                                <Clock className="w-3 h-3" />
                                                                {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
                                                            </span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {projectData.has_transcript && (
                                    <Button variant="outline" className="justify-start" onClick={() => handleDownload(endpoints.downloads.file(videoId!, "transcripts", "transcript.json"), `${videoId}_transcript.json`)}>
                                        <FileText className="mr-2 h-4 w-4" /> Transcript (JSON)
                                    </Button>
                                )}

                                {/* Only show download buttons if current run has artifacts */}
                                {currentRunId && (() => {
                                    // Fallback: Always show buttons if run exists, as metadata might be missing on older runs
                                    // We can try to use flags if available, but default to showing for now to avoid hiding available files.
                                    // const selectedRun = (runsData || []).find((r: any) => r.run_id === currentRunId);
                                    // const files = selectedRun?.notes_files || {};

                                    return (
                                        <>
                                            <Button variant="outline" className="justify-start" onClick={() => handleDownload(endpoints.downloads.file(videoId!, "notes", `${currentRunId}/final_notes.md`), `${videoId}_final_notes.md`)}>
                                                <FileText className="mr-2 h-4 w-4" /> Final Notes (Markdown)
                                            </Button>
                                            <Button variant="outline" className="justify-start" onClick={() => handleDownload(endpoints.downloads.file(videoId!, "notes", `${currentRunId}/final_notes.pdf`), `${videoId}_final_notes.pdf`)}>
                                                <FileText className="mr-2 h-4 w-4" /> Final Notes (PDF)
                                            </Button>
                                            <Button variant="outline" className="justify-start" onClick={() => handleDownload(endpoints.downloads.file(videoId!, "notes", `${currentRunId}/summary.md`), `${videoId}_summary.md`)}>
                                                <FileText className="mr-2 h-4 w-4" /> Summary (Markdown)
                                            </Button>
                                        </>
                                    );
                                })()}
                            </div>

                            {currentRunId ? (
                                <div className="mt-8">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-lg font-semibold">Preview: {currentRunId.substring(0, 8)}</h3>
                                        <div className="flex gap-2">
                                            <Button
                                                variant={previewMode === "final" ? "default" : "outline"}
                                                size="sm"
                                                onClick={() => setPreviewMode("final")}
                                            >
                                                Final Notes
                                            </Button>
                                            <Button
                                                variant={previewMode === "summary" ? "default" : "outline"}
                                                size="sm"
                                                onClick={() => setPreviewMode("summary")}
                                            >
                                                Summary
                                            </Button>
                                        </div>
                                    </div>
                                    <NotesViewer
                                        projectId={videoId || ""}
                                        artifactType="notes"
                                        filename={previewMode === "final" ? `${currentRunId}/final_notes.md` : `${currentRunId}/summary.md`}
                                    />
                                </div>
                            ) : (
                                <div className="mt-8 text-center py-12 border rounded-lg bg-muted/20">
                                    <p className="text-muted-foreground">Run the pipeline to generate notes.</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="settings" className="space-y-6">
                    <StorageStatsCard videoId={videoId!} />

                    <Card>
                        <CardHeader>
                            <CardTitle>Danger Zone</CardTitle>
                            <CardDescription>Irreversible actions for this project.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <DeleteProjectDialog videoId={videoId!} />
                        </CardContent>
                    </Card>
                </TabsContent>

            </Tabs>
        </div>
    );
}
