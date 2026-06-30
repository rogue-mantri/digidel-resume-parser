from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import shutil
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

# Core pipeline modules
from core.extractor import ResumeExtractor
from core.structured_parser import StructuredParser
from core.filter_engine import FilterEngine
from matching.job_matcher import JobMatcher, BatchMatcher
from connector.erpnext import ConnectorFactory

# Routers
from routers.interview import router as interview_router

# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="DIGIDEL Hiring Agent",
    description=("Automated resume parsing, job matching, and first-pass filtering for the DIGIDEL hiring ecosystem. "
                 "NEW: Live interview scoring tool at /interview"),
    version="2.1.0",
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

# In-memory storage (replace with DB in production)
processed_resumes = []
session_stats = {"total_processed": 0, "passed": 0, "rejected": 0, "yellow_flags": 0}
job_descriptions = {}  # Cache for fetched JDs

# ============================================================
# Health & Info
# ============================================================

@app.get("/")
def read_root():
    return {
        "status": "running",
        "service": "DIGIDEL Hiring Agent",
        "version": "2.1.0",
        "crm_mode": os.environ.get("CRM_MODE", "standalone"),
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
            "interview": "/interview (HTML UI - NEW)",
            "interview_roles": "/interview/roles (GET)",
            "interview_sessions": "/interview/sessions (POST/GET)",
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
def full_pipeline(
    file: UploadFile = File(...),
    role: str = Form("react_developer"),
    job_id: Optional[str] = Form(None),
    candidate_name: Optional[str] = Form(None),
    candidate_email: Optional[str] = Form(None),
):
    """Full pipeline: upload → extract → parse → filter → match to job."""
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
            # Try to find a job by role keyword
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

        processed_resumes.append(result)
        session_stats['total_processed'] += 1
        if filter_result['decision'] == 'PASS':
            session_stats['passed'] += 1
        elif filter_result['decision'] == 'REJECT':
            session_stats['rejected'] += 1
        else:
            session_stats['yellow_flags'] += 1

        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/batch")
def batch_pipeline(files: List[UploadFile] = File(...), role: str = Form("react_developer"), job_id: Optional[str] = Form(None)):
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
                # Match against best fitting job
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

            results.append(result)
            processed_resumes.append(result)
            session_stats['total_processed'] += 1
            if filter_result['decision'] == 'PASS':
                session_stats['passed'] += 1
            elif filter_result['decision'] == 'REJECT':
                session_stats['rejected'] += 1
            else:
                session_stats['yellow_flags'] += 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return {"success": True, "total_files": len(files), "processed": len([r for r in results if r.get('success')]), "failed": len([r for r in results if not r.get('success')]), "results": results}


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
):
    """Create a job description manually (standalone mode)."""
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
def list_jobs():
    """List all cached job descriptions."""
    return {"success": True, "count": len(job_descriptions), "jobs": list(job_descriptions.values())}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_descriptions.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return {"success": True, "job": job}


# ============================================================
# Stats & Results
# ============================================================

@app.get("/stats")
def get_stats():
    return {
        "session_stats": session_stats,
        "total_in_session": len(processed_resumes),
        "pass_rate": round(session_stats['passed'] / max(session_stats['total_processed'], 1) * 100, 2),
        "cached_jobs": len(job_descriptions),
    }

@app.get("/results")
def get_results(decision: Optional[str] = Query(None, enum=["PASS", "REJECT", "YELLOW_FLAG"]), limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    results = processed_resumes
    if decision:
        results = [r for r in results if r.get('filter', {}).get('decision') == decision]
    total = len(results)
    paginated = results[offset:offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "results": paginated}

@app.delete("/results")
def clear_results():
    processed_resumes.clear()
    session_stats.update({"total_processed": 0, "passed": 0, "rejected": 0, "yellow_flags": 0})
    job_descriptions.clear()
    return {"success": True, "message": "All results cleared"}


# ============================================================
# Dashboard (HTML UI)
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=open(Path(__file__).parent / "static" / "dashboard.html").read())


# ============================================================
# Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# ============================================================
