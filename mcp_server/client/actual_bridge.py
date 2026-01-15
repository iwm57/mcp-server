import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Configuration settings for MCP server"""

    actual_bridge_url: str = "http://actual-bridge:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra='ignore'  # Ignore extra fields like LOG_LEVEL
    )


class ActualBridgeClient:
    """HTTP client to communicate with actual-bridge API"""

    def __init__(self):
        settings = Settings()
        self.base_url = settings.actual_bridge_url.rstrip('/')
        self.timeout = 30
        self._client: httpx.AsyncClient = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            verify=False  # Skip SSL verification for self-signed certificates
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_accounts(self):
        """GET /mcp/accounts - Returns [{id, name, type, balance}]"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(f"{self.base_url}/mcp/accounts")
        response.raise_for_status()
        return response.json()

    async def get_categories(self):
        """GET /mcp/categories - Returns [{id, name}]"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(f"{self.base_url}/mcp/categories")
        response.raise_for_status()
        return response.json()

    async def get_monthly_summary(self, month: str):
        """GET /mcp/summary/month?month=YYYY-MM - Returns {month, income, expenses, net}"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(
            f"{self.base_url}/mcp/summary/month",
            params={"month": month}
        )
        response.raise_for_status()
        return response.json()

    async def add_transaction(self, account, amount, date, payee=None, category=None, notes=None):
        """POST /mcp/transactions/add - Accepts account/category NAMES (user-friendly)

        Note: actual-bridge handles name-to-ID lookup internally!
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "account": account,  # Can be NAME or ID - bridge handles lookup
            "amount": amount,    # Decimal (e.g., -50.00) - bridge converts to cents
            "date": date,        # YYYY-MM-DD format
        }
        if payee:
            payload["payee"] = payee
        if category:
            payload["category"] = category  # Can be NAME or ID
        if notes:
            payload["notes"] = notes

        response = await self._client.post(
            f"{self.base_url}/mcp/transactions/add",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_recent_transactions(self, since_date: str = None):
        """GET /transactions/recent?since=YYYY-MM-DD - Returns transaction array"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        params = {"since": since_date} if since_date else {}
        response = await self._client.get(
            f"{self.base_url}/transactions/recent",
            params=params
        )
        response.raise_for_status()
        return response.json()
