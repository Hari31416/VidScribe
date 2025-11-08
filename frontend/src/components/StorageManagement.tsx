import { useState, useEffect } from "react";
import {
  deleteVideo,
  deleteFrames,
  deleteStorage,
  listUploads,
} from "../api/upload";
import type { DeleteResponse } from "../api/upload";

interface Props {
  disabled?: boolean;
}

export function StorageManagement({ disabled = false }: Props) {
  const [videoId, setVideoId] = useState<string>("");
  const [videoIds, setVideoIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteResult, setDeleteResult] = useState<DeleteResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [expandStorage, setExpandStorage] = useState(false);

  // Fetch video IDs when panel is expanded
  useEffect(() => {
    if (expandStorage && videoIds.length === 0) {
      fetchVideoIds();
    }
  }, [expandStorage]);

  const fetchVideoIds = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await listUploads();
      setVideoIds(response.uploaded_video_ids);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load video IDs";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (deleteType: "videos" | "frames" | "storage") => {
    if (!videoId.trim()) {
      setError("Please enter a video ID");
      return;
    }

    setDeleting(true);
    setError("");
    setDeleteResult(null);

    try {
      let response: DeleteResponse;

      switch (deleteType) {
        case "videos":
          response = await deleteVideo(videoId);
          break;
        case "frames":
          response = await deleteFrames(videoId);
          break;
        case "storage":
          response = await deleteStorage(videoId);
          break;
      }

      setDeleteResult(response);

      // Refresh the list of video IDs after deletion
      await fetchVideoIds();

      // Auto-clear after 3 seconds
      setTimeout(() => {
        setDeleteResult(null);
        setVideoId("");
      }, 3000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Delete failed";
      setError(errorMessage);
    } finally {
      setDeleting(false);
    }
  };

  const handleClear = () => {
    setVideoId("");
    setError("");
    setDeleteResult(null);
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 bg-gradient-to-r from-red-50 to-orange-50 hover:from-red-100 hover:to-orange-100 transition-colors"
        onClick={() => setExpandStorage((v) => !v)}
        disabled={disabled}
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          <span className="font-semibold text-slate-700">
            Storage Management
          </span>
        </div>
        <span className="text-slate-500 text-sm">
          {expandStorage ? "Hide" : "Show"}
        </span>
      </button>

      {expandStorage && (
        <div className="px-4 pb-4 pt-3 space-y-4 bg-slate-50">
          <p className="text-sm text-slate-600">
            Free up storage space by deleting large video files and extracted
            frames. Notes and transcripts are preserved.
          </p>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="label">Video ID</label>
              <button
                type="button"
                onClick={fetchVideoIds}
                disabled={loading || deleting || disabled}
                className="text-xs text-violet-600 hover:text-violet-700 font-medium disabled:opacity-50"
              >
                {loading ? "Loading..." : "🔄 Refresh"}
              </button>
            </div>
            {videoIds.length > 0 ? (
              <select
                className="input"
                value={videoId}
                onChange={(e) => setVideoId(e.target.value)}
                disabled={deleting || disabled || loading}
              >
                <option value="">Select a video ID to delete...</option>
                {videoIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                className="input"
                value={videoId}
                onChange={(e) => setVideoId(e.target.value)}
                placeholder="e.g., FOONnnq975k or upload_xyz123"
                disabled={deleting || disabled || loading}
              />
            )}
            <p className="text-xs text-slate-500">
              {videoIds.length > 0
                ? `${videoIds.length} video folder${
                    videoIds.length !== 1 ? "s" : ""
                  } available`
                : "No uploaded videos found, or enter a video ID manually"}
            </p>
          </div>

          {deleteResult && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-700 font-semibold">
                {deleteResult.message}
              </p>
              {deleteResult.space_freed_mb !== undefined && (
                <p className="text-xs text-green-600 mt-1">
                  Space freed: {deleteResult.space_freed_mb.toFixed(2)} MB
                </p>
              )}
              <div className="text-xs text-green-600 mt-1">
                Deleted:{" "}
                {Object.entries(deleteResult.deleted_items)
                  .filter(([_, deleted]) => deleted)
                  .map(([item]) => item)
                  .join(", ") || "none"}
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-700 uppercase">
              Delete Options
            </p>
            <div className="grid grid-cols-1 gap-2">
              <button
                type="button"
                onClick={() => handleDelete("videos")}
                disabled={!videoId.trim() || deleting || disabled}
                className="btn bg-orange-100 text-orange-700 hover:bg-orange-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg
                  className="w-4 h-4 inline mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
                {deleting ? "Deleting..." : "Delete Videos Only"}
              </button>

              <button
                type="button"
                onClick={() => handleDelete("frames")}
                disabled={!videoId.trim() || deleting || disabled}
                className="btn bg-amber-100 text-amber-700 hover:bg-amber-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg
                  className="w-4 h-4 inline mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                {deleting ? "Deleting..." : "Delete Frames Only"}
              </button>

              <button
                type="button"
                onClick={() => handleDelete("storage")}
                disabled={!videoId.trim() || deleting || disabled}
                className="btn bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg
                  className="w-4 h-4 inline mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
                {deleting ? "Deleting..." : "Delete Both (Videos + Frames)"}
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={handleClear}
            disabled={deleting || disabled}
            className="btn btn-secondary w-full"
          >
            Clear
          </button>

          <div className="text-xs text-slate-500 space-y-1 bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="font-semibold text-amber-700">⚠️ Important Notes:</p>
            <ul className="list-disc list-inside pl-2 space-y-0.5">
              <li>
                <strong>Videos Only:</strong> Deletes raw video files (largest
                storage use)
              </li>
              <li>
                <strong>Frames Only:</strong> Deletes extracted frame images
              </li>
              <li>
                <strong>Both:</strong> Deletes videos and frames (maximum space
                freed)
              </li>
              <li>
                Transcripts and generated notes are{" "}
                <strong>never deleted</strong>
              </li>
              <li>
                This action <strong>cannot be undone</strong>
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
