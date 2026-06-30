import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Form, Body
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime
from typing import Optional, Dict, Any, List

router = APIRouter(prefix="/interview", tags=["interview"])

# ── Load interview matrices ────────────────────────────────────────────

CONFIG_DIR = Path(__file__).parent.parent / "core" / "config"
MATRIX_PATH = CONFIG_DIR / "interview_matrices.json"

# Fallback: if not found, check from env or use built-in
if MATRIX_PATH.exists():
    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        INTERVIEW_DATA = json.load(f)
else:
    INTERVIEW_DATA = {"roles": {}}  # empty fallback, populated later

# In-memory storage for interview sessions
interview_sessions: Dict[str, Dict[str, Any]] = {}


def get_matrix(role_key: str) -> dict:
    role = INTERVIEW_DATA.get("roles", {}).get(role_key)
    if not role:
        raise HTTPException(404, f"Role '{role_key}' not found. Available: {list(available_roles().keys())}")
    return role


def available_roles() -> dict:
    return {
        k: {
            "title": v["title"],
            "department": v["department"],
            "level": v["level"],
            "sections_count": len(v["sections"]),
            "total_questions": sum(len(s["questions"]) for s in v["sections"]),
        }
        for k, v in INTERVIEW_DATA.get("roles", {}).items()
    }


# ── API Endpoints ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def interview_ui():
    """Serve the live interview scoring UI."""
    html_path = Path(__file__).parent.parent / "static" / "interview.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Interview UI not found</h1>", status_code=404)


@router.get("/roles")
def list_roles():
    """List available interview roles with metadata."""
    return {"success": True, "roles": available_roles()}


@router.get("/roles/{role_key}")
def get_role_matrix(role_key: str):
    """Get full interview matrix for a role."""
    role = get_matrix(role_key)
    return {"success": True, "role": role}


@router.get("/roles/{role_key}/flat")
def get_flat_questions(role_key: str):
    """Get flattened question list for a role (easier for UI)."""
    role = get_matrix(role_key)
    flat = []
    for section in role["sections"]:
        for q in section["questions"]:
            flat.append({
                "section_id": section["id"],
                "section_title": section["title"],
                "section_weight": section["weight"],
                "question_id": q["id"],
                "question_text": q["text"],
                "difficulty": q.get("difficulty", "Medium"),
                "good": q.get("good", ""),
                "great": q.get("great", ""),
                "red_flag": q.get("red_flag", ""),
                "follow_up": q.get("follow_up", ""),
            })
    return {"success": True, "role": role_key, "title": role["title"], "questions": flat}


@router.post("/sessions")
def create_session(
    role_key: str = Form(...),
    candidate_name: str = Form(...),
    candidate_email: Optional[str] = Form(None),
    interviewer: Optional[str] = Form(None),
    job_id: Optional[str] = Form(None),
):
    """Create a new interview scoring session."""
    role = get_matrix(role_key)
    session_id = f"{role_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{candidate_name.replace(' ', '_').lower()[:20]}"

    interview_sessions[session_id] = {
        "session_id": session_id,
        "role_key": role_key,
        "role_title": role["title"],
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "interviewer": interviewer,
        "job_id": job_id,
        "created_at": datetime.now().isoformat(),
        "scores": {},
        "notes": {},
        "status": "in_progress",
    }
    return {"success": True, "session_id": session_id, "message": "Session created"}


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get a session with its scores."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return {"success": True, "session": interview_sessions[session_id]}


@router.post("/sessions/{session_id}/scores")
def submit_score(
    session_id: str,
    question_id: str = Form(...),
    score: float = Form(..., ge=0, le=10),
    notes: Optional[str] = Form(None),
):
    """Submit a score for a specific question."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")

    if not 0 <= score <= 10:
        raise HTTPException(400, "Score must be between 0 and 10")

    interview_sessions[session_id]["scores"][question_id] = score
    if notes:
        interview_sessions[session_id]["notes"][question_id] = notes

    return {"success": True, "question_id": question_id, "score": score}


@router.post("/sessions/{session_id}/scores/batch")
def submit_batch_scores(
    session_id: str,
    scores: Dict[str, float] = Body(...),
):
    """Submit multiple scores at once."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")

    for qid, score in scores.items():
        if not 0 <= score <= 10:
            raise HTTPException(400, f"Score for {qid} must be between 0 and 10")
        interview_sessions[session_id]["scores"][qid] = score

    return {"success": True, "updated_count": len(scores)}


@router.get("/sessions/{session_id}/calculate")
def calculate_scores(session_id: str):
    """Calculate weighted scores and recommendation."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")

    session = interview_sessions[session_id]
    role_key = session["role_key"]
    role = get_matrix(role_key)
    scores = session["scores"]

    # Calculate per-section scores
    section_results = []
    total_weighted = 0
    total_weight = 0

    for section in role["sections"]:
        section_questions = section["questions"]
        section_scores = []
        for q in section_questions:
            q_score = scores.get(q["id"])
            if q_score is not None:
                section_scores.append(q_score)

        if section_scores:
            section_avg = sum(section_scores) / len(section_scores)
            section_weight = section["weight"]
            weighted = section_avg * (section_weight / 100)
            total_weighted += weighted
            total_weight += section_weight
        else:
            section_avg = None
            weighted = None

        section_results.append({
            "section_id": section["id"],
            "section_title": section["title"],
            "weight": section["weight"],
            "questions_count": len(section_questions),
            "answered": len(section_scores),
            "section_avg": round(section_avg, 2) if section_avg is not None else None,
            "weighted_score": round(weighted, 2) if weighted is not None else None,
            "scores": {q["id"]: scores.get(q["id"]) for q in section_questions},
        })

    # Overall score (0-100)
    overall_score = round(total_weighted, 2) if total_weight > 0 else 0

    # Recommendation based on thresholds
    scoring = role.get("scoring", {})
    if overall_score >= scoring.get("exceptional", 85):
        recommendation = "EXCEPTIONAL HIRE"
        recommendation_class = "exceptional"
    elif overall_score >= scoring.get("strong", 70):
        recommendation = "STRONG HIRE"
        recommendation_class = "strong"
    elif overall_score >= scoring.get("adequate", 55):
        recommendation = "ADEQUATE — CONSIDER WITH CAUTION"
        recommendation_class = "adequate"
    elif overall_score >= scoring.get("risky", 40):
        recommendation = "RISKY — NEEDS DEEP REVIEW"
        recommendation_class = "risky"
    else:
        recommendation = "REJECT"
        recommendation_class = "reject"

    # Progress
    total_questions = sum(len(s["questions"]) for s in role["sections"])
    answered = len(scores)
    progress = round(answered / total_questions * 100, 1) if total_questions > 0 else 0

    result = {
        "success": True,
        "session_id": session_id,
        "candidate_name": session["candidate_name"],
        "role": role["title"],
        "progress": {"answered": answered, "total": total_questions, "percent": progress},
        "sections": section_results,
        "overall_score": overall_score,
        "total_weight": total_weight,
        "recommendation": recommendation,
        "recommendation_class": recommendation_class,
        "scoring_thresholds": scoring,
        "scored_at": datetime.now().isoformat(),
    }

    # Store the result back in the session
    session["calculated_result"] = result
    session["status"] = "completed" if answered == total_questions else "in_progress"

    return result


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, final_notes: Optional[str] = Form(None)):
    """Mark session as complete with final notes."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")

    session = interview_sessions[session_id]
    session["status"] = "completed"
    session["completed_at"] = datetime.now().isoformat()
    if final_notes:
        session["final_notes"] = final_notes

    # Ensure calculation is done
    if "calculated_result" not in session:
        return calculate_scores(session_id)

    return {"success": True, "session": session}


@router.get("/sessions")
def list_sessions(
    role_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List all interview sessions."""
    sessions = list(interview_sessions.values())
    if role_key:
        sessions = [s for s in sessions if s["role_key"] == role_key]
    if status:
        sessions = [s for s in sessions if s["status"] == status]

    sessions = sorted(sessions, key=lambda x: x["created_at"], reverse=True)
    total = len(sessions)
    paginated = sessions[offset:offset + limit]

    return {"total": total, "offset": offset, "limit": limit, "sessions": paginated}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete an interview session."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")
    del interview_sessions[session_id]
    return {"success": True, "message": "Session deleted"}


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str, format: str = "json"):
    """Export session results as JSON."""
    if session_id not in interview_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found")

    session = interview_sessions[session_id]

    if format == "json":
        return JSONResponse(content={"success": True, "session": session})

    # CSV export (for future)
    return JSONResponse(content={"success": False, "error": "Format not supported yet"})
