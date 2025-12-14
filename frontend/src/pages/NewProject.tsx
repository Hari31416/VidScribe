import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FileVideo, FileText, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileUpload } from "@/components/FileUpload";
import { api, endpoints } from "@/api";
import { YouTubeImport } from "@/components/YouTubeImport";

export function NewProject() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [projectId, setProjectId] = useState("");
    const [videoFile, setVideoFile] = useState<File | null>(null);
    const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);

    const uploadMutation = useMutation({
        mutationFn: async () => {
            const formData = new FormData();
            if (projectId) formData.append("video_id", projectId);

            // Determine endpoint based on files present
            if (videoFile && transcriptFile) {
                formData.append("video", videoFile);
                formData.append("transcript", transcriptFile);
                const res = await api.post(endpoints.uploads.videoAndTranscript, formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                });
                return res.data;
            } else if (transcriptFile && !videoFile) {
                formData.append("transcript", transcriptFile);
                const res = await api.post(endpoints.uploads.transcriptOnly, formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                });
                return res.data;
            } else {
                throw new Error("Invalid combination. Need at least transcript.");
            }
        },
        onSuccess: () => {
            // Invalidate list to refresh dashboard
            queryClient.invalidateQueries({ queryKey: ["uploads"] });
            navigate("/");
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || err.message || "Upload failed");
        }
    });

    const handleSubmit = () => {
        if (!transcriptFile) {
            // setError("A transcript file is required.");
            // We replaced error state with nothing or alert? 
            // Since error var is removed, we just return or alert.
            // But we can't alert without UI. 
            // Let's just return for now as button is disabled anyway.
            return;
        }
        uploadMutation.mutate();
    };

    return (
        <div className="max-w-3xl mx-auto p-8 space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Create New Project</h2>
                <p className="text-muted-foreground">
                    Upload your video and transcript to start generating notes.
                </p>
            </div>

            <div className="flex justify-end gap-3" hidden>
                {/* Hidden original buttons, moving logic inside tabs */}
            </div>

            <Tabs defaultValue="upload" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="upload">Upload Files</TabsTrigger>
                    <TabsTrigger value="youtube">From YouTube</TabsTrigger>
                </TabsList>

                <TabsContent value="upload" className="space-y-6 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Project Details</CardTitle>
                            <CardDescription>Define a unique ID for your project.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="project-id">Project ID (Optional)</Label>
                                <Input
                                    id="project-id"
                                    placeholder="e.g. calculus_lecture_01"
                                    value={projectId}
                                    onChange={(e) => setProjectId(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">Leave blank to auto-generate.</p>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="grid md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <Label>Video File (Optional)</Label>
                            <FileUpload
                                accept="video/*"
                                label="Upload Video"
                                file={videoFile}
                                onChange={setVideoFile}
                                icon={FileVideo}
                            />
                            <p className="text-xs text-muted-foreground">Required for frame extraction and visual notes.</p>
                        </div>
                        <div className="space-y-2">
                            <Label>Transcript (Required)</Label>
                            <FileUpload
                                accept=".json,.vtt,.srt"
                                label="Upload Transcript"
                                file={transcriptFile}
                                onChange={setTranscriptFile}
                                icon={FileText}
                            />
                            <p className="text-xs text-muted-foreground">JSON (YouTube format), VTT, or SRT.</p>
                        </div>
                    </div>

                    {error && (
                        <div className="flex items-center gap-2 p-4 bg-destructive/10 text-destructive rounded-md text-sm">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}

                    <div className="flex justify-end gap-3">
                        <Button variant="ghost" onClick={() => navigate("/")}>Cancel</Button>
                        <Button onClick={handleSubmit} disabled={uploadMutation.isPending || !transcriptFile}>
                            {uploadMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Create Project
                        </Button>
                    </div>
                </TabsContent>

                <TabsContent value="youtube" className="mt-4">
                    <YouTubeImport
                        onSuccess={(vidId) => {
                            // If we have a video ID, we successfully downloaded video.
                            // Now we need a transcript.
                            // Auto-set project ID to the downloaded video ID if possible or keep prompting.
                            setProjectId(vidId);
                            // Switch back to upload tab but maybe pre-fill some state?
                            // Actually, simpler flow: Stay in YouTube tab, show "Step 2: Upload Transcript"
                        }}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
