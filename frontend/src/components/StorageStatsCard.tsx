import { useQuery } from "@tanstack/react-query";
import { api, endpoints } from "@/api";
import { Loader2, HardDrive, Database, FileText, Image as ImageIcon, Video } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface StorageStatsCardProps {
    videoId: string;
}

interface StatsData {
    video_size_mb: number;
    frames_size_mb: number;
    transcript_size_mb: number;
    notes_size_mb: number;
    total_size_mb: number;
    breakdown: Record<string, string>;
}

export function StorageStatsCard({ videoId }: StorageStatsCardProps) {
    const { data, isLoading, error } = useQuery<StatsData>({
        queryKey: ["storage-stats", videoId],
        queryFn: async () => {
            const res = await api.get(endpoints.uploads.getStorageStats(videoId));
            return res.data;
        },
        refetchInterval: 5000,
    });

    if (isLoading) return <Card className="h-[200px] flex items-center justify-center"><Loader2 className="animate-spin" /></Card>;
    if (error || !data) return null;

    // Ensure breakdown exists with fallback
    const breakdown = data.breakdown || {};

    const getPercent = (val: number) => {
        if (data.total_size_mb === 0) return 0;
        return Math.min(100, Math.max(0, (val / data.total_size_mb) * 100));
    };

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                    <HardDrive className="w-5 h-5 text-muted-foreground" />
                    Storage Usage
                </CardTitle>
                <CardDescription>
                    Total Project Size: <span className="font-bold text-foreground">{breakdown["Total"] || `${data.total_size_mb} MB`}</span>
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Visual Bar */}
                <div className="h-4 w-full bg-muted rounded-full overflow-hidden flex">
                    {data.video_size_mb > 0 && <div className="h-full bg-blue-500" style={{ width: `${getPercent(data.video_size_mb)}%` }} title="Video" />}
                    {data.frames_size_mb > 0 && <div className="h-full bg-purple-500" style={{ width: `${getPercent(data.frames_size_mb)}%` }} title="Frames" />}
                    {data.notes_size_mb > 0 && <div className="h-full bg-green-500" style={{ width: `${getPercent(data.notes_size_mb)}%` }} title="Notes" />}
                    {data.transcript_size_mb > 0 && <div className="h-full bg-yellow-500" style={{ width: `${getPercent(data.transcript_size_mb)}%` }} title="Transcript" />}
                </div>

                {/* Legend */}
                <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex items-center gap-2">
                        <Video className="w-4 h-4 text-blue-500" />
                        <span className="text-muted-foreground">Video:</span>
                        <span className="font-mono ml-auto">{breakdown["Video"] || "0 MB"}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <ImageIcon className="w-4 h-4 text-purple-500" />
                        <span className="text-muted-foreground">Frames:</span>
                        <span className="font-mono ml-auto">{breakdown["Frames"] || "0 MB"}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-green-500" />
                        <span className="text-muted-foreground">Notes:</span>
                        <span className="font-mono ml-auto">{breakdown["Notes"] || "0 MB"}</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-yellow-500" />
                        <span className="text-muted-foreground">Transcript:</span>
                        <span className="font-mono ml-auto">{breakdown["Transcript"] || "0 MB"}</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
