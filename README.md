# DIGIDEL Hiring Agent

> **Automated resume parsing, job description matching, first-pass filtering, live interview scoring, and email notifications for the DIGIDEL hiring ecosystem.**
>
> Integrates with **Twenty CRM** and **ERPNext** (Frappe) or runs standalone. Now with **PostgreSQL persistence** and **SMTP email alerts**.

---

## What This Agent Does

The DIGIDEL Hiring Agent is a custom-built FastAPI application that acts as an intelligent layer on top of your existing hiring workflow. It connects to your CRM/ERP, fetches job descriptions and uploaded resumes, parses them with NLP heuristics, scores candidates against open roles, and presents a unified dashboard for your HR team.

**v2.2 adds:**
- **PostgreSQL persistence** — all interview sessions, scores, resumes, and job descriptions persist to a real database (Supabase/Neon)
- **SMTP email automation** — auto-send interview summaries and new candidate alerts to hiring managers
- **Auto table creation** — SQLAlchemy creates tables on app startup (no manual migration needed)

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
| **Live Interview Scoring** | Real-time weighted scoring tool for interviews — score 1-10 per question, auto-calculate recommendations |
| **PostgreSQL Persistence** | All data persists to Supabase/Neon — no data loss on container restarts |
| **Email Notifications** | Auto-send interview summaries + new candidate alerts via SMTP |

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
│ Twenty API  │  Parser       │ BatchMatcher │  Interview Tool │
│ Standalone  │  FilterEngine │              │  Email Service  │
└─────────────┴──────────────┴──────────────┴─────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
    [ERPNext/     [PDF/DOCX]    [Job Desc]     [HR Browser]
     Twenty]       [TXT/RTF]    [Candidate]    [Mobile/Desktop]
                            │
                            ▼
                    [PostgreSQL — Supabase/Neon]
```

### Database Layer (v2.2 — NEW)

All data now persists to PostgreSQL via SQLAlchemy:

| Table | Purpose |
|-------|---------|
| `interview_sessions` | Interview sessions with candidate info, status, scores |
| `interview_scores` | Per-question scores with section weights and notes |
| `job_descriptions` | Job descriptions created via `/jobs/create` or CRM sync |
| `processed_resumes` | Full pipeline results from resume uploads |
| `session_stats` | Aggregated pipeline counters (optional) |

**Auto-creation:** On startup, `Base.metadata.create_all()` creates all tables if they don't exist. No manual migration needed.

### Email Service (v2.2 — NEW)

Configurable via environment variables. Sends two types of emails:

1. **Interview Summary** — sent when a session is completed (`/interview/sessions/{id}/complete`). Includes candidate name, overall score, recommendation, and section breakdown.
2. **New Candidate Alert** — sent automatically when a resume passes the filter (`/pipeline` or `/batch`). Includes candidate name, role, decision, and skills count.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DIGIDEL-SOLUTIONS/digidel-hiring-agent.git
cd digidel-hiring-agent
pip install -r requirements.txt
```

### 2. Set up PostgreSQL (Supabase or Neon)

**Option A: Supabase**
1. Create a new project at [supabase.com](https://supabase.com) (do NOT use your existing company project)
2. Go to **Settings → Database** → copy the connection string
3. Replace `[YOUR-PASSWORD]` with your actual password

```bash
export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres"
```

**Option B: Neon**
1. Create a new project at [neon.tech](https://neon.tech)
2. Copy the connection string from the dashboard

```bash
export DATABASE_URL="postgresql://neondb_owner:YOUR_PASSWORD@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
```

**Option C: Local SQLite (dev only)**
```bash
export DATABASE_URL="sqlite:///./digidel_hiring.db"
```

### 3. Set up SMTP for email (optional)

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="your-email@gmail.com"
export DEFAULT_TO_EMAIL="hiring-manager@digidelsolutions.com"
```

**For Gmail:** Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

**For SendGrid:**
```bash
export SMTP_HOST="smtp.sendgrid.net"
export SMTP_USER="apikey"
export SMTP_PASSWORD="your-sendgrid-api-key"
```

### 4. Run Standalone (No CRM Needed)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000/dashboard](http://localhost:8000/dashboard) for the resume dashboard

Open [http://localhost:8000/interview](http://localhost:8000/interview) for the interview scoring tool

### 5. Run with Docker

```bash
docker-compose up --build
```

### 6. Connect to Your CRM (optional)

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
| `/pipeline` | POST | Full pipeline: parse + filter + match + **persist + email** |
| `/batch` | POST | Process multiple resumes |
| `/match` | POST | Match a profile against a specific job |
| `/match/bulk` | POST | Rank candidates against a job |
| `/jobs` | GET | List cached job descriptions |
| `/jobs/{id}` | GET | Get a specific job |
| `/jobs/create` | POST | Add a job manually (standalone) |
| `/stats` | GET | Pipeline statistics (from DB) |
| `/results` | GET | Get processed results with filtering (from DB) |
| `/dashboard` | GET | Resume dashboard (HTML UI) |
| `/interview` | GET | Interview scoring tool (HTML UI) |
| `/interview/roles` | GET | List available interview roles |
| `/interview/sessions` | POST/GET | Create or list interview sessions |
| `/interview/sessions/{id}/calculate` | GET | Calculate weighted scores |
| `/interview/sessions/{id}/complete` | POST | Mark session complete + **send email** |
| `/email/interview-summary` | POST | Send interview summary via email |

---

## Deployment

### Render (Free Tier)

1. Push code to GitHub (`DIGIDEL-SOLUTIONS/digidel-hiring-agent`)
2. Go to [dashboard.render.com](https://dashboard.render.com) → Your Service → **Environment**
3. Add these environment variables:

| Variable | Value | Required? |
|----------|-------|-----------|
| `DATABASE_URL` | Your Supabase/Neon connection string | **Yes** |
| `SMTP_HOST` | e.g., `smtp.gmail.com` | No |
| `SMTP_PORT` | `587` | No |
| `SMTP_USER` | Your email address | No |
| `SMTP_PASSWORD` | App password or API key | No |
| `FROM_EMAIL` | Sender email | No |
| `DEFAULT_TO_EMAIL` | Default recipient for alerts | No |
| `CRM_MODE` | `standalone`, `erpnext`, or `twenty` | Yes |
| `PORT` | Auto-set by Render | Auto |

4. Go to **Manual Deploy** → **Deploy Latest Commit**
5. Wait for build to complete. Check logs if it fails.

**Live URL:** [https://digidel-hiring-agent.onrender.com](https://digidel-hiring-agent.onrender.com)

### Self-Hosted / VPS

```bash
docker build -t digidel-hiring-agent .
docker run -d -p 8000:8000 \
  -e DATABASE_URL="your-postgres-url" \
  -e SMTP_HOST="smtp.gmail.com" \
  -e SMTP_USER="your-email" \
  -e SMTP_PASSWORD="your-password" \
  -e FROM_EMAIL="your-email" \
  -e DEFAULT_TO_EMAIL="manager@company.com" \
  digidel-hiring-agent
```

---

## Database Schema

The app auto-creates these tables on startup. You can also run the migration SQL manually:

```bash
# Run in psql or Supabase SQL Editor
psql $DATABASE_URL -f migrations/001_init.sql
```

### Tables

```sql
interview_sessions
  id, session_id, role_key, role_title, candidate_name, candidate_email,
  interviewer, job_id, created_at, completed_at, status, final_notes,
  overall_score, recommendation, recommendation_class, total_questions,
  answered_questions, progress_percent

interview_scores
  id, session_id → interview_sessions(id), question_id, section_id,
  section_title, section_weight, score, notes, created_at, updated_at

job_descriptions
  id, job_id, job_title, description, required_skills, min_experience,
  max_experience, department, location, salary_min, salary_max, source, created_at

processed_resumes
  id, file_name, format, file_size, text_length, parse_confidence,
  profile_json, filter_decision, filter_confidence, filter_summary,
  failed_rules, yellow_flags, match_json, processed_at

session_stats
  id, total_processed, passed, rejected, yellow_flags, updated_at
```

---

## Email Templates

### Interview Summary Email

Sent when you complete an interview session. Includes:
- Candidate name, role, interviewer, date
- Large score display with color-coded recommendation
- Section-by-section breakdown table
- Final notes from the interviewer
- Link back to the interview tool

### New Candidate Alert Email

Sent automatically when a resume passes the filter. Includes:
- Candidate name, email, role
- Experience years and skills count
- Filter decision (PASS/YELLOW_FLAG badge)
- Link to the dashboard

---

## Project Structure

```
digidel-hiring-agent/
├── app/
│   ├── main.py                    # FastAPI entry point (all endpoints)
│   ├── routers/
│   │   ├── __init__.py
│   │   └── interview.py           # Interview scoring API routes
│   ├── static/
│   │   ├── dashboard.html         # Resume dashboard UI
│   │   └── interview.html         # Interview scoring UI
│   ├── core/
│   │   ├── extractor.py           # PDF/DOCX/TXT/RTF extraction
│   │   ├── structured_parser.py   # NLP parsing → structured profile
│   │   ├── filter_engine.py        # First-pass filter rules
│   │   ├── pipeline.py            # CLI batch pipeline (optional)
│   │   └── config/
│   │       ├── roles.json         # Role definitions
│   │       └── interview_matrices.json  # Interview questions
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy engine + session factory
│   │   └── models.py              # All ORM models
│   ├── services/
│   │   ├── __init__.py
│   │   └── email_service.py       # SMTP email service with templates
│   ├── connector/
│   │   ├── erpnext.py             # ERPNext + Standalone connectors
│   │   └── twenty.py              # Twenty CRM GraphQL connector
│   ├── matching/
│   │   └── job_matcher.py         # Resume-to-JD scoring engine
│   └── test_resumes/              # 4 sample resumes for testing
├── migrations/
│   └── 001_init.sql               # PostgreSQL migration (optional — auto-create on startup)
├── Dockerfile                     # Docker image
├── docker-compose.yml             # Local dev stack
├── render.yaml                    # Render.com blueprint + env vars
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

**Interview Scoring Tool:** Tested with all 4 role matrices. Real-time weighted calculation and recommendation generation verified.

**Database Persistence:** Verified with PostgreSQL (Supabase) and SQLite. Auto table creation, CRUD operations, and session persistence all tested.

**Email Service:** Tested with Gmail SMTP. Interview summary and candidate alert templates render correctly.

---

## Next Steps

1. **Add me to your CRM**: Share your ERPNext or Twenty instance URL + API credentials so I can configure the connector and test live data fetching.
2. **Train your HR team**: Use the Phase 1 interview matrices and scoring templates alongside this agent. The `/interview` tool replaces manual Excel scorecards.
3. **Fathom AI integration**: Connect to Fathom AI or Google Calendar for transcription → auto-populate interview notes and suggest scores.
4. **Slack/Teams notifications**: Add webhook support for instant team alerts when a candidate passes.

---

## License

Internal use for DIGIDEL SOLUTIONS. Not open-source.

---

**Built by DIGIDEL SOLUTIONS HR Digital Hiring Team**
