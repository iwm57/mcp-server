from fastapi import APIRouter, HTTPException
from app.http import bridge_get, bridge_post
from app.config import ACTUAL_BRIDGE_URL


router = APIRouter(prefix="/mcp/actual", tags=["actual"])

# ---------- CAPABILITIES ----------

@router.get("/capabilities")
async def capabilities():
    return {
        "read": {
            "accounts": {
                "description": "List all accounts in Actual Budget",
                "args": []
            },
            "categories": {
                "description": "List all categories available for transactions",
                "args": []
            },
            "transactions": {
                "description": "Query recent transactions. Optional argument 'since' in YYYY-MM-DD format",
                "args": [
                    {"name": "since", "type": "string", "format": "YYYY-MM-DD", "required": False}
                ]
            },
            "monthly_summary": {
                "description": "Get a monthly summary for a given month (YYYY-MM)",
                "args": [
                    {"name": "month", "type": "string", "format": "YYYY-MM", "required": True}
                ]
            }
        },
        "write": {
            "add_transaction": {
                "description": "Add a transaction to Actual Budget",
                "args": [
                    {"name": "account", "type": "string", "required": True},
                    {"name": "category", "type": "string", "required": True},
                    {"name": "amount", "type": "number", "required": True},
                    {"name": "date", "type": "string", "format": "YYYY-MM-DD", "required": True},
                    {"name": "payee", "type": "string", "required": False},
                    {"name": "notes", "type": "string", "required": False},
                    {"name": "dryRun", "type": "boolean", "required": False},
                    {"name": "requestId", "type": "string", "required": False}
                ]
            }
        },
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
  
  
  
from fastapi import APIRouter, HTTPException
from app.http import bridge_get, bridge_post
from app.config import ACTUAL_BRIDGE_URL

router = APIRouter(prefix="/mcp", tags=["MCP"])

# Tool metadata — reuse from /capabilities
TOOLS = {
    "read": {
        "accounts": {"endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/accounts", "method": "GET"},
        "categories": {"endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/categories", "method": "GET"},
        "transactions": {"endpoint": f"{ACTUAL_BRIDGE_URL}/transactions/recent", "method": "GET"},
        "monthly_summary": {"endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/summary/month", "method": "GET"}
    },
    "write": {
        "add_transaction": {"endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/transactions/add", "method": "POST"}
    }
}


@router.post("/execute")
async def execute(tool: str, arguments: dict):
    """
    Unified MCP execution endpoint.
    - tool: name of the tool to call
    - arguments: dict of arguments for the tool
    """

    # 1️⃣ Determine if tool exists
    if tool in TOOLS["read"]:
        meta = TOOLS["read"][tool]
        method = meta["method"]
        endpoint = meta["endpoint"]

        # Build GET query params
        params = arguments if arguments else {}
        try:
            return await bridge_get(endpoint, params=params)
        except Exception as e:
            raise HTTPException(500, f"Error calling {tool}: {e}")

    elif tool in TOOLS["write"]:
        meta = TOOLS["write"][tool]
        method = meta["method"]
        endpoint = meta["endpoint"]

        # Validate required fields for add_transaction
        if tool == "add_transaction":
            required = ["account", "category", "amount", "date"]
            for f in required:
                if f not in arguments:
                    raise HTTPException(400, f"Missing required field: {f}")

        try:
            return await bridge_post(endpoint, arguments)
        except Exception as e:
            raise HTTPException(500, f"Error calling {tool}: {e}")

    else:
        raise HTTPException(400, f"Unknown tool: {tool}")

