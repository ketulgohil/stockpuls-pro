from fastapi import APIRouter

router = APIRouter(prefix="/api/deals", tags=["deals"])


@router.get("/block")
def block_deals():
    from core.block_deals import get_block_deals
    return {"deals": get_block_deals()}


@router.get("/bulk")
def bulk_deals():
    from core.block_deals import get_bulk_deals
    return {"deals": get_bulk_deals()}
