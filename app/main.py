from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import shutil
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

# Core pipeline modules
from core.extractor import ResumeExtractor
from core.structured_parser import StructuredParser
from core.filter_engine import FilterEngine
from matching.job_matcher import JobMatcher, BatchMatcher
from connector.erpnext import ConnectorFactory

# Database
from db.database import engine, Base, get_db
from db.models import ProcessedResume, JobDescription, SessionStat

# Email service
from services.email_service import email_service

# Routers
from routers.interview import router as interview_router

# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="DIGIDEL Hiring Agent",
    description=("Automated resume parsing, job matching, and first-pass filtering for the DIGIDEL hiring ecosystem. "
                 "NEW: Live interview scoring tool at /interview. NEW: PostgreSQL persistence + email notifications."),
    version="2.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include interview router
app.include_router(interview_router)

# ── Create tables on startup ───────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables ensured.")

# In-memory cache (still used for quick access, DB is source of truth)
job_descriptions = {}  # Cache for fetched JDs

# ============================================================
# Health & Info
# ============================================================

@app.get("/")
def read_root():
    return {
        "status": "running",
        "service": "DIGIDEL Hiring Agent",
        "version": "2.2.0",
        "crm_mode": os.environ.get("CRM_MODE", "standalone"),
        "database": os.environ.get("DATABASE_URL", "sqlite")[:20] + "...",
        "email_enabled": email_service.enabled,
        "endpoints": {
            "health": "/health",
            "crm_health": "/crm/health",
            "jobs": "/crm/jobs (GET)",
            "job_match": "/match (POST)",
            "parse": "/parse (POST, upload file)",
            "pipeline": "/pipeline (POST, upload file)",
            "batch": "/batch (POST, upload multiple files)",
            "stats": "/stats",
            "results": "/results",
            "dashboard": "/dashboard (HTML UI)",
            "interview": "/interview (HTML UI)",
            "interview_roles": "/interview/roles (GET)",
            "interview_sessions": "/interview/sessions (POST/GET)",
            "email_summary": "/email/interview-summary (POST)",
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============================================================
# CRM Integration Endpoints
# ============================================================

@app.get("/crm/health")
def crm_health():
    """Check CRM connectivity."""
    try:
        connector = ConnectorFactory.from_env()
        return connector.health_check()
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/crm/jobs")
def get_crm_jobs(status: Optional[str] = Query("Open")):
    """Fetch job openings from the connected CRM."""
    try:
        connector = ConnectorFactory.from_env()
        jobs = connector.get_job_openings(status=status)
        # Cache them
        for job in jobs:
            job_id = job.get("name", job.get("id", ""))
            if job_id:
                job_descriptions[job_id] = job
        return {"success": True, "count": len(jobs), "jobs": jobs}
    except Exception as e:
        raise HTTPException(500, f"CRM fetch failed: {str(e)}")

@app.get("/crm/applicants")
def get_crm_applicants(job_id: Optional[str] = Query(None)):
    """Fetch applicants from the connected CRM."""
    try:
        connector = ConnectorFactory.from_env()
        applicants = connector.get_job_applicants(job_opening=job_id)
        return {"success": True, "count": len(applicants), "applicants": applicants}
    except Exception as e:
        raise HTTPException(500, f"CRM fetch failed: {str(e)}")

@app.post("/crm/sync-jobs")
def sync_jobs(background_tasks: BackgroundTasks):
    """Sync job openings from CRM into local cache."""
    background_tasks.add_task(_sync_jobs_task)
    return {"success": True, "message": "Job sync started in background"}

def _sync_jobs_task():
    try:
        connector = ConnectorFactory.from_env()
        jobs = connector.get_job_openings()
        for job in jobs:
            jid = job.get("name", job.get("id", ""))
            if jid:
                job_descriptions[jid] = job
    except Exception as e:
        print(f"Background sync failed: {e}")

# ============================================================
# Core Pipeline Endpoints (Standalone)
# ============================================================

@app.post("/parse")
def parse_resume(file: UploadFile = File(...)):
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        extractor = ResumeExtractor()
        extraction = extractor.extract(tmp_path)
        if not extraction['success']:
            raise HTTPException(400, f"Extraction failed: {extraction.get('error', 'Unknown')}")

        parser = StructuredParser()
        profile = parser.parse(extraction['text'], file.filename)

        return {
            "success": True,
            "file_name": file.filename,
            "file_size": extraction['file_size'],
            "format": extraction['format'],
            "text_length": len(extraction['text']),
            "profile": profile,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    role: str = Form("react_developer"),
    job_id: Optional[str] = Form(None),
    candidate_name: Optional[str] = Form(None),
    candidate_email: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Full pipeline: upload → extract → parse → filter → match to job → persist → notify."""
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Stage 1: Extract
        extractor = ResumeExtractor()
        extraction = extractor.extract(tmp_path)
        if not extraction['success']:
            return JSONResponse(status_code=400, content={"success": False, "stage": "extraction", "error": extraction.get('error', 'Unknown')})

        # Stage 2: Parse
        parser = StructuredParser()
        profile = parser.parse(extraction['text'], file.filename)
        profile['applied_for'] = job_id or role
        profile['source'] = 'web_upload'
        if candidate_name: profile['full_name'] = candidate_name
        if candidate_email: profile['email'] = candidate_email

        # Stage 3: Filter
        filter_engine = FilterEngine(role=role)
        filter_result = filter_engine.evaluate(profile, extraction['text'])

        # Stage 4: Job Match (if job_id provided or cached)
        match_result = None
        target_job = job_descriptions.get(job_id) if job_id else None
        if not target_job:
            for jid, job in job_descriptions.items():
                if role.replace("_", " ") in job.get("job_title", "").lower():
                    target_job = job
                    break
        if target_job:
            matcher = JobMatcher()
            match_result = matcher.match(profile, target_job)

        # Build result
        result = {
            "success": True,
            "file_name": file.filename,
            "format": extraction['format'],
            "file_size": extraction['file_size'],
            "text_length": len(extraction['text']),
            "parse_confidence": profile.get('parse_confidence', 0),
            "profile": {
                "name": profile.get('full_name'),
                "email": profile.get('email'),
                "phone": profile.get('phone'),
                "location": profile.get('location'),
                "experience_years": profile.get('years_experience'),
                "current_title": profile.get('current_title'),
                "skills": profile.get('skills', {}),
                "skills_count": profile.get('skills_count', 0),
                "education": profile.get('education', {}),
                "keywords": profile.get('keywords', []),
                "links": profile.get('links', {}),
            },
            "filter": {
                "role": role,
                "decision": filter_result['decision'],
                "confidence": filter_result['confidence'],
                "summary": filter_result['summary'],
                "failed_rules": filter_result['failed_rules'],
                "yellow_flags": filter_result['yellow_flags'],
            },
            "match": match_result,
            "processed_at": datetime.now().isoformat(),
        }

        # Stage 5: Persist to DB
        db_record = ProcessedResume(
            file_name=file.filename,
            format=extraction['format'],
            file_size=extraction['file_size'],
            text_length=len(extraction['text']),
            parse_confidence=profile.get('parse_confidence', 0),
            profile_json=result["profile"],
            filter_decision=filter_result['decision'],
            filter_confidence=filter_result['confidence'],
            filter_summary=filter_result['summary'],
            failed_rules=filter_result['failed_rules'],
            yellow_flags=filter_result['yellow_flags'],
            match_json=match_result,
        )
        db.add(db_record)
        db.commit()

        # Stage 6: Email notification (fire and forget for non-blocking)
        if email_service.enabled and filter_result['decision'] in ['PASS', 'YELLOW_FLAG']:
            try:
                await email_service.send_new_candidate_alert(result)
            except Exception as e:
                print(f"[Email] Failed to send alert: {e}")

        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/batch")
async def batch_pipeline(
    files: List[UploadFile] = File(...),
    role: str = Form("react_developer"),
    job_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    results = []
    target_job = job_descriptions.get(job_id) if job_id else None

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in {'.pdf', '.docx', '.doc', '.txt', '.rtf'}:
            results.append({"file_name": file.filename, "success": False, "error": f"Unsupported file type: {ext}"})
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        try:
            extractor = ResumeExtractor()
            extraction = extractor.extract(tmp_path)
            if not extraction['success']:
                results.append({"file_name": file.filename, "success": False, "error": extraction.get('error', 'Unknown')})
                continue

            parser = StructuredParser()
            profile = parser.parse(extraction['text'], file.filename)

            filter_engine = FilterEngine(role=role)
            filter_result = filter_engine.evaluate(profile, extraction['text'])

            match_result = None
            if target_job:
                matcher = JobMatcher()
                match_result = matcher.match(profile, target_job)
            elif job_descriptions:
                bm = BatchMatcher()
                matches = bm.match_candidate_to_jobs(profile, list(job_descriptions.values()))
                if matches:
                    match_result = matches[0]

            result = {
                "file_name": file.filename,
                "success": True,
                "format": extraction['format'],
                "profile": {
                    "name": profile.get('full_name'),
                    "email": profile.get('email'),
                    "experience_years": profile.get('years_experience'),
                    "skills_count": profile.get('skills_count', 0),
                },
                "filter": {
                    "decision": filter_result['decision'],
                    "confidence": filter_result['confidence'],
                    "summary": filter_result['summary'],
                },
                "match": match_result,
                "processed_at": datetime.now().isoformat(),
            }

            # Persist to DB
            db_record = ProcessedResume(
                file_name=file.filename,
                format=extraction['format'],
                file_size=extraction.get('file_size'),
                text_length=len(extraction['text']),
                parse_confidence=profile.get('parse_confidence', 0),
                profile_json=result["profile"],
                filter_decision=filter_result['decision'],
                filter_confidence=filter_result['confidence'],
                filter_summary=filter_result['summary'],
                match_json=match_result,
            )
            db.add(db_record)

            results.append(result)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    db.commit()

    # Send email for passed candidates
    if email_service.enabled:
        for r in results:
            if r.get('success') and r.get('filter', {}).get('decision') in ['PASS', 'YELLOW_FLAG']:
                try:
                    await email_service.send_new_candidate_alert(r)
                except Exception as e:
                    print(f"[Email] Batch alert failed: {e}")

    return {
        "success": True,
        "total_files": len(files),
        "processed": len([r for r in results if r.get('success')]),
        "failed": len([r for r in results if not r.get('success')]),
        "results": results,
    }


# ============================================================
# Job Matching Endpoints
# ============================================================

@app.post("/match")
def match_candidate_to_job(profile: Dict, job_id: str = Query(...)):
    """Match a parsed candidate profile against a specific job."""
    job = job_descriptions.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found. Sync jobs first via /crm/jobs")

    matcher = JobMatcher()
    result = matcher.match(profile, job)
    return {"success": True, "job_id": job_id, "job_title": job.get("job_title", ""), **result}


@app.post("/match/bulk")
def match_bulk_candidates(profiles: List[Dict], job_id: str = Query(...)):
    """Match multiple candidates against a specific job and rank them."""
    job = job_descriptions.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found. Sync jobs first via /crm/jobs")

    bm = BatchMatcher()
    ranked = bm.get_best_matches_for_job(profiles, job, top_n=100)
    return {"success": True, "job_id": job_id, "job_title": job.get("job_title", ""), "candidates": ranked}


@app.post("/jobs/create")
def create_job_standalone(
    job_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    required_skills: str = Form(...),  # comma-separated
    min_experience: float = Form(0),
    max_experience: float = Form(99),
    department: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    salary_min: Optional[float] = Form(None),
    salary_max: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    """Create a job description manually (standalone mode)."""
    # Also persist to DB
    db_job = JobDescription(
        job_id=job_id,
        job_title=title,
        description=description,
        required_skills=[s.strip() for s in required_skills.split(",")],
        min_experience=min_experience,
        max_experience=max_experience,
        department=department,
        location=location,
        salary_min=salary_min,
        salary_max=salary_max,
        source="standalone",
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Update in-memory cache
    job = {
        "name": job_id,
        "job_title": title,
        "description": description,
        "required_skills": [s.strip() for s in required_skills.split(",")],
        "min_experience": min_experience,
        "max_experience": max_experience,
        "department": department,
        "location": location,
        "salary_range": {"min": salary_min, "max": salary_max} if salary_min and salary_max else None,
        "source": "standalone",
        "created_at": datetime.now().isoformat(),
    }
    job_descriptions[job_id] = job

    # Also save to disk if standalone
    if os.environ.get("CRM_MODE", "standalone").lower() == "standalone":
        from connector.erpnext import StandaloneConnector
        conn = StandaloneConnector()
        conn.save_job(job_id, title, description, job["required_skills"], **{k: v for k, v in job.items() if k not in ["name", "job_title", "description", "required_skills"]})

    return {"success": True, "job": job}


@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    """List all job descriptions (from DB, with cache fallback)."""
    db_jobs = db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()
    jobs = []
    for j in db_jobs:
        jobs.append({
            "name": j.job_id,
            "job_title": j.job_title,
            "description": j.description,
            "required_skills": j.required_skills or [],
            "min_experience": float(j.min_experience) if j.min_experience else 0,
            "max_experience": float(j.max_experience) if j.max_experience else 99,
            "department": j.department,
            "location": j.location,
            "salary_range": {"min": float(j.salary_min), "max": float(j.salary_max)} if j.salary_min and j.salary_max else None,
            "source": j.source,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        })
    return {"success": True, "count": len(jobs), "jobs": jobs}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(JobDescription).filter(JobDescription.job_id == job_id).first()
    if job:
        return {"success": True, "job": {
            "name": job.job_id,
            "job_title": job.job_title,
            "description": job.description,
            "required_skills": job.required_skills or [],
            "min_experience": float(job.min_experience) if job.min_experience else 0,
            "max_experience": float(job.max_experience) if job.max_experience else 99,
            "department": job.department,
            "location": job.location,
            "salary_range": {"min": float(job.salary_min), "max": float(job.salary_max)} if job.salary_min and j.salary_max else None,
            "source": job.source,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }}
    # Fallback to in-memory
    if job_id in job_descriptions:
        return {"success": True, "job": job_descriptions[job_id]}
    raise HTTPException(404, f"Job {job_id} not found")


# ============================================================
# Stats & Results (from DB)
# ============================================================

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(ProcessedResume).count()
    passed = db.query(ProcessedResume).filter(ProcessedResume.filter_decision == "PASS").count()
    rejected = db.query(ProcessedResume).filter(ProcessedResume.filter_decision == "REJECT").count()
    yellow = db.query(ProcessedResume).filter(ProcessedResume.filter_decision == "YELLOW_FLAG").count()
    pass_rate = round(passed / max(total, 1) * 100, 2)
    return {
        "session_stats": {
            "total_processed": total,
            "passed": passed,
            "rejected": rejected,
            "yellow_flags": yellow,
        },
        "total_in_session": total,
        "pass_rate": pass_rate,
        "cached_jobs": db.query(JobDescription).count(),
    }

@app.get("/results")
def get_results(
    decision: Optional[str] = Query(None, enum=["PASS", "REJECT", "YELLOW_FLAG"]),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ProcessedResume)
    if decision:
        query = query.filter(ProcessedResume.filter_decision == decision)
    total = query.count()
    records = query.order_by(ProcessedResume.processed_at.desc()).offset(offset).limit(limit).all()

    results = []
    for r in records:
        results.append({
            "file_name": r.file_name,
            "format": r.format,
            "file_size": r.file_size,
            "text_length": r.text_length,
            "parse_confidence": float(r.parse_confidence) if r.parse_confidence else None,
            "profile": r.profile_json,
            "filter": {
                "decision": r.filter_decision,
                "confidence": float(r.filter_confidence) if r.filter_confidence else None,
                "summary": r.filter_summary,
                "failed_rules": r.failed_rules,
                "yellow_flags": r.yellow_flags,
            },
            "match": r.match_json,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        })

    return {"total": total, "offset": offset, "limit": limit, "results": results}

@app.delete("/results")
def clear_results(db: Session = Depends(get_db)):
    db.query(ProcessedResume).delete()
    db.commit()
    return {"success": True, "message": "All results cleared"}


# ============================================================
# Email Endpoints
# ============================================================

@app.post("/email/interview-summary")
async def email_interview_summary(
    session_id: str = Form(...),
    to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Send interview summary via email."""
    from db.models import InterviewSession as ISession
    db_session = db.query(ISession).filter(ISession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    # Build session dict for email template
    scores = db.query(db.models.InterviewScore).filter(db.models.InterviewScore.session_id == db_session.id).all()
    score_map = {s.question_id: float(s.score) for s in scores}
    notes_map = {s.question_id: s.notes for s in scores if s.notes}

    session_dict = {
        "session_id": db_session.session_id,
        "candidate_name": db_session.candidate_name,
        "role_title": db_session.role_title,
        "interviewer": db_session.interviewer,
        "completed_at": db_session.completed_at.isoformat() if db_session.completed_at else None,
        "final_notes": db_session.final_notes,
        "calculated_result": {
            "overall_score": float(db_session.overall_score) if db_session.overall_score else 0,
            "recommendation": db_session.recommendation or "N/A",
            "recommendation_class": db_session.recommendation_class or "",
            "sections": [],
        },
    }

    recipients = [to] if to else None
    result = await email_service.send_interview_summary(session_dict, to=recipients)
    return {"success": result.get("success"), "email_result": result}


# ============================================================
# Dashboard (HTML UI)
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=open(Path(__file__).parent / "static" / "dashboard.html").read())


# ============================================================
# Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# ============================================================
