#!/usr/bin/env python3
"""
Actual Budget MCP Server

A Model Context Protocol server that exposes Actual Budget functionality
as MCP tools, communicating with the actual-bridge HTTP API.
"""

import logging
from fastmcp import FastMCP
from mcp_server.client.actual_bridge import ActualBridgeClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("actual-budget-mcp-server")


# =============================================================================
# Tool: List Accounts
# =============================================================================

@mcp.tool()
async def list_accounts() -> list[dict]:
    """List all accounts with their current balances.

    Returns:
        List of accounts with id, name, type, and balance (decimal format)
    """
    async with ActualBridgeClient() as client:
        result = await client.get_accounts()
        logger.info(f"Retrieved {len(result)} accounts")
        return result


# =============================================================================
# Tool: List Categories
# =============================================================================

@mcp.tool()
async def list_categories() -> list[dict]:
    """List all budget categories available in Actual Budget.

    Returns:
        List of categories with id and name
    """
    async with ActualBridgeClient() as client:
        result = await client.get_categories()
        logger.info(f"Retrieved {len(result)} categories")
        return result


# =============================================================================
# Tool: Get Monthly Summary
# =============================================================================

@mcp.tool()
async def get_monthly_summary(month: str) -> dict:
    """Get monthly budget summary showing income, expenses, and net.

    Args:
        month: Month in 'YYYY-MM' format (e.g., '2026-01')

    Returns:
        Dictionary with month, income (decimal), expenses (decimal), and net (decimal)
    """
    async with ActualBridgeClient() as client:
        result = await client.get_monthly_summary(month)
        logger.info(f"Retrieved summary for {month}")
        return result


# =============================================================================
# Tool: Add Transaction
# =============================================================================

@mcp.tool()
async def add_transaction(
    account: str,
    amount: float,
    date: str,
    notes: str = None,
    payee: str = None,
    category: str = None
) -> dict:
    """Add a new transaction to Actual Budget.

    CRITICAL CONSTRAINTS (enforce these rules):
    1. account: MUST be exact match from list_accounts() - never guess or make up names
    2. amount: Negative for expenses (e.g., -10.50), positive for income (e.g., 100.00)
    3. payee: ONLY for transfers - must be exact account name from list_accounts()
    4. notes: For purchases/expense descriptions (e.g., "coffee", "groceries")
    5. date: YYYY-MM-DD format

    DIFFERENTIATING PURCHASES vs TRANSFERS:
    - PURCHASE: Use 'notes' field with description, leave 'payee' empty
                Example: add_transaction(account='Checking', amount=-10.50, date='2025-01-19', notes='coffee')
    - TRANSFER: Use 'payee' field with EXACT destination account name, 'notes' optional
                Example: add_transaction(account='Checking', amount=-100.00, date='2025-01-19', payee='Savings')

    Args:
        account: REQUIRED - Account name MUST match exactly from list_accounts()
        amount: Decimal - Negative for expense, positive for income
        date: Transaction date in 'YYYY-MM-DD' format
        notes: Purchase description (e.g., "coffee", "weekly groceries") - NOT for transfers
        payee: For transfers ONLY - exact account name from list_accounts()
        category: Optional category name (e.g., "Food", "Transport")

    Returns:
        Confirmation with transaction details including generated ID
    """
    async with ActualBridgeClient() as client:
        result = await client.add_transaction(account, amount, date, notes, payee, category)
        logger.info(f"Added transaction: {result.get('transaction', {})}")
        return result


# =============================================================================
# Tool: Edit Transaction
# =============================================================================

@mcp.tool()
async def edit_transaction(
    transaction_id: str,
    amount: float = None,
    date: str = None,
    category: str = None,
    notes: str = None,
    cleared: bool = None,
    account: str = None
) -> dict:
    """Edit an existing transaction in Actual Budget.

    All parameters except transaction_id are optional - only specify what you want to change.

    CONSTRAINTS:
    - amount: Negative for expenses, positive for income
    - category: Should match from list_categories() if specified
    - account: Should match from list_accounts() if specified

    Args:
        transaction_id: REQUIRED - The UUID of the transaction (get from recent transactions)
        amount: New decimal amount (only include if changing) - negative for expense
        date: New transaction date in 'YYYY-MM-DD' format (only include if changing)
        category: New category name (only include if changing)
        notes: New description (only include if changing)
        cleared: Whether transaction has cleared - true/false (only include if changing)
        account: New account name (only include if changing) - moves transaction to different account

    Returns:
        Updated transaction details
    """
    async with ActualBridgeClient() as client:
        result = await client.edit_transaction(transaction_id, amount, date,
                                               category, notes, cleared, account)
        logger.info(f"Edited transaction {transaction_id}")
        return result


# =============================================================================
# Tool: Delete Transaction
# =============================================================================

@mcp.tool()
async def delete_transaction(transaction_id: str) -> dict:
    """Delete a transaction from Actual Budget.

    WARNING: This action cannot be undone!

    Args:
        transaction_id: REQUIRED - The UUID of the transaction (get from recent transactions)

    Returns:
        Confirmation of deletion
    """
    async with ActualBridgeClient() as client:
        result = await client.delete_transaction(transaction_id)
        logger.info(f"Deleted transaction {transaction_id}")
        return result


# =============================================================================
# Tool: Query Transactions
# =============================================================================

@mcp.tool()
async def query_transactions(
    accounts: str | list[str] = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    min_amount: float = None,
    max_amount: float = None,
    search: str = None,
    limit: int = 100
) -> list[dict]:
    """Query transactions with flexible filters.

    ALL PARAMETERS ARE OPTIONAL - works on all accounts when omitted.
    Use this for powerful searching across all transactions.

    CONSTRAINTS:
    - accounts: Must be exact names from list_accounts() if specified
    - category: Should match from list_categories() if specified
    - min_amount: Use negative values for expense thresholds (e.g., -100 for "expenses over $100")
    - max_amount: Use 0 for "expenses only", negative for "income only"

    Args:
        accounts: OPTIONAL - Account name(s): single string or list. Example: "Checking" or ["Checking", "Savings"]
        category: OPTIONAL - Category name filter. Example: "Food"
        start_date: OPTIONAL - Start date in 'YYYY-MM-DD' format
        end_date: OPTIONAL - End date in 'YYYY-MM-DD' format
        min_amount: OPTIONAL - Minimum amount (e.g., -100 for "over $100 expenses")
        max_amount: OPTIONAL - Maximum amount (e.g., 0 for "expenses only")
        search: OPTIONAL - Text search in notes/payee/description. Example: "coffee"
        limit: OPTIONAL - Max results (default: 100)

    Returns:
        List of transactions with id, date, amount, payee, notes, category, account

    Examples:
        query_transactions()  # All recent transactions
        query_transactions(category='Food')  # Food category
        query_transactions(max_amount=-50)  # Expenses over $50
        query_transactions(search='coffee')  # Search for "coffee"
        query_transactions(start_date='2025-01-01', end_date='2025-01-31')  # January
    """
    async with ActualBridgeClient() as client:
        result = await client.query_transactions(
            accounts=accounts,
            category=category,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            search=search,
            limit=limit
        )
        filters = []
        if accounts:
            filters.append(f"accounts={accounts}")
        if category:
            filters.append(f"category={category}")
        if start_date or end_date:
            filters.append(f"dates={start_date} to {end_date}")
        if search:
            filters.append(f"search='{search}'")
        logger.info(f"Queried transactions: {', '.join(filters) if filters else 'all'} - found {len(result)} results")
        return result


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for the MCP server"""

    logger.info("Starting Actual Budget MCP Server...")
    logger.info("Available tools:")
    logger.info("  - list_accounts")
    logger.info("  - list_categories")
    logger.info("  - get_monthly_summary")
    logger.info("  - add_transaction")
    logger.info("  - edit_transaction")
    logger.info("  - delete_transaction")
    logger.info("  - query_transactions")

    # Run the server using STDIO transport
    # This will read JSON-RPC messages from stdin and write to stdout
    mcp.run()


if __name__ == "__main__":
    main()
