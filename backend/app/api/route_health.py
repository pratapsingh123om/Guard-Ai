#importing libs
from fastapi import APIRouter

#using decorators @
router =APIRouter()
@router.get("/health")
#using async to hold code in time to wait and handle other queries
async def check_health():
  return {"status":"health"}

