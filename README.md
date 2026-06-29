# DIGIDELSOLUTIONS RESUME PARSER API

## Quick Start

### Run with Docker (Recommended)
```bash
docker-compose up --build
```

App will be available at: http://localhost:8000

### Run Locally (Python)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info & endpoint list |
| `/health` | GET | Health check |
| `/parse` | POST | Parse a resume file (upload) |
| `/filter` | POST | Apply filter to a parsed profile |
| `/pipeline` | POST | Full pipeline: upload + parse + filter |
| `/batch` | POST | Process multiple resumes |
| `/stats` | GET | Pipeline statistics |
| `/results` | GET | Get processed results |
| `/dashboard` | GET | Web UI (HTML) |

### Dashboard
Open http://localhost:8000/dashboard in your browser to use the web UI.

### Deploy to Render
1. Push code to GitHub
2. Connect repo to Render
3. Use `render.yaml` for blueprint deployment
4. App auto-deploys on every push

