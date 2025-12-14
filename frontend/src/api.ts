import axios from "axios";

// Access environment variable for API URL or default to localhost
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const endpoints = {
  uploads: {
    list: "/uploads/list",
    check: (id: string) => `/uploads/check/${id}`,
    videoAndTranscript: "/uploads/video-and-transcript",
    transcriptOnly: "/uploads/transcript-only",
    deleteVideo: (id: string) => `/uploads/videos/${id}`,
    deleteFrames: (id: string) => `/uploads/frames/${id}`,
    deleteStorage: (id: string) => `/uploads/storage/${id}`,
    deleteProject: (id: string) => `/uploads/project/${id}`,
    getStorageStats: (id: string) => `/uploads/stats/${id}`,
  },
  videos: {
    download: "/videos/download",
    downloadStream: "/videos/download/stream",
  },
  downloads: {
    video: "/videos/download",
    videoStream: "/videos/download/stream",
    file: (path: string, filename?: string) => `/files/download?path=${encodeURIComponent(path)}${filename ? `&filename=${encodeURIComponent(filename)}` : ""}`,
  },
  // Ensure we match the backend routes structure
  check_health: "/health",
};
