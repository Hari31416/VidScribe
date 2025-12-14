import { useState } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Loader2, Download, CheckCircle, AlertCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { FileUpload } from "@/components/FileUpload";
import { api, endpoints } from "@/api";

interface YouTubeImportProps {
    onSuccess: (videoId: string) => void;
}

export function YouTubeImport({ onSuccess }: YouTubeImportProps) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [url, setUrl] = useState("");
    const [logs, setLogs] = useState<string[]>([]);
    const [downloadStatus, setDownloadStatus] = useState<"idle" | "downloading" | "completed" | "error">("idle");
    const [downloadedVideoId, setDownloadedVideoId] = useState<string | null>(null);

    // Step 2: Transcript Upload State
    const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);

    const handleDownload = async () => {
        if (!url) return;
        setDownloadStatus("downloading");
        setLogs(["Starting download..."]);

        try {
            // Using POST to /videos/download/stream as per backend docs
            const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/videos/download/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    video_id: url,
                    resolution: 720,
                    audio_only: false,
                    video_only: false // We need video for the project
                })
            });

            if (!response.ok) throw new Error("Failed to start download");

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) throw new Error("No reader");

            let finalVideoId = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split("\n");
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.status === "downloading") {
                                setLogs(prev => {
                                    const last = prev[prev.length - 1];
                                    if (last === "Downloading...") return prev;
                                    return [...prev, "Downloading..."];
                                });
                            } else if (data.status === "started") {
                                if (data.video_id) finalVideoId = data.video_id; // Usually URL or ID
                            } else if (data.status === "finished") {
                                setLogs(prev => [...prev, "Download finished."]);
                            } else if (data.status === "completed" || data.status === "success" || data.status === "skipped") {
                                setLogs(prev => [...prev, "Process completed."]);
                                if (data.video_id && !finalVideoId) finalVideoId = data.video_id;

                                // Clean ID if it's a URL
                                if (finalVideoId.includes("v=")) {
                                    finalVideoId = finalVideoId.split("v=")[1].split("&")[0];
                                } else if (finalVideoId.includes("youtube.com") || finalVideoId.includes("youtu.be")) {
                                    finalVideoId = "youtube_video";
                                }

                                setDownloadedVideoId(finalVideoId);
                                setDownloadStatus("completed");
                                onSuccess(finalVideoId);
                            } else if (data.status === "error") {
                                setLogs(prev => [...prev, `Error: ${data.error}`]);
                                setDownloadStatus("error");
                            }
                        } catch (e) { }
                    }
                }
            }
        } catch (err: any) {
            setLogs(prev => [...prev, `[ERROR] ${err.message}`]);
            setDownloadStatus("error");
        }
    };

    const transcriptMutation = useMutation({
        mutationFn: async () => {
            if (!transcriptFile || !downloadedVideoId) throw new Error("Missing file or ID");
            const formData = new FormData();
            formData.append("transcript", transcriptFile);
            formData.append("video_id", downloadedVideoId); // Link to downloaded video

            const res = await api.post(endpoints.uploads.transcriptOnly, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            return res.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["uploads"] });
            navigate("/");
        },
        onError: (err: any) => {
            setUploadError(err.response?.data?.detail || err.message || "Upload failed");
        }
    });

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Step 1: Download Video</CardTitle>
                    <CardDescription>Enter a YouTube URL to download the video to the server.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex gap-2">
                        <Input
                            placeholder="https://www.youtube.com/watch?v=..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={downloadStatus === "downloading" || downloadStatus === "completed"}
                        />
                        <Button onClick={handleDownload} disabled={!url || downloadStatus === "downloading" || downloadStatus === "completed"}>
                            {downloadStatus === "downloading" ? <Loader2 className="animate-spin" /> : <Download className="w-4 h-4" />}
                        </Button>
                    </div>
                    {/* Minimal Log View */}
                    <div className="bg-muted p-2 rounded text-xs font-mono h-24 overflow-y-auto">
                        {logs.map((l, i) => <div key={i}>{l}</div>)}
                    </div>
                </CardContent>
            </Card>

            {downloadStatus === "completed" && (
                <Card className="border-green-200 bg-green-50 dark:bg-green-950/20 dark:border-green-900">
                    <CardHeader>
                        <CardTitle className="text-green-800 dark:text-green-300 flex items-center gap-2">
                            <CheckCircle className="w-5 h-5" /> Video Ready
                        </CardTitle>
                        <CardDescription>
                            Video ID: <span className="font-mono font-bold">{downloadedVideoId}</span>. Now upload the transcript.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label>Transcript File</Label>
                            <FileUpload
                                accept=".json,.vtt,.srt"
                                label="Upload Transcript"
                                file={transcriptFile}
                                onChange={setTranscriptFile}
                                icon={FileText as any}
                            />
                            <p className="text-xs text-muted-foreground">The system does not auto-download YouTube captions mostly, so please provide the .json or .vtt file manually.</p>
                        </div>

                        {uploadError && (
                            <div className="flex items-center gap-2 p-4 bg-destructive/10 text-destructive rounded-md text-sm">
                                <AlertCircle className="w-4 h-4" />
                                {uploadError}
                            </div>
                        )}

                        <div className="flex justify-end gap-2">
                            <Button variant="ghost" onClick={() => navigate("/")}>Cancel</Button>
                            <Button onClick={() => transcriptMutation.mutate()} disabled={!transcriptFile || transcriptMutation.isPending}>
                                {transcriptMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Create Project
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
