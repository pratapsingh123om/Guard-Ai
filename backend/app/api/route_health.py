from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health", summary="Service liveness check")
async def check_health() -> dict[str, str]:
    return {"status": "healthy"}
