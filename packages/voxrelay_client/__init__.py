from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request


@dataclass
class VoxRelayClient:
    base_url: str = "http://localhost:8000"
    token: str | None = None

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(f"{self.base_url}{path}", data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with request.urlopen(req, timeout=15) as res:  # nosec - local demo client
            payload = res.read().decode()
            return json.loads(payload) if payload else {}

    def login(self, email: str = "admin@voxrelay.demo", password: str = "DemoPass123!") -> dict:
        payload = self._call("POST", "/api/v1/auth/login", {"email": email, "password": password})
        self.token = payload["access_token"]
        return payload

    def list_calls(self) -> dict:
        return self._call("GET", "/api/v1/calls")

    def get_call(self, call_id: str) -> dict:
        return self._call("GET", f"/api/v1/calls/{call_id}")

    def start_simulated_call(self, agent_id: str = "agent-clinic", scenario: str = "clinic_booking") -> dict:
        return self._call("POST", f"/api/v1/voice-agents/{agent_id}/simulate", {"scenario": scenario})

    def list_leads(self) -> dict:
        return self._call("GET", "/api/v1/leads")

    def create_followup(self, call_id: str, title: str) -> dict:
        return self._call("POST", f"/api/v1/calls/{call_id}/follow-up", {"title": title, "task_type": "callback"})

    def list_agent_versions(self, agent_id: str = "agent-clinic") -> dict:
        return self._call("GET", f"/api/v1/voice-agents/{agent_id}/versions")

    def run_agent_evaluation(self, version_id: str) -> dict:
        return self._call("POST", f"/api/v1/voice-agents/versions/{version_id}/evaluate", {})

    def create_report(self, report_type: str = "Daily Voice Operations Brief") -> dict:
        return self._call("POST", "/api/v1/reports/generate", {"report_type": report_type})

    def list_alerts(self) -> dict:
        return self._call("GET", "/api/v1/alerts")
