"""Audit & Compliance API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.primitives.audit.logger import verify_chain
from acp.primitives.audit.reports import (
    export_audit_log_csv,
    export_audit_log_json,
    generate_eu_ai_act_report,
    generate_soc2_evidence,
)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/events")
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    fmt: str = Query("json", pattern="^(json|csv)$"),
    format_: Optional[str] = Query(None, alias="format", pattern="^(json|csv)$"),
):
    """AUD-03: Export audit log in JSON or CSV."""
    selected_format = format_ or fmt
    kwargs = dict(
        org_id=org_id,
        start=since,
        end=until,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    if selected_format == "csv":
        csv_data = await export_audit_log_csv(db, **kwargs)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    return await export_audit_log_json(db, **kwargs)


@router.get("/verify")
async def verify_integrity(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    """AUD-06: Verify hash chain integrity of the entire audit log."""
    is_valid, tampered_id = await verify_chain(db)
    return {
        "valid": is_valid,
        "tampered_event_id": tampered_id,
        "message": "Audit log integrity verified" if is_valid else f"Tampering detected at event {tampered_id}",
    }


@router.get("/reports/eu-ai-act")
async def eu_ai_act_report(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
):
    """AUD-04: EU AI Act compliance report."""
    return await generate_eu_ai_act_report(db, org_id, start, end)


@router.get("/reports/soc2")
async def soc2_report(
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
    org_id: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
):
    """AUD-05: SOC 2 Type II evidence package."""
    return await generate_soc2_evidence(db, org_id, start, end)
