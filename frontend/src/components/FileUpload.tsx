import { useRef, useState } from "react";
import { Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/utils";

interface FileUploadProps {
    accept: string;
    label: string;
    onChange: (file: File | null) => void;
    file: File | null;
    icon?: React.ElementType;
}

export function FileUpload({ accept, label, onChange, file, icon: Icon = Upload }: FileUploadProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [isDragOver, setIsDragOver] = useState(false);

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) onChange(droppedFile);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(true);
    };

    const handleDragLeave = () => setIsDragOver(false);

    return (
        <Card
            className={cn(
                "border-2 border-dashed transition-colors",
                isDragOver ? "border-primary bg-primary/5" : "border-muted",
                file ? "border-solid border-primary/50" : ""
            )}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
        >
            <CardContent className="flex flex-col items-center justify-center py-8 space-y-4 text-center">
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    accept={accept}
                    onChange={(e) => onChange(e.target.files?.[0] || null)}
                />

                {file ? (
                    <div className="flex flex-col items-center gap-2">
                        <div className="p-4 bg-primary/10 rounded-full">
                            <Icon className="w-8 h-8 text-primary" />
                        </div>
                        <div className="space-y-1">
                            <p className="font-medium text-sm max-w-xs truncate" title={file.name}>
                                {file.name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                {(file.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="mt-2 text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={(e) => {
                                e.stopPropagation();
                                onChange(null);
                                if (inputRef.current) inputRef.current.value = "";
                            }}
                        >
                            <X className="w-3 h-3 mr-2" /> Remove
                        </Button>
                    </div>
                ) : (
                    <>
                        <div className="p-4 bg-muted rounded-full">
                            <Icon className="w-8 h-8 text-muted-foreground" />
                        </div>
                        <div className="space-y-1">
                            <p className="text-sm font-medium">{label}</p>
                            <p className="text-xs text-muted-foreground">
                                Drag & drop or click to browse
                            </p>
                        </div>
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => inputRef.current?.click()}
                        >
                            Select File
                        </Button>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
