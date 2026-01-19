import httpx
import os
import logging

logger = logging.getLogger(__name__)


class ActualBridgeClient:
    """HTTP client to communicate with actual-bridge API"""

    def __init__(self):
        # Read from environment variable with fallback
        self.base_url = os.getenv(
            "ACTUAL_BRIDGE_URL",
            "http://actual-bridge:3000"
        ).rstrip('/')
        self.sync_id = os.getenv("ACTUAL_SYNC_ID", None)
        self.file_password = os.getenv("ACTUAL_FILE_PASSWORD", None)
        self.timeout = 30
        self._client: httpx.AsyncClient = None

    async def __aenter__(self):
        headers = {}

        # Add sync_id header if provided
        if self.sync_id:
            headers["x-actual-sync-id"] = self.sync_id

        # Add file password header if provided
        if self.file_password:
            headers["x-actual-file-password"] = self.file_password

        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            verify=False,  # Skip SSL verification for self-signed certificates
            headers=headers
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

    async def add_transaction(self, account, amount, date, notes=None, payee=None, category=None):
        """POST /mcp/transactions/add - Add a transaction

        Note: actual-bridge handles name-to-ID lookup internally!
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "account": account,  # Can be NAME or ID - bridge handles lookup
            "amount": amount,    # Decimal (e.g., -8.50) - bridge converts to cents
            "date": date,        # YYYY-MM-DD format
        }
        if notes:
            payload["notes"] = notes           # Purchase description
        if payee:
            payload["payee"] = payee           # For transfers ONLY (exact account name)
        if category:
            payload["category"] = category     # Can be NAME or ID

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
