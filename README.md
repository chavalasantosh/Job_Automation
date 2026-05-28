# NowCurry Infinity 🍛

**NowCurry Infinity (v2)** is an industrial-grade, AI-driven multi-agent fleet designed for automated job searching, intelligent resume uploading, and autonomous job application submissions across major career portals.

This system leverages large language models (via Ollama and Google Generative AI) combined with stealth browsing techniques to navigate modern application flows, bypass anti-bot protections, and manage the entire career operation lifecycle.

## 🚀 Features

- **Multi-Portal Support**: Dedicated agents for major job platforms:
  - **LinkedIn** (`LinkieDin`)
  - **Naukri**
  - **Foundit**
  - **Glassdoor** (`GallasuDooru`)
  - **Indeed** (`InDeed`)
- **Omni-Agent Fleet Coordination**: Launch all agents simultaneously via a centralized `master_dispatch.py` coordinator.
- **Stealth Mode Browsing**: Uses customized Selenium and Playwright with Cloudflare IUAM bypass strategies (e.g., off-screen window positioning) to avoid detection.
- **AI-Powered RAG Engine**: 
  - Uses local Ollama (Gemma 4) and Google Generative AI for intelligent resume extraction and application question answering.
  - Contextual Agentic RAG capabilities to maintain career graphs and application context.
- **Infinity Command Center (Dashboard)**:
  - Real-time React/Vite/Tailwind dashboard (`/dashboard`) for monitoring fleet status, application success rates, and live logs.
  - "Theater Mode" visual relay for capturing and viewing live screenshots from worker pods.
- **Robust Infrastructure**: Containerized with Docker Compose, featuring FastAPI (Control Plane), Celery/Redis (Message Bus/Workers), and PostgreSQL (State Persistence).

## 🏗️ Architecture

The system is divided into four main layers (as defined in `docker-compose.yml`):

1. **Control Plane (The Brain)**: A FastAPI backend (`server.py`) that handles API requests, fleet status, and telemetry streams.
2. **Data Plane (The Hive Workers)**: Celery workers executing background automation tasks (`NowCurry.tasks`).
3. **Nervous System (Message Bus)**: Redis for managing task queues and rapid state sharing.
4. **Command Center (Dashboard)**: A Vite + React application providing a beautiful UI for monitoring the autonomous fleet.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Celery
- **Frontend**: React (v19), Vite, TailwindCSS, Framer Motion, Recharts
- **Database / Cache**: PostgreSQL, Redis, SQLite (for local native mode)
- **Automation / Scraping**: Selenium, Playwright, curl-cffi
- **AI Integration**: Ollama, `google-generativeai`, local RAG pipelines

## ⚙️ Prerequisites

- **Docker & Docker Compose** (for containerized deployment)
- **Python 3.10+** (for native/local execution)
- **Node.js 18+** (for local dashboard development)
- **Ollama**: Must be running locally with the Gemma 4 model (or your configured local LLM) for local AI features.
- A valid `GEMINI_API_KEY` for external AI fallback.

## 🚀 Quickstart (Native / Local Mode)

1. **Install Dependencies**:
   ```powershell
   pip install -r requirements_worker.txt
   ```

2. **Initialize the Database**:
   The database will initialize automatically upon starting the master dispatch, but ensure your SQLite permissions are set if running purely local.

3. **Start the Fleet**:
   You can run the entire fleet locally using the single-window launcher:
   ```powershell
   python master_dispatch.py
   ```
   *Note: Ensure Ollama is running locally on port 11434 before launching.*

4. **Start the API Server**:
   ```powershell
   python server.py
   ```

## 🐳 Deployment (Dockerized Hive)

To spin up the entire production infrastructure (API, Workers, DB, Redis, and Dashboard):

```bash
# Provide your Gemini API key in a .env file or inline
docker-compose up --build -d
```

Access the **Command Center Dashboard** at `http://localhost:5173`.
Access the **FastAPI Swagger UI** at `http://localhost:8000/docs`.

## 📁 Repository Structure

- `/Agent`: Core agent architectures (SingleAgent and MultiAgent coordinators).
- `/LinkieDin`, `/InDeed`, `/GallasuDooru`, `/Foundit`: Portal-specific automation scripts (login, apply, resume upload).
- `/RAG`: Agentic Retrieval-Augmented Generation engines for AI decision making.
- `/dashboard`: The React/Vite source code for the command center UI.
- `/missions`: Storage for application screenshots and visual telemetry.
- `master_dispatch.py`: The main entry point for running the Omni-Agent fleet natively.
- `server.py`: The core FastAPI application.

## ⚠️ Disclaimer

This software is designed for educational and personal automation purposes. Be aware that automated interactions with job portals may violate their Terms of Service. Use responsibly and ensure compliance with platform rules.
