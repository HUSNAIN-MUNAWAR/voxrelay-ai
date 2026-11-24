from app.security import has_permission, permission_set


def test_call_stream_requires_call_read_permission():
    viewer = type("Principal", (), {"permissions": permission_set("viewer")})()
    calendar_only = type("Principal", (), {"permissions": permission_set("calendar:read")})()
    assert has_permission(viewer, "calls:read")
    assert not has_permission(calendar_only, "calls:read")
