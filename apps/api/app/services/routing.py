from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db import RoutingRule


@dataclass(frozen=True)
class RoutingDecision:
    matched: bool
    rule_id: str | None
    rule_name: str | None
    destination_type: str
    destination: str
    fallback: str
    notification: str
    reason: str


def _matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, expected in condition.items():
        actual = context.get(key)
        if isinstance(expected, bool):
            if bool(actual) != expected:
                return False
        elif isinstance(expected, (int, float)) and key.endswith("_below"):
            source_key = key.removesuffix("_below")
            if not isinstance(context.get(source_key), (int, float)) or context[source_key] >= expected:
                return False
        elif actual != expected:
            return False
    return True


def evaluate_routing(db: Session, organization_id: str, context: dict[str, Any]) -> RoutingDecision:
    rules = (
        db.query(RoutingRule)
        .filter(RoutingRule.organization_id == organization_id, RoutingRule.is_active.is_(True))
        .order_by(RoutingRule.priority.asc())
        .all()
    )
    for rule in rules:
        if _matches(rule.condition, context):
            return RoutingDecision(
                matched=True,
                rule_id=rule.id,
                rule_name=rule.name,
                destination_type=rule.destination_type,
                destination=rule.destination,
                fallback=rule.fallback,
                notification=rule.notification,
                reason=f"Rule '{rule.name}' matched {rule.condition}",
            )
    return RoutingDecision(
        matched=False,
        rule_id=None,
        rule_name=None,
        destination_type="ai_agent",
        destination="continue current agent",
        fallback="Create callback task",
        notification="in_app",
        reason="No policy rule matched; continue deterministic local simulation.",
    )
