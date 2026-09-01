from datetime import UTC, datetime

from fastapi import Depends, Query

from app.api.routers import insights as router
from app.db import get_session
from app.engine import rules


@router.get("/rules")
async def list_rules(severity: str | None = Query(None), session=Depends(get_session)):
    now = datetime.now(UTC)
    report = rules.Report()
    findings = await rules.evaluate(session, now=now, report=report)
    if severity:
        findings = [f for f in findings if f.severity == severity]
    return {
        "as_of": now.isoformat(),
        "rules": len(rules.definitions()),
        "findings": [f.as_dict() for f in findings],
        "by_severity": {
            s: sum(1 for f in findings if f.severity == s) for s in rules.SEVERITIES
        },
        "report": report.as_dict(),
    }


@router.get("/rules/definitions")
async def rule_definitions():
    return {
        "rules": {
            name: {
                "label": rule.label,
                "entity": rule.entity,
                "severity": rule.severity,
                "all": [{"attr": c.attr, c.op: c.operand} for c in rule.all_of],
                "any": [{"attr": c.attr, c.op: c.operand} for c in rule.any_of],
            }
            for name, rule in sorted(rules.definitions().items())
        }
    }
