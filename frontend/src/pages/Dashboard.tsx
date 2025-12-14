import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/api";
import { Loader2, FileVideo } from "lucide-react";

export function Dashboard() {
    const { data, isLoading } = useQuery({
        queryKey: ["uploads"],
        queryFn: async () => {
            const res = await api.get(endpoints.uploads.list);
            return res.data.uploaded_video_ids as string[];
        }
    });

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
                <Card className="hover:bg-muted/50 transition-colors cursor-pointer border-dashed border-2 flex flex-col items-center justify-center p-6 h-[200px]">
                    <Link to="/new" className="flex flex-col items-center text-muted-foreground hover:text-foreground">
                        <Plus className="w-8 h-8 mb-2" />
                        <span>Create New Project</span>
                    </Link>
                </Card>

                {isLoading ? (
                    <div className="col-span-1 flex justify-center p-8"><Loader2 className="animate-spin" /></div>
                ) : (
                    data?.map(id => (
                        <Link key={id} to={`/project/${id}`}>
                            <Card className="hover:border-primary transition-colors cursor-pointer h-[200px] flex flex-col justify-between">
                                <div className="p-6">
                                    <div className="flex items-start justify-between">
                                        <div className="p-2 bg-primary/10 rounded-md">
                                            <FileVideo className="w-6 h-6 text-primary" />
                                        </div>
                                    </div>
                                    <div className="mt-4">
                                        <h3 className="font-semibold text-lg truncate" title={id}>{id}</h3>
                                        <p className="text-xs text-muted-foreground">Ready to process</p>
                                    </div>
                                </div>
                            </Card>
                        </Link>
                    ))
                )}
            </div>
        </div>
    );
}
