from fastapi import FastAPI
from app.mcp.actual import router as actual_router

app = FastAPI(
    title="MCP Server",
    version="1.0.0"
)

app.include_router(actual_router)

@app.get("/health")
async def health():
    return {"ok": True}
