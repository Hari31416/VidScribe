import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Plus, Download, CheckCircle2, Clock } from "lucide-react";
import { Link } from "react-router-dom";

import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/api";
import { Loader2, FileVideo } from "lucide-react";

export function Dashboard() {
    const { data: projects, isLoading } = useQuery({
        queryKey: ["uploads"],
        queryFn: async () => {
            const res = await api.get(endpoints.uploads.list);
            return res.data.projects as {
                project_id: string,
                has_notes: boolean,
                name: string,
                created_at: string,
                has_video: boolean,
                has_transcript: boolean,
                current_run_id?: string,
                notes_files?: Record<string, boolean>,
                status?: string
            }[];
        }
    });

    const handleDownloadPdf = async (e: React.MouseEvent, projectId: string, runId: string) => {
        e.preventDefault(); // Prevent card click navigation
        e.stopPropagation();

        try {
            const filename = `${runId}/final_notes.pdf`;
            const response = await api.get(endpoints.downloads.file(projectId, "notes", filename), {
                responseType: 'blob',
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${projectId}_final_notes.pdf`);
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Download failed:", error);
        }
    };

    return (
        <div className="p-8 space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold p-1">Projects</h2>
                    <p className="text-muted-foreground">Manage your video transcription projects.</p>
                </div>
                <Link to="/new">
                    <Button className="gap-2">
                        <Plus className="w-4 h-4" /> New Project
                    </Button>
                </Link>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card className="hover:bg-muted/50 transition-colors cursor-pointer border-dashed border-2 flex flex-col items-center justify-center p-6 h-[220px]">
                    <Link to="/new" className="flex flex-col items-center text-muted-foreground hover:text-foreground">
                        <Plus className="w-8 h-8 mb-2" />
                        <span>Create New Project</span>
                    </Link>
                </Card>

                {isLoading ? (
                    <div className="col-span-1 flex justify-center p-8"><Loader2 className="animate-spin" /></div>
                ) : (
                        projects?.map(project => {
                            const hasRun = (project.status === "completed") || (project.has_notes && !!project.current_run_id);
                            // Relax check: If run is completed, we assume PDF exists or user should try to download it (legacy support)
                            const hasPdf = hasRun;

                            return (
                                <Link key={project.project_id} to={`/project/${project.project_id}`}>
                                    <Card className="hover:border-primary transition-colors cursor-pointer h-[220px] flex flex-col justify-between relative group">
                                        <div className="p-6 pb-2">
                                            <div className="flex items-start justify-between">
                                                <div className="p-2 bg-primary/10 rounded-md">
                                                    <FileVideo className="w-6 h-6 text-primary" />
                                                </div>
                                                <div className="flex flex-col items-end gap-1.5">
                                                    {/* Run Status Indicator */}
                                                    <div className={`text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1 font-medium ${hasRun
                                                        ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                                        : "bg-amber-100 text-amber-800 border border-amber-200"
                                                        }`}>
                                                        {hasRun ? (
                                                            <>
                                                                <CheckCircle2 className="w-3 h-3" />
                                                                <span>Completed</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <Clock className="w-3 h-3" />
                                                                <span>Not Run</span>
                                                            </>
                                                        )}
                                                    </div>

                                                    <div className="flex gap-1">
                                                        {project.has_video && (
                                                            <div className="bg-blue-100 text-blue-800 text-[10px] px-1.5 py-0.5 rounded-full flex items-center" title="Has Video">
                                                                VID
                                                            </div>
                                                        )}
                                                        {project.has_transcript && (
                                                            <div className="bg-green-100 text-green-800 text-[10px] px-1.5 py-0.5 rounded-full flex items-center" title="Has Transcript">
                                                                TS
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="mt-4">
                                                <h3 className="font-semibold text-lg truncate" title={project.name || project.project_id}>{project.name || project.project_id}</h3>
                                                <div className="flex flex-col gap-1 mt-1">
                                                    <p className="text-xs text-muted-foreground truncate" title={project.project_id}>
                                                        ID: {project.project_id}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                        <span className="inline-block w-2 h-2 rounded-full bg-slate-300" />
                                                        {project.created_at ? new Date(project.created_at).toLocaleDateString() : "Unknown date"}
                                                    </p>
                                                </div>
                                            </div>
                                    </div>

                                        {/* Action Bar */}
                                        {hasPdf && project.current_run_id && (
                                            <div className="px-6 pb-4 pt-2 mt-auto border-t border-transparent group-hover:border-border/40 transition-colors">
                                                <Button
                                                    variant="secondary"
                                                    size="sm"
                                                    className="w-full h-8 text-xs gap-2 bg-secondary/50 hover:bg-secondary"
                                                    onClick={(e) => project.current_run_id && handleDownloadPdf(e, project.project_id, project.current_run_id)}
                                                >
                                                    <Download className="w-3 h-3" />
                                                    Download PDF Notes
                                                </Button>
                                            </div>
                                        )}
                                    </Card>
                                </Link>
                            )
                        })
                )}
            </div>
        </div>
    );
}
