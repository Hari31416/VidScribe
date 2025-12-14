# 🎬 VidScribe

**AI-Powered Video Transcript to Notes Generator**

VidScribe is a full-stack application that transforms video transcripts into comprehensive, well-formatted notes using LangGraph-based AI pipelines. It supports YouTube video import, multiple transcript formats, frame extraction for visual context, and exports to PDF.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-0.6-purple)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

---

## ✨ Features

### 📝 Notes Generation
- **AI-Powered Processing**: Multi-agent LangGraph pipeline for intelligent note generation
- **Chunk-Based Processing**: Splits transcripts into manageable chunks for quality output
- **Image Integration**: Automatically extracts key frames from videos and integrates them into notes
- **Smart Summarization**: Generates executive summaries of the full content
- **PDF Export**: Export notes and summaries as formatted PDF documents

### 🎥 Video & Transcript Support
- **YouTube Import**: Download videos and transcripts directly via yt-dlp
- **Multiple Formats**: Supports VTT, SRT, and JSON transcript uploads
- **Transcript-Only Mode**: Process transcripts without video for faster, text-only notes
- **Frame Extraction**: OpenCV-powered frame extraction at key timestamps

### 🔐 User Management
- **JWT Authentication**: Secure token-based authentication
- **User Projects**: Each user has isolated project storage
- **Admin Dashboard**: User management and system overview

### 🌐 Multi-Provider LLM Support
- **Google Gemini**: Default provider with Gemini 2.0 Flash
- **OpenAI**: GPT-4 and GPT-3.5 support
- **Groq**: Fast inference with Llama models
- **NVIDIA AI Endpoints**: Enterprise-grade inference

### 📡 Real-Time Progress
- **Server-Sent Events (SSE)**: Live progress streaming to frontend
- **Phase Tracking**: Monitor each stage of the pipeline
- **Detailed Counters**: Track chunks, notes, and image processing progress

---

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend (React + Vite)"]
        UI[Web Interface]
        Auth[Authentication]
        Dashboard[Project Dashboard]
        Viewer[Notes Viewer]
    end

    subgraph API["Backend (FastAPI)"]
        Routes[API Routes]
        AuthService[Auth Service]
        Pipeline[LangGraph Pipeline]
        Storage[Storage Service]
    end

    subgraph LLM["LLM Providers"]
        Google[Google Gemini]
        OpenAI[OpenAI GPT]
        Groq[Groq]
        NVIDIA[NVIDIA AI]
    end

    subgraph Infrastructure["Infrastructure"]
        MinIO[(MinIO<br/>Object Storage)]
        MongoDB[(MongoDB<br/>Database)]
    end

    UI --> Routes
    Auth --> AuthService
    Dashboard --> Routes
    Viewer --> Routes
    
    Routes --> Pipeline
    Routes --> Storage
    Pipeline --> Google & OpenAI & Groq & NVIDIA
    
    Storage --> MinIO
    AuthService --> MongoDB
    Routes --> MongoDB
```

---

## 🔄 Notes Generation Pipeline

The core of VidScribe is a LangGraph-based multi-agent pipeline:

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API as FastAPI
    participant Graph as LangGraph Pipeline
    participant LLM as LLM Provider
    participant Storage as MinIO

    User->>API: Start Pipeline (project_id, config)
    API->>Graph: Initialize Pipeline
    
    rect rgb(240, 248, 255)
        Note over Graph: Phase 1: Transcript Processing
        Graph->>Storage: Fetch Transcript
        Graph->>Graph: Chunk Transcript
    end

    rect rgb(255, 248, 240)
        Note over Graph: Phase 2: Notes Generation (Parallel)
        loop For Each Chunk
            Graph->>LLM: Generate Chunk Notes
            LLM-->>Graph: Structured Notes
        end
    end

    rect rgb(240, 255, 240)
        Note over Graph: Phase 3: Image Integration
        Graph->>LLM: Generate Timestamps
        Graph->>Storage: Extract Frames (FFmpeg)
        Graph->>LLM: Integrate Images into Notes
    end

    rect rgb(255, 240, 255)
        Note over Graph: Phase 4: Final Processing
        Graph->>LLM: Format & Collect Notes
        Graph->>LLM: Generate Summary
        Graph->>Graph: Export to PDF
    end

    Graph->>Storage: Save Artifacts
    Graph-->>API: Pipeline Complete
    API-->>User: SSE: Final Results
```

### Pipeline Nodes

| Node | Description |
|------|-------------|
| `create_transcript_chunks` | Splits transcript into configurable chunks |
| `chunk_notes_agent` | Generates notes for each chunk |
| `timestamp_generator_agent` | Identifies key timestamps for frames |
| `extract_frames` | Extracts video frames using OpenCV |
| `image_integrator_agent` | Integrates frames into notes |
| `formatter_agent` | Formats notes with consistent styling |
| `notes_collector_agent` | Combines all chunk notes |
| `summarizer_agent` | Generates executive summary |
| `exporter_agent` | Exports final PDF documents |

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | Modern async Python web framework |
| **LangGraph** | Multi-agent orchestration framework |
| **LangChain** | LLM abstraction and tooling |
| **LiteLLM** | Unified LLM provider interface |
| **yt-dlp** | YouTube video/transcript download |
| **OpenCV** | Video frame extraction |
| **FFmpeg** | Video processing |
| **Boto3** | MinIO/S3 client |
| **PyMongo** | MongoDB driver |
| **python-jose** | JWT authentication |

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 19** | UI framework |
| **Vite** | Build tool and dev server |
| **TypeScript** | Type safety |
| **TailwindCSS** | Utility-first styling |
| **shadcn/ui** | Component library |
| **React Query** | Server state management |
| **Axios** | HTTP client |
| **React Router** | Client-side routing |
| **Lucide React** | Icon library |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **MinIO** | S3-compatible object storage |
| **MongoDB** | Document database |
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **FFmpeg** (for video processing)
- **Pandoc** (for markdown to PDF conversion)
- **XeLaTeX** (LaTeX engine for PDF generation)
  - macOS: `brew install --cask mactex-no-gui`
  - Ubuntu/Debian: `sudo apt install texlive-xetex texlive-fonts-recommended`


### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/hari31416/VidScribe.git
cd VidScribe

# Copy environment files
cp backend/.env.example backend/.env
# Edit backend/.env with your LLM API keys

# Start all services
docker compose up -d

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# MinIO Console: http://localhost:9001
```

### Local Development

```bash
# Start infrastructure services (MinIO + MongoDB)
make up

# Install dependencies
make install

# Run backend and frontend
make run

# View logs
make logs

# Stop services
make stop
```

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install backend and frontend dependencies |
| `make run` | Start backend and frontend in background |
| `make stop` | Stop all services |
| `make logs` | Tail backend and frontend logs |
| `make up` | Start Docker infrastructure (MinIO, MongoDB) |
| `make down` | Stop Docker infrastructure |
| `make clean` | Remove build artifacts and logs |

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# MongoDB
MONGO_URI=mongodb://admin:password@localhost:27018
DEFAULT_USERNAME=default

# MinIO / S3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
S3_USE_SSL=false

# Authentication
SECRET_KEY=your-super-secret-key-change-in-production
TOKEN_EXPIRE_MINUTES=1440

# Admin User
ADMIN_USER_NAME=admin
ADMIN_PASSWORD=PassWord@1234
ADMIN_EMAIL=admin@example.com

# LLM Providers (add keys for providers you use)
GOOGLE_API_KEY=your-google-key
OPENAI_API_KEY=your-openai-key
GROQ_API_KEY=your-groq-key

# Logging
LOG_LEVEL=warning
```

### Frontend Configuration

Create a `.env` file in the `frontend/` directory:

```bash
VITE_API_URL=http://localhost:8000
```

---

## 📚 API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Login with username/password |
| `/auth/register` | POST | Register new user |
| `/auth/me` | GET | Get current user info |

### Projects & Uploads

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/uploads/list` | GET | List user's projects |
| `/uploads/video-and-transcript` | POST | Upload video + transcript |
| `/uploads/transcript-only` | POST | Upload transcript only |
| `/uploads/check/{id}` | GET | Check project status |
| `/uploads/project/{id}` | DELETE | Delete project |
| `/uploads/stats/{id}` | GET | Get storage statistics |

### Pipeline Execution

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/run/stream` | POST | Run pipeline with SSE progress |
| `/run/final` | POST | Run pipeline, return final result |
| `/run/project/{id}/runs` | GET | List pipeline runs |

### Downloads

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/files/download` | GET | Download project artifacts |
| `/videos/download` | POST | Download YouTube video |

---

## 🐳 Docker Deployment

### Production Deployment

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v
```

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 5173 | React application |
| Backend | 8000 | FastAPI server |
| MinIO API | 9000 | S3-compatible API |
| MinIO Console | 9001 | Web management UI |
| MongoDB | 27018 | Database (mapped from 27017) |

---

## 📁 Project Structure

```
VidScribe/
├── backend/
│   ├── app/
│   │   ├── graph/           # LangGraph pipeline
│   │   │   ├── nodes/       # Pipeline agents
│   │   │   ├── graph.py     # Graph construction
│   │   │   └── runner.py    # Pipeline execution
│   │   ├── prompts/         # LLM system prompts
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utilities
│   ├── main.py              # FastAPI app entry
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── context/         # React context
│   │   └── api.ts           # API client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml       # Multi-container setup
├── Makefile                 # Development commands
└── README.md
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for the multi-agent framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube integration
- [shadcn/ui](https://ui.shadcn.com/) for beautiful React components
