import { useState, useRef, ChangeEvent } from "react";
import { uploadVideoAndTranscript } from "../api/upload";

interface Props {
  onUploadSuccess: (videoId: string, videoPath: string) => void;
  disabled?: boolean;
}

export function UploadPanel({ onUploadSuccess, disabled = false }: Props) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [customVideoId, setCustomVideoId] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [expandUpload, setExpandUpload] = useState(false);

  const videoInputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  const handleVideoChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
      setError("");
    }
  };

  const handleTranscriptChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate it's a JSON, VTT, or SRT file
      const validExtensions = [".json", ".vtt", ".srt"];
      const hasValidExtension = validExtensions.some((ext) =>
        file.name.toLowerCase().endsWith(ext)
      );

      if (!hasValidExtension) {
        setError("Transcript must be a JSON, VTT, or SRT file");
        return;
      }
      setTranscriptFile(file);
      setError("");
    }
  };

  const handleUpload = async () => {
    if (!videoFile || !transcriptFile) {
      setError("Please select both video and transcript files");
      return;
    }

    setUploading(true);
    setError("");
    setUploadProgress("Uploading files...");

    try {
      const response = await uploadVideoAndTranscript(
        videoFile,
        transcriptFile,
        customVideoId || undefined
      );

      setUploadProgress(`Upload successful! Video ID: ${response.video_id}`);

      // Call the success callback with the generated video_id and video_path
      setTimeout(() => {
        onUploadSuccess(response.video_id, response.video_path || "");
        // Reset form
        setVideoFile(null);
        setTranscriptFile(null);
        setCustomVideoId("");
        setUploadProgress("");
        setExpandUpload(false);
        if (videoInputRef.current) videoInputRef.current.value = "";
        if (transcriptInputRef.current) transcriptInputRef.current.value = "";
      }, 1500);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(errorMessage);
      setUploadProgress("");
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setVideoFile(null);
    setTranscriptFile(null);
    setCustomVideoId("");
    setError("");
    setUploadProgress("");
    if (videoInputRef.current) videoInputRef.current.value = "";
    if (transcriptInputRef.current) transcriptInputRef.current.value = "";
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 transition-colors"
        onClick={() => setExpandUpload((v) => !v)}
        disabled={disabled}
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-indigo-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <span className="font-semibold text-slate-700">
            Upload Custom Video & Transcript
          </span>
        </div>
        <span className="text-slate-500 text-sm">
          {expandUpload ? "Hide" : "Show"}
        </span>
      </button>

      {expandUpload && (
        <div className="px-4 pb-4 pt-3 space-y-4 bg-slate-50">
          <p className="text-sm text-slate-600">
            Upload your own video and transcript to process without needing a
            YouTube video ID. Your files will be cached for future use.
          </p>

          <div className="space-y-2">
            <label className="label">Video File</label>
            <input
              ref={videoInputRef}
              type="file"
              accept="video/*"
              onChange={handleVideoChange}
              disabled={uploading || disabled}
              className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100 disabled:opacity-50"
            />
            {videoFile && (
              <p className="text-xs text-slate-600">
                Selected: {videoFile.name} (
                {(videoFile.size / (1024 * 1024)).toFixed(2)} MB)
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="label">
              Transcript File (JSON, VTT, or SRT)
              <span className="text-xs text-slate-500 ml-2 font-normal">
                Supports YouTube JSON, WebVTT, or SubRip formats
              </span>
            </label>
            <input
              ref={transcriptInputRef}
              type="file"
              accept=".json,.vtt,.srt,application/json,text/vtt,application/x-subrip"
              onChange={handleTranscriptChange}
              disabled={uploading || disabled}
              className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100 disabled:opacity-50"
            />
            {transcriptFile && (
              <p className="text-xs text-slate-600">
                Selected: {transcriptFile.name} (
                {(transcriptFile.size / 1024).toFixed(2)} KB)
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="label">
              Custom Video ID (Optional)
              <span className="text-xs text-slate-500 ml-2 font-normal">
                Leave empty to auto-generate
              </span>
            </label>
            <input
              type="text"
              className="input"
              value={customVideoId}
              onChange={(e) => setCustomVideoId(e.target.value)}
              placeholder="e.g., my_custom_video"
              disabled={uploading || disabled}
            />
          </div>

          {uploadProgress && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-700">{uploadProgress}</p>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleUpload}
              disabled={!videoFile || !transcriptFile || uploading || disabled}
              className="btn btn-primary flex-1"
            >
              {uploading ? "Uploading..." : "Upload Files"}
            </button>
            <button
              type="button"
              onClick={handleClear}
              disabled={uploading || disabled}
              className="btn btn-secondary"
            >
              Clear
            </button>
          </div>

          <div className="text-xs text-slate-500 space-y-1">
            <p>
              <strong>Note:</strong> After uploading, the generated video ID
              will be automatically filled in the form above.
            </p>
            <p>
              <strong>Supported formats:</strong>
            </p>
            <ul className="list-disc list-inside pl-2 space-y-0.5">
              <li>
                <strong>JSON:</strong> YouTube transcript format with "text",
                "start", and "duration" fields
              </li>
              <li>
                <strong>VTT:</strong> WebVTT subtitle format (will be converted
                automatically)
              </li>
              <li>
                <strong>SRT:</strong> SubRip subtitle format (will be converted
                automatically)
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
