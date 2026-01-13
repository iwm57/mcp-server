import httpx
from app.config import REQUEST_TIMEOUT

async def bridge_get(url: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def bridge_post(url: str, payload: dict):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()
