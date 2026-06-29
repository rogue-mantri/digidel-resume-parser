import re
from typing import Dict, List, Any
from collections import Counter


class JobMatcher:
    """Matches a candidate profile against a job description."""

    def __init__(self):
        self.weights = {"skills_match": 0.35, "experience_match": 0.20, "title_relevance": 0.15, "education_match": 0.10, "keyword_match": 0.10, "ai_bonus": 0.10}

    def match(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        job_title = job.get("job_title", job.get("title", "")).lower()
        job_desc = job.get("description", "").lower()
        job_text = f"{job_title} {job_desc}"
        required_skills = [s.lower() for s in job.get("required_skills", [])]
        bonus_skills = [s.lower() for s in job.get("bonus_skills", [])]
        min_exp = job.get("min_experience", 0)
        max_exp = job.get("max_experience", 99)
        candidate_skills = self._flatten_skills(profile.get("skills", {}))
        candidate_exp = profile.get("years_experience", 0) or 0
        candidate_title = (profile.get("current_title", "") or "").lower()
        candidate_edu = profile.get("education", {})
        candidate_keywords = [k.lower() for k in profile.get("keywords", [])]
        skills_score = self._score_skills(candidate_skills, required_skills, bonus_skills)
        exp_score = self._score_experience(candidate_exp, min_exp, max_exp)
        title_score = self._score_title_relevance(candidate_title, job_title, job_text)
        edu_score = self._score_education(candidate_edu, job_text)
        keyword_score = self._score_keywords(candidate_keywords, job_text, required_skills)
        ai_score = self._score_ai_bonus(candidate_skills, candidate_keywords)
        total = (skills_score * self.weights["skills_match"] + exp_score * self.weights["experience_match"] + title_score * self.weights["title_relevance"] + edu_score * self.weights["education_match"] + keyword_score * self.weights["keyword_match"] + ai_score * self.weights["ai_bonus"])
        return {"match_score": round(total, 1), "recommendation": self._recommendation(total, skills_score, exp_score), "breakdown": {"skills_match": round(skills_score, 1), "experience_match": round(exp_score, 1), "title_relevance": round(title_score, 1), "education_match": round(edu_score, 1), "keyword_match": round(keyword_score, 1), "ai_bonus": round(ai_score, 1)}, "matched_skills": self._get_matched_skills(candidate_skills, required_skills), "missing_skills": self._get_missing_skills(candidate_skills, required_skills), "bonus_skills_found": self._get_matched_skills(candidate_skills, bonus_skills)}

    def _flatten_skills(self, skills: Dict) -> List[str]:
        flat = []
        for cat, items in skills.items():
            if isinstance(items, list): flat.extend([s.lower() for s in items])
            elif isinstance(items, str): flat.append(items.lower())
        return flat

    def _score_skills(self, candidate_skills: List[str], required: List[str], bonus: List[str]) -> float:
        if not required and not bonus: return 50.0
        matched_required = sum(1 for r in required if any(r in cs or cs in r for cs in candidate_skills))
        matched_bonus = sum(1 for b in bonus if any(b in cs or cs in b for cs in candidate_skills))
        req_score = (matched_required / max(len(required), 1)) * 70 if required else 0
        bonus_score = (matched_bonus / max(len(bonus), 1)) * 30 if bonus else 0
        return min(req_score + bonus_score, 100.0)

    def _score_experience(self, candidate_exp: float, min_exp: float, max_exp: float) -> float:
        if candidate_exp == 0 and min_exp == 0: return 100.0
        if candidate_exp < min_exp:
            gap = min_exp - candidate_exp
            return 60.0 if gap <= 1 else max(0, 40 - gap * 10)
        if candidate_exp > max_exp:
            over = candidate_exp - max_exp
            return 80.0 if over <= 2 else 60.0
        return 100.0

    def _score_title_relevance(self, candidate_title: str, job_title: str, job_text: str) -> float:
        if not candidate_title: return 30.0
        if candidate_title in job_title or job_title in candidate_title: return 100.0
        job_words = set(job_title.split())
        cand_words = set(candidate_title.split())
        overlap = len(job_words & cand_words)
        if overlap > 0: return min(70 + overlap * 10, 100)
        job_text_words = set(job_text.split())
        cand_in_job = len(cand_words & job_text_words)
        if cand_in_job > 0: return min(40 + cand_in_job * 10, 70)
        return 20.0

    def _score_education(self, candidate_edu: Dict, job_text: str) -> float:
        if not candidate_edu: return 40.0
        degree = (candidate_edu.get("degree", "") or "").lower()
        field = (candidate_edu.get("field", "") or "").lower()
        job_text_lower = job_text.lower()
        score = 50.0
        if any(d in job_text_lower for d in ["b.tech", "bachelor", "ug", "graduate"]):
            if any(d in degree for d in ["b.tech", "bachelor", "b.e", "b.s"]): score += 20
        if any(d in job_text_lower for d in ["m.tech", "master", "m.s", "postgraduate"]):
            if any(d in degree for d in ["m.tech", "master", "m.e", "m.s"]): score += 20
        if field and any(f in job_text_lower for f in [field, "computer science", "engineering", "technology"]): score += 15
        return min(score, 100.0)

    def _score_keywords(self, candidate_keywords: List[str], job_text: str, required_skills: List[str]) -> float:
        if not candidate_keywords: return 30.0
        job_words = set(job_text.split())
        matched = sum(1 for kw in candidate_keywords if kw in job_text or kw in job_words)
        return min((matched / max(len(candidate_keywords), 1)) * 100, 100.0)

    def _score_ai_bonus(self, candidate_skills: List[str], candidate_keywords: List[str]) -> float:
        all_text = " ".join(candidate_skills + candidate_keywords).lower()
        ai_signals = ["ai", "llm", "langchain", "rag", "openai", "gpt", "vector", "embedding", "fine-tuning", "copilot", "cursor"]
        matches = sum(1 for s in ai_signals if s in all_text)
        if matches >= 3: return 100.0
        if matches >= 1: return 50.0 + matches * 15
        return 0.0

    def _get_matched_skills(self, candidate_skills: List[str], target_skills: List[str]) -> List[str]:
        matched = []
        for t in target_skills:
            for cs in candidate_skills:
                if t in cs or cs in t: matched.append(t); break
        return matched

    def _get_missing_skills(self, candidate_skills: List[str], required_skills: List[str]) -> List[str]:
        missing = []
        for r in required_skills:
            if not any(r in cs or cs in r for cs in candidate_skills): missing.append(r)
        return missing

    def _recommendation(self, total: float, skills_score: float, exp_score: float) -> str:
        if total >= 85: return "STRONG_MATCH"
        elif total >= 70: return "GOOD_MATCH"
        elif total >= 55: return "POTENTIAL_MATCH"
        elif total >= 40: return "NEEDS_REVIEW"
        else: return "NOT_A_MATCH"


class BatchMatcher:
    """Matches candidates against multiple jobs and ranks them."""

    def __init__(self): self.matcher = JobMatcher()

    def match_candidate_to_jobs(self, profile: Dict, jobs: List[Dict]) -> List[Dict]:
        results = []
        for job in jobs:
            match = self.matcher.match(profile, job)
            results.append({"job_id": job.get("name", job.get("id", "unknown")), "job_title": job.get("job_title", job.get("title", "unknown")), **match})
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results

    def match_all_candidates(self, profiles: List[Dict], jobs: List[Dict]) -> Dict[str, List[Dict]]:
        all_matches = {}
        for profile in profiles:
            candidate_name = profile.get("full_name", "unknown")
            all_matches[candidate_name] = self.match_candidate_to_jobs(profile, jobs)
        return all_matches

    def get_best_matches_for_job(self, profiles: List[Dict], job: Dict, top_n: int = 10) -> List[Dict]:
        results = []
        for profile in profiles:
            match = self.matcher.match(profile, job)
            results.append({"candidate_name": profile.get("full_name", "unknown"), "email": profile.get("email", ""), **match})
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results[:top_n]
