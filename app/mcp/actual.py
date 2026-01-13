from fastapi import APIRouter, HTTPException
from app.http import bridge_get, bridge_post
from app.config import ACTUAL_BRIDGE_URL

router = APIRouter(prefix="/mcp/actual", tags=["actual"])

# ---------- CAPABILITIES ----------

@router.get("/capabilities")
async def capabilities():
    return {
        "read": [
            "accounts",
            "categories",
            "transactions",
            "monthly_summary"
        ],
        "write": [
            "add_transaction"
        ],
        "features": {
            "dryRun": True,
            "idempotency": True
        }
    }

# ---------- READ ----------

@router.get("/accounts")
async def accounts():
    return await bridge_get(f"{ACTUAL_BRIDGE_URL}/mcp/accounts")

@router.get("/categories")
async def categories():
    return await bridge_get(f"{ACTUAL_BRIDGE_URL}/mcp/categories")

@router.get("/transactions")
async def transactions(since: str | None = None):
    params = f"?since={since}" if since else ""
    return await bridge_get(f"{ACTUAL_BRIDGE_URL}/transactions/recent{params}")

@router.get("/summary/month")
async def month_summary(month: str):
    if not month:
        raise HTTPException(400, "month required (YYYY-MM)")
    return await bridge_get(
        f"{ACTUAL_BRIDGE_URL}/mcp/summary/month?month={month}"
    )

# ---------- WRITE ----------

@router.post("/transactions/add")
async def add_transaction(payload: dict):
    """
    Expected MCP payload:
    {
      "account": "Checking",
      "category": "Food",
      "amount": 12.50,
      "date": "2026-01-12",
      "payee": "Lunch",
      "notes": "...",
      "requestId": "uuid",
      "dryRun": true
    }
    """

    required = ["account", "category", "amount", "date"]
    for f in required:
        if f not in payload:
            raise HTTPException(400, f"Missing field: {f}")

    return await bridge_post(
        f"{ACTUAL_BRIDGE_URL}/mcp/transactions/add",
        payload
    )

# ---------- STATUS ----------

@router.get("/status")
async def status():
    return await bridge_get(f"{ACTUAL_BRIDGE_URL}/mcp/status")
