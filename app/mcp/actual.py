from fastapi import FastAPI, APIRouter, HTTPException
from app.http import bridge_get, bridge_post
from app.config import ACTUAL_BRIDGE_URL

app = FastAPI()
router = APIRouter(prefix="/mcp", tags=["MCP"])

# ---------------- Tools Metadata ----------------
TOOLS = {
    "accounts": {
        "type": "read",
        "description": "List all accounts",
        "endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/accounts",
        "method": "GET",
        "args": []
    },
    "categories": {
        "type": "read",
        "description": "List all categories",
        "endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/categories",
        "method": "GET",
        "args": []
    },
    "add_transaction": {
        "type": "write",
        "description": "Add a transaction using an exact account and category match.",
        "endpoint": f"{ACTUAL_BRIDGE_URL}/mcp/transactions/add",
        "method": "POST",
        "args": [
            {"name": "account", "type": "string", "required": true, "description": "Exact name of the account to add the transaction to"},
            {"name": "category", "type": "string", "required": true, "description": "Exact name of the category"},
            {"name": "amount", "type": "number", "required": true, "description": "Amount of the transaction"},
            {"name": "date", "type": "string", "required": true, "description": "Date in YYYY-MM-DD format"},
            {"name": "payee", "type": "string", "required": false, "description": "Used for transfers; must be the exact name of another account"},
            {"name": "notes", "type": "string", "required": false, "description": "Short description of what the transaction is for"}
        ]
    }
}

# ---------------- Tool Discovery ----------------
@router.get("/tools")
async def tools():
    """Return all tools in a machine-readable format."""
    return TOOLS

# ---------------- Execute Any Tool ----------------
@router.post("/execute")
async def execute(tool: str, arguments: dict):
    if tool not in TOOLS:
        raise HTTPException(400, f"Unknown tool: {tool}")

    meta = TOOLS[tool]
    endpoint = meta["endpoint"]
    method = meta["method"]

    # Validate required arguments
    for arg in meta.get("args", []):
        if arg.get("required") and arg["name"] not in arguments:
            raise HTTPException(400, f"Missing required field: {arg['name']}")

    try:
        if method == "GET":
            return await bridge_get(endpoint, params=arguments)
        elif method == "POST":
            return await bridge_post(endpoint, arguments)
        else:
            raise HTTPException(500, f"Unsupported method: {method}")
    except Exception as e:
        raise HTTPException(500, f"Error calling tool {tool}: {e}")

app.include_router(router)
