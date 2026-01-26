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
        self.bridge_api_key = os.getenv("BRIDGE_API_KEY", None)
        self.timeout = 30
        self._client: httpx.AsyncClient = None

    async def __aenter__(self):
        headers = {}

        # Add API key for actual-bridge authentication
        if self.bridge_api_key:
            headers["x-api-key"] = self.bridge_api_key

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

    async def edit_transaction(self, transaction_id: str, amount: float = None,
                              date: str = None, category: str = None,
                              notes: str = None, cleared: bool = None,
                              account: str = None):
        """PUT /mcp/transactions/:id - Edit an existing transaction

        Args:
            transaction_id: The UUID of the transaction to edit
            amount: New amount in decimal format (e.g., -10.50)
            date: New date in YYYY-MM-DD format
            category: New category name
            notes: New notes/description
            cleared: Whether transaction is cleared
            account: New account name (moves transaction to different account)

        Returns:
            Updated transaction object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {}
        if amount is not None:
            payload["amount"] = amount
        if date:
            payload["date"] = date
        if category:
            payload["category"] = category
        if notes is not None:
            payload["notes"] = notes
        if cleared is not None:
            payload["cleared"] = cleared
        if account:
            payload["account"] = account

        response = await self._client.put(
            f"{self.base_url}/mcp/transactions/{transaction_id}",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def delete_transaction(self, transaction_id: str):
        """DELETE /mcp/transactions/:id - Delete a transaction

        Args:
            transaction_id: The UUID of the transaction to delete

        Returns:
            Confirmation of deletion
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.delete(
            f"{self.base_url}/mcp/transactions/{transaction_id}"
        )
        response.raise_for_status()
        return response.json()

    async def query_transactions(
        self,
        accounts: str | list[str] = None,
        category: str = None,
        start_date: str = None,
        end_date: str = None,
        min_amount: float = None,
        max_amount: float = None,
        search: str = None,
        limit: int = 100
    ):
        """POST /mcp/transactions/query - Query transactions with flexible filters

        Args:
            accounts: Account name(s) - single string or list of strings (default: all accounts)
            category: Category name to filter by
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            min_amount: Minimum amount in dollars
            max_amount: Maximum amount in dollars
            search: Search text (searches notes, payee, imported_payee)
            limit: Maximum number of results (default: 100)

        Returns:
            List of transactions matching criteria
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {"limit": limit}

        if accounts:
            payload["accounts"] = accounts
        if category:
            payload["category"] = category
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if min_amount is not None:
            payload["min_amount"] = min_amount
        if max_amount is not None:
            payload["max_amount"] = max_amount
        if search:
            payload["search"] = search

        response = await self._client.post(
            f"{self.base_url}/mcp/transactions/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()
