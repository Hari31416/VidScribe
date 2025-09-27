from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "service": "VidScribe API"}


@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "VidScribe API"}
