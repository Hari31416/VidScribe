import { useEffect, useState, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, endpoints } from "@/api";
import { Loader2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import html2pdf from 'html2pdf.js';

interface NotesViewerProps {
    projectId: string;
    artifactType: string;
    filename: string;
}

export function NotesViewer({ projectId, artifactType, filename }: NotesViewerProps) {
    const [content, setContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);
    const contentRef = useRef<HTMLElement>(null);

    useEffect(() => {
        const fetchNotes = async () => {
            if (!projectId || !artifactType || !filename) return;
            setLoading(true);
            setError(null);
            try {
                const res = await api.get(endpoints.downloads.file(projectId, artifactType, filename));
                setContent(res.data);
            } catch (err) {
                setError("Notes not found or could not be loaded.");
            } finally {
                setLoading(false);
            }
        };

        fetchNotes();
    }, [projectId, artifactType, filename]);

    const handleExportPdf = async () => {
        if (!contentRef.current) return;

        setExporting(true);
        try {
            // Extract base filename for PDF
            const baseFilename = filename.split('/').pop()?.replace(/\.[^/.]+$/, '') || 'notes';
            const pdfFilename = `${projectId}_${baseFilename}`;

            // Clone the content for PDF generation with light mode styles
            const clonedContent = contentRef.current.cloneNode(true) as HTMLElement;

            // Apply light mode styles for PDF (dark text on white background)
            clonedContent.style.backgroundColor = '#ffffff';
            clonedContent.style.color = '#1f2937';
            clonedContent.style.padding = '20px';

            // Force all text elements to have dark colors
            const allElements = clonedContent.querySelectorAll('*');
            allElements.forEach((el) => {
                const element = el as HTMLElement;
                element.style.color = '#1f2937';
                // Make headings slightly darker
                if (element.tagName.match(/^H[1-6]$/)) {
                    element.style.color = '#111827';
                    element.style.fontWeight = 'bold';
                }
                // Style code blocks
                if (element.tagName === 'CODE' || element.tagName === 'PRE') {
                    element.style.backgroundColor = '#f3f4f6';
                    element.style.color = '#1f2937';
                }
                // Style links
                if (element.tagName === 'A') {
                    element.style.color = '#2563eb';
                }
                // Style list markers
                if (element.tagName === 'LI') {
                    element.style.color = '#1f2937';
                }
            });

            // Create a temporary container for the cloned content
            const tempContainer = document.createElement('div');
            tempContainer.style.position = 'absolute';
            tempContainer.style.left = '-9999px';
            tempContainer.style.top = '0';
            tempContainer.style.width = '210mm'; // A4 width
            tempContainer.style.backgroundColor = '#ffffff';
            tempContainer.appendChild(clonedContent);
            document.body.appendChild(tempContainer);

            const options = {
                margin: [10, 10, 10, 10] as [number, number, number, number],
                filename: `${pdfFilename}.pdf`,
                image: { type: 'jpeg' as const, quality: 0.98 },
                html2canvas: {
                    scale: 2,
                    useCORS: true,
                    logging: false,
                    backgroundColor: '#ffffff'
                },
                jsPDF: {
                    unit: 'mm' as const,
                    format: 'a4' as const,
                    orientation: 'portrait' as const
                },
                pagebreak: { mode: ['avoid-all', 'css', 'legacy'] as const }
            };

            await html2pdf().set(options).from(clonedContent).save();

            // Clean up temporary container
            document.body.removeChild(tempContainer);
        } catch (err) {
            console.error('PDF export failed:', err);
            alert('Failed to export PDF. Please try again.');
        } finally {
            setExporting(false);
        }
    };

    if (loading) return <div className="flex justify-center p-4"><Loader2 className="animate-spin" /></div>;
    if (error) return <div className="text-muted-foreground italic p-4">{error}</div>;

    return (
        <div className="space-y-2">
            <div className="flex justify-end">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleExportPdf}
                    disabled={exporting || !content}
                    className="gap-2"
                >
                    {exporting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Download className="h-4 w-4" />
                    )}
                    {exporting ? 'Exporting...' : 'Export PDF'}
                </Button>
            </div>
            <ScrollArea className="h-[600px] w-full rounded-md border p-4 bg-card">
                <article ref={contentRef} className="prose dark:prose-invert max-w-none">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[rehypeKatex]}
                    >
                        {content || ""}
                    </ReactMarkdown>
                </article>
            </ScrollArea>
        </div>
    );
}
