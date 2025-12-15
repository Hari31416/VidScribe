import axios from "axios";

// Access environment variable for API URL or default to localhost
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
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
    file: (projectId: string, artifactType: string, filename: string) =>
      `/files/download?project_id=${encodeURIComponent(
        projectId
      )}&artifact_type=${encodeURIComponent(
        artifactType
      )}&filename=${encodeURIComponent(filename)}`,
  },
  // Ensure we match the backend routes structure
  runs: {
    list: (projectId: string) => `/run/project/${projectId}/runs`,
    get: (projectId: string, runId: string) =>
      `/run/project/${projectId}/runs/${runId}`,
    setCurrent: (projectId: string, runId: string) =>
      `/run/project/${projectId}/current-run?run_id=${runId}`,
  },
  check_health: "/health",
};
