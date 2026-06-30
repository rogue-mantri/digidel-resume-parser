import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Form, Body, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import InterviewSession, InterviewScore
from services.email_service import email_service

router = APIRouter(prefix="/interview", tags=["interview"])

# ── Load interview matrices ────────────────────────────────────────────

CONFIG_DIR = Path(__file__).parent.parent / "core" / "config"
MATRIX_PATH = CONFIG_DIR / "interview_matrices.json"

if MATRIX_PATH.exists():
    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        INTERVIEW_DATA = json.load(f)
else:
    INTERVIEW_DATA = {"roles": {}}


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


# ── Helper: Build session dict from DB ─────────────────────────────────

def build_session_dict(session: InterviewSession, include_scores: bool = True) -> dict:
    data = {
        "id": session.id,
        "session_id": session.session_id,
        "role_key": session.role_key,
        "role_title": session.role_title,
        "candidate_name": session.candidate_name,
        "candidate_email": session.candidate_email,
        "interviewer": session.interviewer,
        "job_id": session.job_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "status": session.status,
        "final_notes": session.final_notes,
        "overall_score": float(session.overall_score) if session.overall_score else None,
        "recommendation": session.recommendation,
        "recommendation_class": session.recommendation_class,
        "total_questions": session.total_questions,
        "answered_questions": session.answered_questions,
        "progress_percent": float(session.progress_percent) if session.progress_percent else None,
    }
    if include_scores and session.scores:
        data["scores"] = {
            s.question_id: float(s.score) for s in session.scores
        }
        data["notes"] = {
            s.question_id: s.notes for s in session.scores if s.notes
        }
    return data


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
    db: Session = Depends(get_db),
):
    """Create a new interview scoring session."""
    role = get_matrix(role_key)
    total_questions = sum(len(s["questions"]) for s in role["sections"])
    session_id = f"{role_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{candidate_name.replace(' ', '_').lower()[:20]}"

    db_session = InterviewSession(
        session_id=session_id,
        role_key=role_key,
        role_title=role["title"],
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        interviewer=interviewer,
        job_id=job_id,
        total_questions=total_questions,
        status="in_progress",
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return {"success": True, "session_id": session_id, "db_id": db_session.id, "message": "Session created"}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get a session with its scores."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    return {"success": True, "session": build_session_dict(db_session)}


@router.post("/sessions/{session_id}/scores")
def submit_score(
    session_id: str,
    question_id: str = Form(...),
    score: float = Form(..., ge=0, le=10),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Submit or update a score for a specific question."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    if not 0 <= score <= 10:
        raise HTTPException(400, "Score must be between 0 and 10")

    # Upsert score
    existing = db.query(InterviewScore).filter(
        InterviewScore.session_id == db_session.id,
        InterviewScore.question_id == question_id,
    ).first()

    if existing:
        existing.score = score
        existing.notes = notes
        existing.updated_at = datetime.utcnow()
    else:
        # Find section info from matrices
        role = get_matrix(db_session.role_key)
        section_id = None
        section_title = None
        section_weight = None
        for sec in role["sections"]:
            for q in sec["questions"]:
                if q["id"] == question_id:
                    section_id = sec["id"]
                    section_title = sec["title"]
                    section_weight = sec["weight"]
                    break

        new_score = InterviewScore(
            session_id=db_session.id,
            question_id=question_id,
            section_id=section_id,
            section_title=section_title,
            section_weight=section_weight,
            score=score,
            notes=notes,
        )
        db.add(new_score)

    # Update session progress
    answered_count = db.query(InterviewScore).filter(InterviewScore.session_id == db_session.id).count()
    db_session.answered_questions = answered_count
    if db_session.total_questions > 0:
        db_session.progress_percent = round(answered_count / db_session.total_questions * 100, 1)

    db.commit()
    return {"success": True, "question_id": question_id, "score": score}


@router.post("/sessions/{session_id}/scores/batch")
def submit_batch_scores(
    session_id: str,
    scores: Dict[str, float] = Body(...),
    db: Session = Depends(get_db),
):
    """Submit multiple scores at once."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    role = get_matrix(db_session.role_key)
    section_map = {}
    for sec in role["sections"]:
        for q in sec["questions"]:
            section_map[q["id"]] = (sec["id"], sec["title"], sec["weight"])

    for qid, score in scores.items():
        if not 0 <= score <= 10:
            raise HTTPException(400, f"Score for {qid} must be between 0 and 10")

        existing = db.query(InterviewScore).filter(
            InterviewScore.session_id == db_session.id,
            InterviewScore.question_id == qid,
        ).first()

        if existing:
            existing.score = score
            existing.updated_at = datetime.utcnow()
        else:
            sec_info = section_map.get(qid, (None, None, None))
            db.add(InterviewScore(
                session_id=db_session.id,
                question_id=qid,
                section_id=sec_info[0],
                section_title=sec_info[1],
                section_weight=sec_info[2],
                score=score,
            ))

    answered_count = db.query(InterviewScore).filter(InterviewScore.session_id == db_session.id).count()
    db_session.answered_questions = answered_count
    if db_session.total_questions > 0:
        db_session.progress_percent = round(answered_count / db_session.total_questions * 100, 1)

    db.commit()
    return {"success": True, "updated_count": len(scores)}


@router.get("/sessions/{session_id}/calculate")
def calculate_scores(session_id: str, db: Session = Depends(get_db)):
    """Calculate weighted scores and recommendation."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    role = get_matrix(db_session.role_key)
    scores = db.query(InterviewScore).filter(InterviewScore.session_id == db_session.id).all()
    score_map = {s.question_id: float(s.score) for s in scores}

    # Calculate per-section scores
    section_results = []
    total_weighted = 0.0
    total_weight = 0.0

    for section in role["sections"]:
        section_questions = section["questions"]
        section_scores = []
        for q in section_questions:
            q_score = score_map.get(q["id"])
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
            "scores": {q["id"]: score_map.get(q["id"]) for q in section_questions},
        })

    overall_score = round(total_weighted, 2) if total_weight > 0 else 0.0

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

    # Update session
    db_session.overall_score = overall_score
    db_session.recommendation = recommendation
    db_session.recommendation_class = recommendation_class
    db_session.status = "completed" if db_session.answered_questions == db_session.total_questions else "in_progress"
    db.commit()

    result = {
        "success": True,
        "session_id": session_id,
        "candidate_name": db_session.candidate_name,
        "role": db_session.role_title,
        "progress": {
            "answered": db_session.answered_questions,
            "total": db_session.total_questions,
            "percent": float(db_session.progress_percent) if db_session.progress_percent else 0,
        },
        "sections": section_results,
        "overall_score": overall_score,
        "total_weight": total_weight,
        "recommendation": recommendation,
        "recommendation_class": recommendation_class,
        "scoring_thresholds": scoring,
        "scored_at": datetime.now().isoformat(),
    }

    return result


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    final_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Mark session as complete with final notes. Optionally send email."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    db_session.status = "completed"
    db_session.completed_at = datetime.utcnow()
    if final_notes:
        db_session.final_notes = final_notes

    # Ensure calculation is done
    if db_session.overall_score is None:
        # We can't call the endpoint from here directly, so calculate inline
        role = get_matrix(db_session.role_key)
        scores = db.query(InterviewScore).filter(InterviewScore.session_id == db_session.id).all()
        score_map = {s.question_id: float(s.score) for s in scores}

        total_weighted = 0.0
        total_weight = 0.0
        for section in role["sections"]:
            section_scores = [score_map.get(q["id"]) for q in section["questions"] if score_map.get(q["id"]) is not None]
            if section_scores:
                avg = sum(section_scores) / len(section_scores)
                total_weighted += avg * (section["weight"] / 100)
                total_weight += section["weight"]

        db_session.overall_score = round(total_weighted, 2) if total_weight > 0 else 0.0

        scoring = role.get("scoring", {})
        ov = db_session.overall_score
        if ov >= scoring.get("exceptional", 85):
            db_session.recommendation = "EXCEPTIONAL HIRE"
            db_session.recommendation_class = "exceptional"
        elif ov >= scoring.get("strong", 70):
            db_session.recommendation = "STRONG HIRE"
            db_session.recommendation_class = "strong"
        elif ov >= scoring.get("adequate", 55):
            db_session.recommendation = "ADEQUATE — CONSIDER WITH CAUTION"
            db_session.recommendation_class = "adequate"
        elif ov >= scoring.get("risky", 40):
            db_session.recommendation = "RISKY — NEEDS DEEP REVIEW"
            db_session.recommendation_class = "risky"
        else:
            db_session.recommendation = "REJECT"
            db_session.recommendation_class = "reject"

    db.commit()

    # Build response dict for email
    session_dict = build_session_dict(db_session, include_scores=True)
    session_dict["calculated_result"] = {
        "overall_score": float(db_session.overall_score) if db_session.overall_score else 0,
        "recommendation": db_session.recommendation,
        "recommendation_class": db_session.recommendation_class,
        "sections": [],  # Simplified for email
    }

    # Send email summary
    email_result = await email_service.send_interview_summary(session_dict)

    return {
        "success": True,
        "session": build_session_dict(db_session),
        "email": email_result,
    }


@router.get("/sessions")
def list_sessions(
    role_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all interview sessions."""
    query = db.query(InterviewSession)
    if role_key:
        query = query.filter(InterviewSession.role_key == role_key)
    if status:
        query = query.filter(InterviewSession.status == status)

    total = query.count()
    sessions = query.order_by(InterviewSession.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "sessions": [build_session_dict(s, include_scores=False) for s in sessions],
    }


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete an interview session."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")
    db.delete(db_session)
    db.commit()
    return {"success": True, "message": "Session deleted"}


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str, format: str = "json", db: Session = Depends(get_db)):
    """Export session results as JSON."""
    db_session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(404, f"Session '{session_id}' not found")

    if format == "json":
        return JSONResponse(content={"success": True, "session": build_session_dict(db_session)})

    return JSONResponse(content={"success": False, "error": "Format not supported yet"})
