# Digidelsolutions Resume Parser — Deployment Package

## What's Included

This is a complete, production-ready FastAPI application for the Digidelsolutions HR Resume Parser & Filter Pipeline.

### Project Structure

```
Phase3_Resume_Hub/
├── Dockerfile              # Docker container config
├── docker-compose.yml      # Local development with Docker
├── render.yaml             # Render.com blueprint (auto-deploy)
├── requirements.txt        # Python dependencies
├── README.md               # Quick start guide
└── app/
    ├── __init__.py         # Python package marker
    ├── main.py             # FastAPI entry point (all endpoints + dashboard)
    ├── core/
    │   ├── __init__.py     # Python package marker
    │   ├── extractor.py    # PDF/DOCX/TXT/RTF text extraction
    │   ├── structured_parser.py  # Regex-based NLP parsing
    │   ├── filter_engine.py      # First-pass filter rules
    │   └── config/         # Role configurations
    └── test_resumes/       # Sample resumes for testing
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info & endpoint list |
| `/health` | GET | Health check |
| `/parse` | POST | Parse a single resume file |
| `/filter` | POST | Apply filter to a parsed profile |
| `/pipeline` | POST | Full pipeline: upload → parse → filter → decision |
| `/batch` | POST | Process multiple resumes at once |
| `/stats` | GET | Pipeline statistics |
| `/results` | GET | Get processed results (with filtering) |
| `/dashboard` | GET | Web UI (HTML) |

## Deploy on Render (Free Tier)

### Option 1: Blueprint (One-Click)

1. Push this code to a GitHub repository
2. Go to [dashboard.render.com](https://dashboard.render.com)
3. Click **New +** → **Blueprint**
4. Connect your GitHub repo
5. Render will auto-read `render.yaml` and deploy

### Option 2: Manual Web Service

1. Push code to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com)
3. Click **New +** → **Web Service**
4. Connect your GitHub repo
5. Use these settings:
   - **Runtime:** Docker
   - **Branch:** main
   - **Root Directory:** (leave blank)
   - **Dockerfile Path:** `./Dockerfile`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Deploy Locally (Docker)

```bash
docker-compose up --build
```

App will be at: http://localhost:8000

Dashboard: http://localhost:8000/dashboard

## Deploy Locally (Python)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port (Render auto-sets this) |
| `APP_ENV` | `production` | Environment name |
| `PYTHONPATH` | `/app` | Python path (set in Docker) |

## Notes

- **In-memory storage:** This demo uses in-memory lists for session data. For production, connect to a PostgreSQL/Supabase database using the D1 schema from Phase 1.
- **File uploads:** Temp files are cleaned up after processing.
- **CORS:** Enabled for all origins (`*`) for demo purposes. Lock down for production.
