import { useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, endpoints } from "@/api";
import { Loader2 } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface NotesViewerProps {
    path: string;
}

export function NotesViewer({ path }: NotesViewerProps) {
    const [content, setContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchNotes = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await api.get(endpoints.downloads.file(path));
                setContent(res.data);
            } catch (err) {
                setError("Notes not found or could not be loaded.");
            } finally {
                setLoading(false);
            }
        };

        if (path) fetchNotes();
    }, [path]);

    if (loading) return <div className="flex justify-center p-4"><Loader2 className="animate-spin" /></div>;
    if (error) return <div className="text-muted-foreground italic p-4">{error}</div>;

    return (
        <ScrollArea className="h-[600px] w-full rounded-md border p-4 bg-card">
            <article className="prose dark:prose-invert max-w-none">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                >
                    {content || ""}
                </ReactMarkdown>
            </article>
        </ScrollArea>
    );
}
