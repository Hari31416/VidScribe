import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Play, RotateCcw, AlertTriangle, CheckCircle, Loader2, FileText, ChevronDown, ChevronRight } from "lucide-react";

import { api, endpoints } from "@/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { LogViewer } from "@/components/LogViewer";
import { NotesViewer } from "@/components/NotesViewer";
import { DeleteProjectDialog } from "@/components/DeleteProjectDialog";
import { StorageStatsCard } from "@/components/StorageStatsCard";
import { cn } from "@/utils";

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

    // Check project status
    const { data: projectData, isLoading, error } = useQuery({
        queryKey: ["project", videoId],
        queryFn: async () => {
            const res = await api.get(endpoints.uploads.check(videoId!));
            return res.data;
        },
        enabled: !!videoId,
        retry: false,
    });

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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    video_id: videoId,
                    video_path: projectData.video_files && projectData.video_files.length > 0 ? projectData.video_files[0] : null,
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

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split("\n");
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            // setLogs(prev => [...prev, JSON.stringify(data)]); // Too verbose to log all data

                            // Update progress
                            if (typeof data.progress === 'number') {
                                setProgress(Math.round(data.progress * 100));
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

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">{videoId}</h1>
                    <div className="flex items-center gap-2 mt-2">
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
                                                // Reset model to default when provider changes
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
                                                // Safely render value, detecting if it is an object (like usage stats)
                                                let displayValue: string | number = "";
                                                if (typeof value === "object" && value !== null) {
                                                    // If it's an object, try to render a sensible summary or stringify
                                                    // Example: {current: 10, total: 100} -> "10 / 100"
                                                    // Unknown object -> JSON.stringify
                                                    const obj = value as any;
                                                    if (obj.current !== undefined && obj.total !== undefined) {
                                                        displayValue = `${obj.current} / ${obj.total}`;
                                                    } else {
                                                        displayValue = JSON.stringify(value);
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
                            <CardTitle>Generated Artifacts</CardTitle>
                            <CardDescription>Download your processing results here.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Button variant="outline" className="justify-start" onClick={() => window.open(`${api.defaults.baseURL}${endpoints.downloads.file("transcripts/" + videoId + ".json", videoId + "_transcript.json")}`, "_blank")}>
                                    <FileText className="mr-2 h-4 w-4" /> Transcript (JSON)
                                </Button>
                                {projectData.outputs?.final_notes_md && (
                                    <Button variant="outline" className="justify-start" onClick={() => window.open(`${api.defaults.baseURL}${endpoints.downloads.file("notes/" + videoId + "/final_notes.md", videoId + "_final_notes.md")}`, "_blank")}>
                                        <FileText className="mr-2 h-4 w-4" /> Final Notes (Markdown)
                                    </Button>
                                )}
                                {projectData.outputs?.final_notes_pdf && (
                                    <Button variant="outline" className="justify-start" onClick={() => window.open(`${api.defaults.baseURL}${endpoints.downloads.file("notes/" + videoId + "/final_notes.pdf", videoId + "_final_notes.pdf")}`, "_blank")}>
                                        <FileText className="mr-2 h-4 w-4" /> Final Notes (PDF)
                                    </Button>
                                )}
                                {projectData.outputs?.summary_md && (
                                    <Button variant="outline" className="justify-start" onClick={() => window.open(`${api.defaults.baseURL}${endpoints.downloads.file("notes/" + videoId + "/summary.md", videoId + "_summary.md")}`, "_blank")}>
                                        <FileText className="mr-2 h-4 w-4" /> Summary (Markdown)
                                    </Button>
                                )}
                            </div>

                            <div className="mt-8">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-semibold">Preview</h3>
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
                                <NotesViewer path={previewMode === "final" ? `notes/${videoId}/final_notes.md` : `notes/${videoId}/summary.md`} />
                                {/* Optional: could show empty state if file doesn't exist, but NotesViewer handles 404s gracefully */}
                            </div>
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
