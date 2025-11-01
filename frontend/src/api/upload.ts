const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface UploadResponse {
  status: string;
  video_id: string;
  message: string;
  video_path?: string;
  transcript_path?: string;
}

export interface CheckUploadResponse {
  video_id: string;
  video_exists: boolean;
  transcript_exists: boolean;
  video_files: string[];
  transcript_path: string | null;
  ready_for_processing: boolean;
}

/**
 * Upload a video file and its transcript to the backend
 * @param videoFile - The video file to upload
 * @param transcriptFile - The transcript JSON file
 * @param videoId - Optional custom video ID (will be generated if not provided)
 * @returns Promise with upload response
 */
export async function uploadVideoAndTranscript(
  videoFile: File,
  transcriptFile: File,
  videoId?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("video", videoFile);
  formData.append("transcript", transcriptFile);
  if (videoId) {
    formData.append("video_id", videoId);
  }

  const response = await fetch(`${API_BASE_URL}/uploads/video-and-transcript`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage: string;
    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.detail || errorText;
    } catch {
      errorMessage = errorText;
    }
    throw new Error(
      `Upload failed with status ${response.status}: ${errorMessage}`
    );
  }

  return (await response.json()) as UploadResponse;
}

/**
 * Check if a video and transcript exist for a given video ID
 * @param videoId - The video ID to check
 * @returns Promise with check response
 */
export async function checkUpload(
  videoId: string
): Promise<CheckUploadResponse> {
  const response = await fetch(`${API_BASE_URL}/uploads/check/${videoId}`, {
    method: "GET",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Check upload failed with status ${response.status}: ${errorText}`
    );
  }

  return (await response.json()) as CheckUploadResponse;
}
