from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, email: str = "admin@voxrelay.demo") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "DemoPass123!"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}", "X-Refresh-Token": payload["refresh_token"]}


def workspace_token(client: TestClient, headers: dict[str, str], organization_id: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/switch-workspace",
        headers={"Authorization": headers["Authorization"]},
        json={"organization_id": organization_id},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_login_and_workspace_membership(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["organizations"] == 3
    headers = login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert len(me.json()["workspaces"]) == 3
    switched = workspace_token(client, headers, "org-carebridge")
    carebridge_calls = client.get("/api/v1/calls", headers=switched)
    assert carebridge_calls.status_code == 200
    assert all(call["organization_id"] == "org-carebridge" for call in carebridge_calls.json()["items"])


def test_cross_tenant_call_lead_agent_and_report_access_is_blocked(client: TestClient) -> None:
    admin_headers = login(client)
    northstar_calls = client.get("/api/v1/calls", headers=admin_headers).json()["items"]
    northstar_call = northstar_calls[0]
    northstar_lead = client.get("/api/v1/leads", headers=admin_headers).json()["items"][0]
    carebridge_headers = workspace_token(client, admin_headers, "org-carebridge")
    assert client.get(f"/api/v1/calls/{northstar_call['id']}", headers=carebridge_headers).status_code == 404
    assert client.get(f"/api/v1/leads/{northstar_lead['id']}", headers=carebridge_headers).status_code == 404
    assert client.get("/api/v1/voice-agents/agent-realestate", headers=carebridge_headers).status_code == 404
    report = client.get("/api/v1/reports", headers=admin_headers).json()["items"][0]
    assert client.get(f"/api/v1/reports/{report['id']}/export", headers=carebridge_headers).status_code == 404


def test_deterministic_call_websocket_persists_transcript_and_entities(client: TestClient) -> None:
    headers = login(client, "ops@voxrelay.demo")
    response = client.post(
        "/api/v1/voice-agents/agent-clinic/simulate",
        headers=headers,
        json={"scenario": "clinic_booking"},
    )
    assert response.status_code == 201, response.text
    call_id = response.json()["call"]["id"]
    token = headers["Authorization"].split(" ", 1)[1]
    events: list[dict[str, object]] = []
    with client.websocket_connect(f"/api/v1/ws/calls/{call_id}?token={token}") as websocket:
        while True:
            try:
                events.append(websocket.receive_json())
            except Exception:
                break
    assert any(event.get("type") == "completed" for event in events)
    detail = client.get(f"/api/v1/calls/{call_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["transcript"]) >= 3
    assert detail.json()["lead"] is not None
    assert detail.json()["appointment"] is not None
    assert detail.json()["entities"]


def test_emergency_routing_and_supervisor_takeover_are_audited(client: TestClient) -> None:
    admin_headers = login(client)
    apex_headers = workspace_token(client, admin_headers, "org-apex")
    route = client.post(
        "/api/v1/routing/evaluate",
        headers=apex_headers,
        json={"context": {"urgency": "emergency"}},
    )
    assert route.status_code == 200
    assert route.json()["destination"] == "Emergency Dispatch"
    simulation = client.post(
        "/api/v1/voice-agents/agent-services/simulate",
        headers=apex_headers,
        json={"scenario": "plumbing_emergency"},
    )
    assert simulation.status_code == 201
    call_id = simulation.json()["call"]["id"]
    takeover = client.post(f"/api/v1/calls/{call_id}/takeover", headers=apex_headers)
    assert takeover.status_code == 200
    assert takeover.json()["status"] == "human_takeover"


def test_agent_version_release_gate_lifecycle(client: TestClient) -> None:
    manager_headers = login(client, "agentmanager@voxrelay.demo")
    create = client.post(
        "/api/v1/voice-agents/agent-clinic/versions",
        headers=manager_headers,
        json={"release_notes": "Strengthen booking confirmation fallback."},
    )
    assert create.status_code == 201, create.text
    version_id = create.json()["id"]
    evaluated = client.post(f"/api/v1/voice-agents/versions/{version_id}/evaluate", headers=manager_headers)
    assert evaluated.status_code == 200
    submitted = client.post(f"/api/v1/voice-agents/versions/{version_id}/submit", headers=manager_headers)
    assert submitted.status_code == 200
    admin_headers = login(client)
    carebridge_headers = workspace_token(client, admin_headers, "org-carebridge")
    approved = client.post(f"/api/v1/voice-agents/versions/{version_id}/approve", headers=carebridge_headers, json={"note": "Demo approval"})
    assert approved.status_code == 200
    activated = client.post(f"/api/v1/voice-agents/versions/{version_id}/activate", headers=carebridge_headers)
    assert activated.status_code == 200
    assert activated.json()["version"]["status"] == "active"


def test_crm_idempotency_retry_and_calendar_conflict(client: TestClient) -> None:
    admin_headers = login(client)
    headers = workspace_token(client, admin_headers, "org-carebridge")
    lead_id = client.get("/api/v1/leads", headers=headers).json()["items"][0]["id"]
    failed = client.post(
        f"/api/v1/leads/{lead_id}/crm-sync",
        headers={**headers, "X-Idempotency-Key": "crm-idempotency-test"},
        json={"simulate_failure": True},
    )
    assert failed.status_code == 200
    repeat = client.post(
        f"/api/v1/leads/{lead_id}/crm-sync",
        headers={**headers, "X-Idempotency-Key": "crm-idempotency-test"},
        json={"simulate_failure": True},
    )
    assert repeat.status_code == 200
    assert repeat.json()["job"]["id"] == failed.json()["job"]["id"]
    retried = client.post(f"/api/v1/integrations/jobs/{failed.json()['job']['id']}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["job"]["status"] == "succeeded"

    scheduler_headers = login(client, "scheduler@voxrelay.demo")
    appointments = client.get("/api/v1/appointments", headers=scheduler_headers).json()["items"]
    target = appointments[0]
    start = datetime.fromisoformat(target["start_time"])
    end = datetime.fromisoformat(target["end_time"])
    conflict = client.post(
        "/api/v1/appointments",
        headers=scheduler_headers,
        json={"title": "Conflict test", "start_time": start.isoformat(), "end_time": end.isoformat(), "assignee": target["assignee"]},
    )
    assert conflict.status_code == 409
    safe_start = datetime.utcnow().replace(microsecond=0) + timedelta(days=180)
    available = client.post(
        "/api/v1/appointments",
        headers=scheduler_headers,
        json={"title": "Conflict-safe test", "start_time": safe_start.isoformat(), "end_time": (safe_start + timedelta(hours=1)).isoformat(), "assignee": f"Verification Team {uuid4().hex[:8]}"},
    )
    assert available.status_code == 201


def test_reports_api_keys_and_provider_visibility(client: TestClient) -> None:
    admin_headers = login(client)
    generated = client.post("/api/v1/reports/generate", headers=admin_headers, json={"report_type": "Daily Voice Operations Brief"})
    assert generated.status_code == 201
    report_id = generated.json()["id"]
    pdf = client.get(f"/api/v1/reports/{report_id}/export", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    key = client.post("/api/v1/security/api-keys", headers=admin_headers, json={"name": "Readonly calls", "scopes": ["calls:read"]})
    assert key.status_code == 201
    api_key = key.json()["api_key"]
    calls = client.get("/api/v1/calls", headers={"X-API-Key": api_key})
    assert calls.status_code == 200
    providers = client.get("/api/v1/providers", headers={"X-API-Key": api_key})
    assert providers.status_code == 403
