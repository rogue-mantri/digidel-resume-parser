import os
import json
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime


class ERPNextConnector:
    """Connector for ERPNext / Frappe REST API."""

    def __init__(self, base_url: str, api_key: str, api_secret: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {api_key}:{api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def get_job_openings(self, status: str = "Open", limit: int = 100) -> List[Dict]:
        url = f"{self.base_url}/api/resource/Job Opening"
        params = {"filters": json.dumps([["status", "=", status]]), "fields": "*", "limit_page_length": limit, "limit_start": 0}
        resp = self.session.get(url, params=params, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_job_opening(self, name: str) -> Dict:
        url = f"{self.base_url}/api/resource/Job Opening/{name}"
        resp = self.session.get(url, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def get_job_applicants(self, job_opening: Optional[str] = None, status: str = "New", limit: int = 500) -> List[Dict]:
        url = f"{self.base_url}/api/resource/Job Applicant"
        filters = [["status", "=", status]]
        if job_opening: filters.append(["job_title", "=", job_opening])
        params = {"filters": json.dumps(filters), "fields": "*", "limit_page_length": limit, "limit_start": 0}
        resp = self.session.get(url, params=params, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_applicant(self, name: str) -> Dict:
        url = f"{self.base_url}/api/resource/Job Applicant/{name}"
        resp = self.session.get(url, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def get_file_attachment(self, file_url: str) -> bytes:
        if file_url.startswith("/"):
            file_url = f"{self.base_url}{file_url}"
        resp = self.session.get(file_url, verify=self.verify_ssl, stream=True)
        resp.raise_for_status()
        return resp.content

    def update_applicant_status(self, name: str, status: str, rating: Optional[float] = None, comments: Optional[str] = None) -> Dict:
        url = f"{self.base_url}/api/resource/Job Applicant/{name}"
        payload = {"status": status}
        if rating is not None: payload["applicant_rating"] = rating
        if comments: payload["notes"] = comments
        resp = self.session.put(url, json=payload, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def create_custom_evaluation(self, applicant_name: str, job_opening: str, match_score: float, decision: str, details: Dict) -> Dict:
        url = f"{self.base_url}/api/resource/Resume Evaluation"
        payload = {"applicant": applicant_name, "job_opening": job_opening, "match_score": match_score, "decision": decision, "evaluation_details": json.dumps(details), "evaluated_at": datetime.now().isoformat()}
        resp = self.session.post(url, json=payload, verify=self.verify_ssl)
        if resp.status_code == 404:
            return {"warning": "Resume Evaluation DocType not found. Please create it or use applicant notes."}
        resp.raise_for_status()
        return resp.json().get("data", {})

    def health_check(self) -> Dict:
        try:
            url = f"{self.base_url}/api/method/frappe.auth.get_logged_user"
            resp = self.session.get(url, verify=self.verify_ssl, timeout=10)
            if resp.status_code == 200:
                return {"status": "connected", "user": resp.json().get("message")}
            return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class StandaloneConnector:
    """Fallback connector that works without any CRM."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "jobs"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "resumes"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "results"), exist_ok=True)

    def get_job_openings(self) -> List[Dict]:
        jobs = []
        jobs_dir = os.path.join(self.data_dir, "jobs")
        for fname in os.listdir(jobs_dir):
            if fname.endswith(".json"):
                with open(os.path.join(jobs_dir, fname), "r", encoding="utf-8") as f:
                    job = json.load(f)
                    job["source"] = "standalone"
                    jobs.append(job)
        return jobs

    def get_job_applicants(self, job_opening: Optional[str] = None) -> List[Dict]:
        resumes = []
        resumes_dir = os.path.join(self.data_dir, "resumes")
        for fname in os.listdir(resumes_dir):
            if fname.lower().endswith((".pdf", ".docx", ".doc", ".txt", ".rtf")):
                resumes.append({"name": fname, "file_path": os.path.join(resumes_dir, fname), "job_opening": job_opening or "manual", "source": "standalone"})
        return resumes

    def save_job(self, job_id: str, title: str, description: str, required_skills: List[str], **kwargs) -> Dict:
        job = {"name": job_id, "job_title": title, "description": description, "required_skills": required_skills, "source": "standalone", "created_at": datetime.now().isoformat(), **kwargs}
        path = os.path.join(self.data_dir, "jobs", f"{job_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=2, ensure_ascii=False)
        return job

    def save_result(self, result: Dict) -> str:
        result_id = result.get("file_name", "unknown") + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.data_dir, "results", f"{result_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        return path

    def health_check(self) -> Dict:
        return {"status": "standalone", "message": "No CRM connected. Using local file storage."}


class ConnectorFactory:
    """Factory to create the appropriate connector based on environment config."""

    @staticmethod
    def from_env() -> Any:
        mode = os.environ.get("CRM_MODE", "standalone").lower()
        if mode == "erpnext":
            base_url = os.environ["ERPNEXT_URL"]
            api_key = os.environ["ERPNEXT_API_KEY"]
            api_secret = os.environ["ERPNEXT_API_SECRET"]
            return ERPNextConnector(base_url, api_key, api_secret)
        elif mode == "twenty":
            raise NotImplementedError("Twenty connector in twenty.py. Use standalone or erpnext for now.")
        else:
            data_dir = os.environ.get("DATA_DIR", "./data")
            return StandaloneConnector(data_dir)
