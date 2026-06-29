import os
import json
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime


class TwentyConnector:
    """Connector for Twenty CRM GraphQL API."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

    def _query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/graphql"
        payload = {"query": query}
        if variables: payload["variables"] = variables
        resp = self.session.post(url, json=payload, verify=self.verify_ssl)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})

    def get_job_openings(self, limit: int = 100) -> List[Dict]:
        query = """
        query FindManyJobOpenings {
          jobOpenings: findManyObject(filter: { objectName: { eq: "jobOpenings" } }, pagination: { limit: %d }) {
            edges { node { id title: field(name: "title") description: field(name: "description")
              department: field(name: "department") status: field(name: "status")
              requiredSkills: field(name: "requiredSkills") location: field(name: "location")
              salaryRange: field(name: "salaryRange") createdAt } }
          }
        }
        """ % limit
        data = self._query(query)
        edges = data.get("jobOpenings", {}).get("edges", [])
        return [e["node"] for e in edges]

    def get_job_opening(self, opening_id: str) -> Dict:
        query = """
        query FindOneJobOpening($id: ID!) {
          jobOpening: findOneObject(id: $id) { id title: field(name: "title") description: field(name: "description")
            department: field(name: "department") status: field(name: "status")
            requiredSkills: field(name: "requiredSkills") location: field(name: "location")
            salaryRange: field(name: "salaryRange") createdAt }
        }
        """
        return self._query(query, {"id": opening_id}).get("jobOpening", {})

    def get_candidates(self, job_opening_id: Optional[str] = None, limit: int = 500) -> List[Dict]:
        query = """
        query FindManyPeople($limit: Int) {
          people: findManyPerson(pagination: { limit: $limit }) {
            edges { node { id name { firstName lastName } emails { primaryEmail email }
              phoneNumbers { primaryPhoneNumber phoneNumber } linkedinLink { primaryLinkUrl url }
              jobTitle city company { name } createdAt attachments { id name fullPath } } }
          }
        }
        """
        data = self._query(query, {"limit": limit})
        edges = data.get("people", {}).get("edges", [])
        candidates = []
        for e in edges:
            node = e["node"]
            full_name = f"{node.get('name', {}).get('firstName', '')} {node.get('name', {}).get('lastName', '')}".strip()
            candidates.append({"id": node["id"], "name": full_name, "email": node.get("emails", {}).get("primaryEmail", ""),
                "phone": node.get("phoneNumbers", {}).get("primaryPhoneNumber", ""), "linkedin": node.get("linkedinLink", {}).get("primaryLinkUrl", ""),
                "job_title": node.get("jobTitle", ""), "city": node.get("city", ""), "company": node.get("company", {}).get("name", ""),
                "attachments": node.get("attachments", []), "source": "twenty"})
        return candidates

    def download_attachment(self, attachment_id: str) -> bytes:
        url = f"{self.base_url}/files/{attachment_id}"
        resp = self.session.get(url, verify=self.verify_ssl, stream=True)
        resp.raise_for_status()
        return resp.content

    def update_person(self, person_id: str, **fields) -> Dict:
        mutation = """
        mutation UpdateOnePerson($id: ID!, $data: UpdatePersonInput!) {
          updateOnePerson(id: $id, data: $data) { id }
        }
        """
        return self._query(mutation, {"id": person_id, "data": fields}).get("updateOnePerson", {})

    def create_note(self, person_id: str, title: str, body: str) -> Dict:
        mutation = """
        mutation CreateNote($data: CreateNoteInput!) { createNote(data: $data) { id } }
        """
        return self._query(mutation, {"data": {"title": title, "body": body, "personId": person_id}}).get("createNote", {})

    def health_check(self) -> Dict:
        try:
            return {"status": "connected", "data": self._query("query HealthCheck { checkUserExists }")}
        except Exception as e:
            return {"status": "error", "error": str(e)}


from .erpnext import ERPNextConnector, StandaloneConnector

class CRMConnector:
    """Unified connector that wraps either ERPNext or Twenty."""

    def __init__(self):
        self.mode = os.environ.get("CRM_MODE", "standalone").lower()
        self._connector = None

    @property
    def connector(self):
        if self._connector is None:
            if self.mode == "erpnext":
                self._connector = ERPNextConnector(base_url=os.environ["ERPNEXT_URL"], api_key=os.environ["ERPNEXT_API_KEY"], api_secret=os.environ["ERPNEXT_API_SECRET"])
            elif self.mode == "twenty":
                self._connector = TwentyConnector(base_url=os.environ["TWENTY_URL"], api_key=os.environ["TWENTY_API_KEY"])
            else:
                self._connector = StandaloneConnector(data_dir=os.environ.get("DATA_DIR", "./data"))
        return self._connector

    def get_job_openings(self, **kwargs) -> List[Dict]: return self.connector.get_job_openings(**kwargs)
    def get_job_applicants(self, **kwargs) -> List[Dict]:
        if hasattr(self.connector, "get_candidates"): return self.connector.get_candidates(**kwargs)
        return self.connector.get_job_applicants(**kwargs)
    def get_file(self, file_ref: str) -> bytes:
        if hasattr(self.connector, "download_attachment"): return self.connector.download_attachment(file_ref)
        return self.connector.get_file_attachment(file_ref)
    def save_result(self, result: Dict) -> Any:
        if hasattr(self.connector, "save_result"): return self.connector.save_result(result)
        return {"status": "saved_locally", "path": result.get("file_name", "unknown")}
    def health_check(self) -> Dict: return self.connector.health_check()
