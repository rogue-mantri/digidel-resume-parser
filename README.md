# DIGIDEL Hiring Agent

> **Automated resume parsing, job description matching, and first-pass filtering for the DIGIDEL hiring ecosystem.**
>
> Integrates with **Twenty CRM** and **ERPNext** (Frappe) or runs standalone.

---

## What This Agent Does

The DIGIDEL Hiring Agent is a custom-built FastAPI application that acts as an intelligent layer on top of your existing hiring workflow. It connects to your CRM/ERP, fetches job descriptions and uploaded resumes, parses them with NLP heuristics, scores candidates against open roles, and presents a unified dashboard for your HR team.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Resume Parsing** | Extracts structured data (name, email, skills, experience, education) from PDF, DOCX, TXT, RTF |
| **Job Matching** | Matches parsed candidates against job descriptions with weighted scoring (skills, experience, title, AI bonus) |
| **First-Pass Filter** | Rule-based engine: PASS, REJECT, or YELLOW_FLAG based on universal + role-specific rules |
| **CRM Integration** | Auto-fetches job descriptions and candidates from **ERPNext** or **Twenty CRM** via API |
| **Standalone Mode** | Works without any CRM — upload job descriptions and resumes manually via the dashboard |
| **Batch Processing** | Process 10, 50, or 500 resumes in one upload |
| **Web Dashboard** | Dark-themed HTML UI for non-technical HR users — drag, drop, evaluate |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DIGIDEL Hiring Agent                      │
│                      (FastAPI + Uvicorn)                     │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│  Connector  │   Core Pipe   │   Matching   │   Dashboard     │
│             │               │              │                 │
│ ERPNext API │  Extractor    │ JobMatcher   │  HTML/JS UI     │
│ Twenty API  │  Parser       │ BatchMatcher │  (no build)     │
│ Standalone  │  FilterEngine │              │                 │
└─────────────┴──────────────┴──────────────┴─────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    [ERPNext/     [PDF/DOCX]    [Job Desc]     [HR Browser]
     Twenty]       [TXT/RTF]    [Candidate]    [Mobile/Desktop]
```

### Connector Layer

The agent can switch between three modes via environment variables:

- **`standalone`** (default): Local file storage for jobs and resumes. No external CRM needed.
- **`erpnext`**: Connects to ERPNext/Frappe via REST API (`token` auth). Reads Job Openings and Job Applicants. Writes evaluation results back.
- **`twenty`**: Connects to Twenty CRM via GraphQL API. Reads custom job objects and people. Writes evaluation notes.

### Core Pipeline

1. **Extractor** (`core/extractor.py`): Multi-format text extraction (PDF → pypdf, DOCX → python-docx, TXT → multi-encoding, RTF → strip control words)
2. **Structured Parser** (`core/structured_parser.py`): Regex-based NLP extraction of 9 skill categories, education, links, experience, salary, notice period
3. **Filter Engine** (`core/filter_engine.py`): 5 universal rules + 5 role-specific rules. Decisions: PASS, REJECT, YELLOW_FLAG

### Matching Engine

- **Skills Match** (35%): Required vs. bonus skills overlap
- **Experience Match** (20%): Within min/max range
- **Title Relevance** (15%): Current role vs. job title similarity
- **Education Match** (10%): Degree/field alignment
- **Keyword Match** (10%): Resume keyword overlap with JD
- **AI Bonus** (10%): Extra points for AI/LLM/RAG skills

Scoring thresholds: **STRONG_MATCH** (85+), **GOOD_MATCH** (70–84), **POTENTIAL_MATCH** (55–69), **NEEDS_REVIEW** (40–54), **NOT_A_MATCH** (<40)

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DIGIDEL-SOLUTIONS/digidel-hiring-agent.git
cd digidel-hiring-agent
pip install -r requirements.txt
```

### 2. Run Standalone (No CRM Needed)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard)

### 3. Run with Docker

```bash
docker-compose up --build
```

### 4. Connect to Your CRM

Create a `.env` file:

```bash
# ERPNext mode
CRM_MODE=erpnext
ERPNEXT_URL=https://your-erpnext-instance.com
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# OR Twenty mode
CRM_MODE=twenty
TWENTY_URL=https://your-twenty-instance.com
TWENTY_API_KEY=your_api_key
```

Then start the agent. It will auto-fetch job descriptions and candidates on first load.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent info & endpoint list |
| `/health` | GET | Health check |
| `/crm/health` | GET | CRM connectivity status |
| `/crm/jobs` | GET | Fetch job openings from CRM |
| `/crm/applicants` | GET | Fetch applicants from CRM |
| `/crm/sync-jobs` | POST | Background sync of job descriptions |
| `/parse` | POST | Parse a single resume file |
| `/pipeline` | POST | Full pipeline: parse + filter + match |
| `/batch` | POST | Process multiple resumes |
| `/match` | POST | Match a profile against a specific job |
| `/match/bulk` | POST | Rank candidates against a job |
| `/jobs` | GET | List cached job descriptions |
| `/jobs/{id}` | GET | Get a specific job |
| `/jobs/create` | POST | Add a job manually (standalone) |
| `/stats` | GET | Pipeline statistics |
| `/results` | GET | Get processed results with filtering |
| `/dashboard` | GET | Web UI |

---

## Deployment

### Render (Free Tier)

1. Push code to GitHub (`DIGIDEL-SOLUTIONS/digidel-hiring-agent`)
2. Go to [dashboard.render.com](https://dashboard.render.com) → New → Blueprint
3. Connect the repo. Render reads `render.yaml` and auto-deploys.

### Self-Hosted / VPS

```bash
docker build -t digidel-hiring-agent .
docker run -d -p 8000:8000 --env-file .env digidel-hiring-agent
```

### Environment Variables

| Variable | Required For | Description |
|----------|--------------|-------------|
| `CRM_MODE` | All | `standalone`, `erpnext`, or `twenty` |
| `PORT` | All | Server port (Render auto-sets this) |
| `ERPNEXT_URL` | ERPNext | Your ERPNext base URL |
| `ERPNEXT_API_KEY` | ERPNext | API Key from ERPNext user settings |
| `ERPNEXT_API_SECRET` | ERPNext | API Secret from ERPNext user settings |
| `TWENTY_URL` | Twenty | Your Twenty CRM base URL |
| `TWENTY_API_KEY` | Twenty | API Key from Twenty settings |
| `DATA_DIR` | Standalone | Local storage path (default: `./data`) |

---

## Integrating with Your Existing Stack

### ERPNext / Frappe Hiring Module

The agent reads from the standard `Job Opening` and `Job Applicant` DocTypes. To write results back:

1. **Option A**: The agent updates `Job Applicant.status` and `applicant_rating` directly.
2. **Option B**: Create a custom `Resume Evaluation` DocType and the agent will post evaluation records there.

### Twenty CRM

The agent expects job openings as custom objects (name: `jobOpenings`). It reads `Person` records as candidates and writes evaluation results as `Notes` on the person.

### Custom Integration

If you have a custom API, extend the `ConnectorFactory` in `app/connector/erpnext.py` or add a new module in `app/connector/`. The connector just needs to implement:

- `get_job_openings()` → List[Dict]
- `get_job_applicants()` → List[Dict]
- `get_file_attachment(url)` → bytes
- `health_check()` → Dict

---

## Project Structure

```
digidel-hiring-agent/
├── app/
│   ├── main.py                    # FastAPI entry point (all endpoints)
│   ├── static/
│   │   └── dashboard.html         # Web UI (no build step)
│   ├── core/
│   │   ├── extractor.py           # PDF/DOCX/TXT/RTF extraction
│   │   ├── structured_parser.py   # NLP parsing → structured profile
│   │   ├── filter_engine.py        # First-pass filter rules
│   │   ├── pipeline.py            # CLI batch pipeline (optional)
│   │   └── config/roles.json      # Role definitions
│   ├── connector/
│   │   ├── erpnext.py             # ERPNext + Standalone connectors
│   │   └── twenty.py              # Twenty CRM GraphQL connector
│   ├── matching/
│   │   └── job_matcher.py         # Resume-to-JD scoring engine
│   └── test_resumes/              # 4 sample resumes for testing
├── Dockerfile                     # Docker image
├── docker-compose.yml             # Local dev stack
├── render.yaml                    # Render.com blueprint
├── requirements.txt               # Python dependencies
├── README.md                      # This file
└── DEPLOY.md                      # Deployment-specific guide
```

---

## Tested & Verified

All core components have been tested with the provided sample resumes:

| Candidate | Role | Filter Decision | Match Score | Recommendation |
|-----------|------|----------------|-------------|----------------|
| Rahul Sharma | React Developer | **PASS** (100%) | 84.8 | GOOD_MATCH |
| Vikram Patel | React Developer | **PASS** (100%) | — | — |
| Priya Desai | UI/UX Designer | **REJECT** | — | — |
| Amit Kumar | Generic | **REJECT** | — | — |

The matching engine correctly identifies skill matches, missing skills, and AI bonuses. The connector factory auto-falls back to standalone mode if no CRM credentials are configured.

---

## Next Steps

1. **Add me to your CRM**: Share your ERPNext or Twenty instance URL + API credentials so I can configure the connector and test live data fetching.
2. **Train your HR team**: Use the Phase 1 interview matrices and scoring templates (already built) alongside this agent.
3. **Email automation**: Add SMTP/Gmail integration to auto-send shortlisted candidate summaries to hiring managers.
4. **Database persistence**: Swap in-memory storage for PostgreSQL (Supabase) using the D1 schema from Phase 1.

---

## License

Internal use for DIGIDEL SOLUTIONS. Not open-source.

---

**Built by DIGIDEL SOLUTIONS HR Digital Hiring Team**
