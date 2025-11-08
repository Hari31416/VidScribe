# 📚 VidScribe

VidScribe is an AI-powered tool that turns videos into **structured, markdown-style notes** with optional **images extracted from the video**. It helps people who understand better through written content but struggle to retain knowledge from videos.

## 🚀 Project Goals

- Convert **video transcripts** into clean, well-structured notes.
- Enrich notes with **key frames/images** from the video.
- Provide an **optional summary** for quick review.
- Simple React frontend for easy interaction.

## 🛠️ Tech Stack

- **Backend / Orchestration**: Python, FastAPI (future), LangGraph
- **LLM**: OpenAI (or other LLMs)
- **Transcript**: YouTube Transcript API / VTT / SRT / JSON
- **Video Frames**: ffmpeg / OpenCV + CLIP (optional filtering)
- **Frontend**: React

## 📂 Planned Project Structure (MVP)

In the `backend/` folder:

```bash
VidScribe/
│── app/
│   ├── main.py               # Gradio entrypoint
│   ├── graph/
│   │   ├── langgraph.py      # Graph assembly
│   │   └── nodes/            # Individual pipeline nodes
│   │       ├── transcript.py
│   │       ├── chunker.py
│   │       ├── notes_agent.py
│   │       ├── summary_agent.py
│   │       ├── frame_extractor.py
│   │       └── formatter.py
│── outputs/                  # Generated notes & images
│   ├── notes.md
│   ├── summary.md
│   └── images/
│── requirements.txt
│── README.md
```

## 📅 Development Plan

- **Weekend 1**: Transcript → Structured Notes (MVP text only).
- **Weekend 2**: Add image extraction + integrate into notes.
- **Weekend 3**: Add summary + polish Gradio app.
- **Weekend 4+**: Move to full FastAPI + React app.

## 🧪 FastAPI (API) Quickstart

A minimal FastAPI server is available alongside the Gradio app with endpoints including:

- POST /run/stream — live progress via Server-Sent Events (SSE)
- POST /run/final — run to completion and return the final result as JSON
- POST /videos/download — download a YouTube video (audio/video) to `backend/outputs/videos/{video_id}`
- POST /videos/download/stream — stream progress events while downloading a video
- GET /files/download?path=... — serve generated files (PDF, Markdown, media) from `backend/outputs`

How to run locally:

```bash
cd backend
pip install -r requirements.txt
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

Example requests (now also require a `video_path` pointing to the local downloaded video; this is used for frame extraction):

- Streaming (SSE). You can test with curl; it will print events as they arrive.

```bash
curl -N -H "Content-Type: application/json" \
  -X POST http://localhost:8000/run/stream \
  -d '{
    "video_id": "wjZofJX0v4M",
    "video_path": "/home/USER/Desktop/VidScribe/backend/outputs/videos/wjZofJX0v4M/Transformers_the_tech_behind_LLMs_Deep_Learning_Chapter_5.mp4",
    "num_chunks": 2,
    "provider": "google",
    "model": "gemini-2.0-flash",
    "stream_config": { "include_data": true }
  }'
```

- Final-only JSON result:

```bash
curl -H "Content-Type: application/json" \
  -X POST http://localhost:8000/run/final \
  -d '{
    "video_id": "wjZofJX0v4M",
    "video_path": "/home/USER/Desktop/VidScribe/backend/outputs/videos/wjZofJX0v4M/Transformers_the_tech_behind_LLMs_Deep_Learning_Chapter_5.mp4",
    "num_chunks": 2,
    "provider": "google",
    "model": "gemini-2.0-flash"
  }'
```

- Download a YouTube video (returns JSON with file paths and pre-built download URLs):

```bash
curl -H "Content-Type: application/json" \
  -X POST http://localhost:8000/videos/download \
  -d '{
    "video_id": "wjZofJX0v4M",
    "resolution": 720
  }'
```

- Stream video download progress (SSE). Each event contains status, byte counts, and final result metadata:

```bash
curl -N -H "Content-Type: application/json" \
  -X POST http://localhost:8000/videos/download/stream \
  -d '{
    "video_id": "wjZofJX0v4M",
    "resolution": 720
  }'
```

- Download a generated asset (use `relative_path` returned by the API or any path under `backend/outputs`):

```bash
curl -L "http://localhost:8000/files/download?path=notes/wjZofJX0v4M/summary.pdf" --output summary.pdf
```

## 📤 Custom Video & Transcript Upload

Upload your own videos and transcripts for processing without needing YouTube videos. Supports multiple transcript formats:

### Upload Endpoints

- **POST /uploads/video-and-transcript** — Upload a video file with transcript
- **GET /uploads/check/{video_id}** — Check if video and transcript exist
- **GET /uploads/list** — List all uploaded video folders

### Supported Transcript Formats

- **JSON**: YouTube transcript API format with `text`, `start`, and `duration` fields
- **VTT**: WebVTT subtitle format (automatically converted)
- **SRT**: SubRip subtitle format (automatically converted)

### Upload Example

```bash
curl -X POST "http://localhost:8000/uploads/video-and-transcript" \
  -F "video=@my_video.mp4" \
  -F "transcript=@transcript.vtt" \
  -F "video_id=my_custom_video"
```

### List Available Uploads

```bash
curl "http://localhost:8000/uploads/list"
# Returns: {"uploaded_video_ids": ["upload_abc123", "upload_def456", ...]}
```

## 🗂️ Storage Management

Manage storage space by deleting large video files and extracted frames. Transcripts and generated notes are preserved.

### Storage Management Endpoints

- **DELETE /uploads/videos/{video_id}** — Delete video files only
- **DELETE /uploads/frames/{video_id}** — Delete frame images only
- **DELETE /uploads/storage/{video_id}** — Delete both videos and frames

### Delete Examples

```bash
# Delete video files only (frees most space)
curl -X DELETE "http://localhost:8000/uploads/videos/upload_abc123"

# Delete frame images only
curl -X DELETE "http://localhost:8000/uploads/frames/upload_abc123"

# Delete both videos and frames (maximum space freed)
curl -X DELETE "http://localhost:8000/uploads/storage/upload_abc123"
```

Each deletion response includes the space freed in MB:

```json
{
  "status": "success",
  "video_id": "upload_abc123",
  "message": "Successfully deleted storage for video_id: upload_abc123",
  "deleted_items": { "videos": true, "frames": true },
  "space_freed_mb": 245.67
}
```

## 🖥️ Frontend (Vite + React)

A dedicated Vite/React dashboard lives in `frontend/`. It mirrors the Gradio experience with:

- Streaming progress from `/run/stream` via POST + SSE parsing
- Final-run support using `/run/final`
- Configurable stream shaping (compact mode, included fields, truncation limits)
- Rich counters, event log, and per-section outputs for quick inspection
- **Custom video & transcript upload** with support for VTT, SRT, and JSON formats
- **Storage management** with dropdown selection of uploaded videos for deletion

### Prerequisites

- Node.js 18 or newer (tested with npm 11)
- The FastAPI server running locally (defaults to `http://localhost:8000`)

### Quickstart

```bash
cd frontend
npm install
cp .env.example .env.local   # optional, adjust VITE_API_BASE_URL if backend differs
npm run dev
```

This starts Vite on `http://localhost:5173` (configurable via `VITE_PORT`). Update `VITE_API_BASE_URL` if your API listens on a different host or port.

### Production build

```bash
cd frontend
npm run build
```

The optimized assets are emitted to `frontend/dist/` and can be served by any static host.

## 🛠️ Makefile helpers

The repository provides a top-level `Makefile` to streamline common workflows:

```bash
# Install backend (pip) and frontend (npm) dependencies
make install

# Build the frontend bundle (backend currently has no build step)
make build

# Run just one side
make backend-run
make frontend-run

# Launch FastAPI and the Vite dev server together (Ctrl+C stops both)
make run
```

Adjust `PYTHON`, `NPM`, or other variables when invoking make if your environment differs, for example `make PYTHON=python3.11 install`.

Notes:

- The API reuses the existing LangGraph pipeline. For streaming, each SSE event now has shape `{ phase, progress, message, data, counters, stream }` (see schema below).
- New pipeline phase: `image_integration` appears between `chunk_notes` and formatting when images are being integrated per chunk.
- Progress mapping (heuristic): `chunks` (~20%) → `chunk_notes` (20–40%) → `image_integration` (40–50%) → `format_docs` (50–80%) → `collect_notes` (90%) → `summary` (100%).
- `video_path` must point to the local MP4 used for frame extraction. You can derive it from the downloaded video directory (e.g. `backend/outputs/videos/{video_id}/...mp4`).
- CORS is enabled for local development by default. Restrict origins before deploying.

### Event/response schema

- SSE event (from `/run/stream`):

```jsonc
{
  "phase": "chunk_notes", // string lifecycle phase
  "progress": 35, // 0-100 (heuristic)
  "message": "Chunk notes generated", // human-readable
  "data": {
    // shaped state subset
    "chunks": ["..."],
    "chunk_notes": ["..."],
    "image_integrated_notes": ["..."],
    "formatted_notes": ["..."],
    "collected_notes": "...",
    "summary": "...",
    "timestamps_output": [[{ "timestamp": "00:00:42", "reason": "..." }]],
    "image_insertions_output": [
      [{ "timestamp": "00:00:42", "line_number": 3, "caption": "..." }]
    ],
    "extracted_images_output": [
      [{ "timestamp": "00:00:42", "frame_path": ".../frame.jpg" }]
    ],
    "integrates": [
      /* per-chunk integration objects */
    ]
  },
  "counters": {
    // derived real-time metrics
    "expected_chunks": 10,
    "notes_created": { "current": 3, "total": 10 },
    "integrated_image_notes_created": { "current": 2, "total": 10 },
    "formatted_notes_created": { "current": 1, "total": 10 },
    "timestamps_created": {
      "current_items": 18,
      "chunks_completed": 3,
      "total_chunks": 10
    },
    "image_insertions_created": {
      "current_items": 12,
      "chunks_completed": 2,
      "total_chunks": 10
    },
    "extracted_images_created": {
      "current_items": 5,
      "chunks_completed": 2,
      "total_chunks": 10
    },
    "finalization": { "collected": false, "summary": false },
    "notes_by_type": {
      "raw": 3,
      "integrated": 2,
      "formatted": 1,
      "collected": 0,
      "summary": 0
    }
  },
  "stream": {
    // stream metadata
    "mode": "values", // "values" | "updates"
    "update": null // present only for updates
  }
}
```

- Final-only response (from `/run/final`) mirrors a single event without the `stream` block:

```jsonc
{
  "phase": "done",
  "progress": 100,
  "message": "Graph execution completed",
  "data": {
    /* same shape as above */
  },
  "counters": {
    /* same shape as above */
  }
}
```

### stream_config

The `stream_config` object controls shaping of `data`:

- `include_data` (bool): default true
- `include_fields` (list of strings): subset of fields to include. Valid keys:
  - `chunks`, `chunk_notes`, `image_integrated_notes`, `formatted_notes`, `collected_notes`, `summary`
  - `timestamps_output`, `image_insertions_output`, `extracted_images_output`, `integrates`
- `max_items_per_field` (int): truncate list fields
- `max_chars_per_field` (int): truncate long strings and list items

## ⚠️ Status

MVP is under active development: transcript → structured notes working; image extraction & integration stage added; API and Gradio support streaming with selectable fields including `image_integrated_notes`. Stream events now include derived `counters` and `stream` metadata to support richer progress UIs.

**Recent additions:**

- ✅ Custom video & transcript upload support (VTT, SRT, JSON formats)
- ✅ Storage management system for deleting videos and frames
- ✅ Enhanced frontend with upload and storage management UI
- ✅ Automatic transcript format conversion (VTT/SRT → JSON)

### Gradio UI Deprecation

Gradio UI is being deprecated in favor of the React frontend. The Gradio app will remain functional for now but will not receive further enhancements.

### React Frontend Features

- **Upload Panel**: Upload custom videos with VTT, SRT, or JSON transcripts
- **Storage Management**: Dropdown selection of uploaded videos for deletion with space usage feedback
- **Streaming Progress**: Real-time pipeline progress with counters and event logs
- **Configuration Options**: Advanced settings for stream shaping and processing parameters

## The Architecture

```mermaid
flowchart TD
    %% Subgraph 1: Video Input to Chunk Generation
    subgraph SG1 ["Transcript & Chunk Preparation"]
        VI["Video Input"]
        TG["Transcript Generator"]
        CH["Chunker"]
        NA["Notes Agent Chunk"]
    end

    %% Subgraph 2: Raw Notes to Image Integration
  subgraph SG2 ["Image Extraction & Integration"]
    RN["Raw Notes (per chunk)"]
    TS["Timestamp Generator"]
    IE["Image Extractor (frames)"]
    II["Image Integrator"]
    IN["Integrated Notes (per chunk)"]
    FN["Formatted Notes (per chunk)"]
  end

    %% Subgraph 3: Integrated Notes to Final Notes & Summary
    subgraph SG3 ["Notes Processing & Summarization"]
        NC["Notes Collector"]
        FN1[[Final Notes]]
        SA["Summary Agent"]
        SM[[Summary]]
    end

    %% Connections
    MF["Markdown Formatter"]
    VI --> TG --> CH --> NA
    NA -->|"multiple chunks"| RN
  RN --> TS --> IE --> II --> IN --> MF --> FN
    FN -->|"multiple formatted chunks"| NC
    MF <--> NC --> FN1
    FN1 --> SA --> SM
    SA <--> MF

    %% Styles
    classDef input fill:#ffefd5,stroke:#e67e22,stroke-width:2px,color:#000,font-weight:bold;
    classDef process fill:#d1e8ff,stroke:#2980b9,stroke-width:2px,color:#000;
    classDef agent fill:#eafbea,stroke:#27ae60,stroke-width:2px,color:#000,font-style:italic;
    classDef output fill:#ffe6e6,stroke:#c0392b,stroke-width:2px,color:#000,font-weight:bold;
    classDef special fill:#f9e6ff,stroke:#8e44ad,stroke-width:2px,color:#000;

    %% Assign classes
    class VI input;
    class TG,CH process;
    class NA,NC,MF,SA,TG,TS,II,IM agent;
    class FS special;
    class IE special;
    class FN1,SM,RN,FN,IN output;
```
