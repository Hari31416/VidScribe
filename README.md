# 📚 VidScribe

VidScribe is an AI-powered tool that turns videos into **structured, markdown-style notes** with optional **images extracted from the video**. It helps people who understand better through written content but struggle to retain knowledge from videos.

## 🚀 Project Goals

- Convert **video transcripts** into clean, well-structured notes.
- Enrich notes with **key frames/images** from the video.
- Provide an **optional summary** for quick review.
- Simple **Gradio app** for the MVP (later React frontend planned).

## 🛠️ Tech Stack

- **Backend / Orchestration**: Python, FastAPI (future), LangGraph
- **LLM**: OpenAI (or other LLMs)
- **Transcript**: Whisper / YouTube Transcript API
- **Video Frames**: ffmpeg / OpenCV + CLIP (optional filtering)
- **Frontend (MVP)**: Gradio
- **Future Frontend**: React

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

## ⚠️ Status

🔨 Work has not started yet. This README will be updated as development progresses.
