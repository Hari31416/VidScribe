import { useEffect, useRef } from "react";


interface LogViewerProps {
    logs: string[];
    className?: string;
}

export function LogViewer({ logs, className }: LogViewerProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    return (
        <div className={`bg-slate-950 text-slate-50 font-mono text-xs p-4 rounded-md overflow-y-auto h-[400px] ${className}`}>
            {logs.length === 0 ? (
                <span className="text-slate-500 italic">Waiting for logs...</span>
            ) : (
                logs.map((log, i) => (
                    <div key={i} className="whitespace-pre-wrap break-all border-b border-slate-900/50 py-0.5">
                        {log}
                    </div>
                ))
            )}
            <div ref={scrollRef} />
        </div>
    );
}
