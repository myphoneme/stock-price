"""Stock API endpoints."""
from fastapi import APIRouter, HTTPException

from ..handlers import handle_get_stock_price

router = APIRouter(prefix="/api", tags=["Stock"])


@router.get("/stock/{symbol}")
async def get_stock_api(symbol: str):
    """Simple REST endpoint for stock price - used by React frontend."""
    result = await handle_get_stock_price({"symbol": symbol})
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
