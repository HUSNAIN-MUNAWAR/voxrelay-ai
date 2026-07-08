from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, email: str = "admin@voxrelay.demo") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_phase3_event_envelope_trace_and_redacted_notes() -> None:
    with TestClient(app) as client:
        headers = login(client, "ops@voxrelay.demo")
        created = client.post("/api/v1/voice-agents/agent-clinic/simulate", headers=headers, json={"scenario": "clinic_booking"})
        assert created.status_code == 201, created.text
        call_id = created.json()["call"]["id"]
        token = headers["Authorization"].split(" ", 1)[1]
        events: list[dict[str, object]] = []
        with client.websocket_connect(f"/api/v1/ws/calls/{call_id}?token={token}") as websocket:
            while True:
                try:
                    events.append(websocket.receive_json())
                except Exception:
                    break
        assert events
        assert {"event_id", "event_type", "sequence", "organization_id", "trace_id", "payload", "schema_version"}.issubset(events[0])
        assert [event["sequence"] for event in events] == sorted(event["sequence"] for event in events)
        note = client.post(f"/api/v1/calls/{call_id}/notes", headers=headers, json={"note": "Call back Jordan at +1 555 999 8888 and email jordan@example.com"})
        assert note.status_code == 201, note.text
        redacted = note.json()["note_redacted"]
        assert "jordan@example.com" not in redacted
        assert "555 999 8888" not in redacted
        trace = client.get(f"/api/v1/platform/trace/{call_id}", headers=headers)
        assert trace.status_code == 200
        assert trace.json()["trace_id"].startswith("trace-")


def test_phase3_cancel_boundary_and_readiness() -> None:
    with TestClient(app) as client:
        headers = login(client)
        created = client.post("/api/v1/calls/simulated", headers=headers, json={"scenario": "low_confidence"})
        assert created.status_code == 201
        call_id = created.json()["call"]["id"]
        cancelled = client.post(f"/api/v1/calls/{call_id}/cancel", headers=headers, json={"reason": "Supervisor stopped the local simulation"})
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "abandoned"
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "connected"


def test_phase3_release_stage_and_api_key_revocation() -> None:
    with TestClient(app) as client:
        manager_headers = login(client, "agentmanager@voxrelay.demo")
        created = client.post("/api/v1/voice-agents/agent-clinic/versions", headers=manager_headers, json={"release_notes": "Phase 3 staged release."})
        version_id = created.json()["id"]
        assert client.post(f"/api/v1/voice-agents/versions/{version_id}/evaluate", headers=manager_headers).status_code == 200
        assert client.post(f"/api/v1/voice-agents/versions/{version_id}/submit", headers=manager_headers).status_code == 200
        admin = login(client)
        carebridge = client.post("/api/v1/auth/switch-workspace", headers=admin, json={"organization_id": "org-carebridge"})
        admin_headers = {"Authorization": f"Bearer {carebridge.json()['access_token']}"}
        assert client.post(f"/api/v1/voice-agents/versions/{version_id}/approve", headers=admin_headers, json={"note": "approved"}).status_code == 200
        staged = client.post(f"/api/v1/voice-agents/versions/{version_id}/stage", headers=admin_headers)
        assert staged.status_code == 200
        assert staged.json()["status"] == "staged"
        activated = client.post(f"/api/v1/voice-agents/versions/{version_id}/activate", headers=admin_headers)
        assert activated.status_code == 200
        key = client.post("/api/v1/security/api-keys", headers=admin_headers, json={"name": "Phase3 calls", "scopes": ["calls:read"]})
        api_key = key.json()["api_key"]
        assert client.get("/api/v1/calls", headers={"X-API-Key": api_key}).status_code == 200
        revoked = client.post(f"/api/v1/security/api-keys/{key.json()['id']}/revoke", headers=admin_headers)
        assert revoked.status_code == 200
        assert client.get("/api/v1/calls", headers={"X-API-Key": api_key}).status_code == 401
