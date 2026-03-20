"""Demo helpers for the built-in console."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from acp.database import get_db_dependency
from acp.demo import DEMO_ORG_ID, seed_demo_data

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoSeedRequest(BaseModel):
    replace_existing: bool = True


@router.post("/seed")
async def seed_demo(
    body: DemoSeedRequest,
    db: Annotated[AsyncSession, Depends(get_db_dependency)],
):
    counts = await seed_demo_data(db, replace_existing=body.replace_existing)
    return {"org_id": DEMO_ORG_ID, "counts": counts}
