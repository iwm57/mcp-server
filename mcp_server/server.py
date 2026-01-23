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

    DEPENDENCIES: Call list_accounts() first to get exact account names.
                  Call list_categories() first if you want to categorize.

    IMPORTANT:
    - For purchases: use 'notes' field (e.g., "coffee at oaks")
    - For transfers: use 'payee' field with EXACT account name (e.g., "Capital One Savings")

    Args:
        account: Account name - MUST match exactly. Example: "Capital One Checking"
        amount: Decimal amount e.g. -8.50 for expense, 100.00 for income
        date: Transaction date in 'YYYY-MM-DD' format
        notes: Purchase description (e.g., "coffee at oaks", "weekly groceries")
        payee: For transfers ONLY - exact account name (e.g., "Capital One Savings")
        category: Category name for categorization (e.g., "Food", "Transport")

    Returns:
        Confirmation with transaction details including generated ID

    Examples:
        # Purchase coffee
        add_transaction(account='Capital One Checking', amount=-8.50,
                       date='2025-01-19', notes='coffee at oaks')

        # Transfer to savings
        add_transaction(account='Capital One Checking', amount=-100.00,
                       date='2025-01-19', payee='Capital One Savings')
    """
    async with ActualBridgeClient() as client:
        result = await client.add_transaction(account, amount, date, notes, payee, category)
        logger.info(f"Added transaction: {result.get('transaction', {})}")
        return result


# =============================================================================
# Tool: Get Recent Transactions
# =============================================================================

@mcp.tool()
async def get_recent_transactions(since_date: str = None) -> list[dict]:
    """Get recent transactions across all accounts.

    Args:
        since_date: Optional start date in 'YYYY-MM-DD' format.
                    Defaults to returning all recent transactions.

    Returns:
        List of transactions with details including date, amount, payee, account, etc.
    """
    async with ActualBridgeClient() as client:
        result = await client.get_recent_transactions(since_date)
        logger.info(f"Retrieved {len(result)} transactions since {since_date or 'beginning'}")
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
    cleared: bool = None
) -> dict:
    """Edit an existing transaction in Actual Budget.

    All parameters except transaction_id are optional - only specify what you want to change.

    Args:
        transaction_id: The UUID of the transaction to edit (get from recent transactions)
        amount: New decimal amount e.g. -8.50 for expense, 100.00 for income
        date: New transaction date in 'YYYY-MM-DD' format
        category: New category name (e.g., "Food", "Transport")
        notes: New description (e.g., "coffee at oaks", "weekly groceries")
        cleared: Whether transaction has cleared (true/false)

    Returns:
        Updated transaction details

    Examples:
        # Change amount
        edit_transaction(transaction_id='abc123', amount=-15.00)

        # Change category and notes
        edit_transaction(transaction_id='abc123', category='Food',
                       notes='lunch at cafe')

        # Clear a transaction
        edit_transaction(transaction_id='abc123', cleared=True)
    """
    async with ActualBridgeClient() as client:
        result = await client.edit_transaction(transaction_id, amount, date,
                                               category, notes, cleared)
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
        transaction_id: The UUID of the transaction to delete (get from recent transactions)

    Returns:
        Confirmation of deletion

    Examples:
        delete_transaction(transaction_id='abc123')
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
    """Query transactions with flexible filters using ActualQL.

    All parameters are optional - omit to include all.

    DEPENDENCIES: Call list_accounts() first to get exact account names.
                  Call list_categories() first if filtering by category.

    Args:
        accounts: Account name(s) - single string or list. Example: "Checking" or ["Checking", "Savings"]
        category: Category name to filter by. Example: "Food"
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        min_amount: Minimum amount in dollars (e.g., -100 for expenses over $100)
        max_amount: Maximum amount in dollars (e.g., 0 for expenses only)
        search: Search text (searches notes, payee, description). Example: "coffee"
        limit: Maximum number of results (default: 100)

    Returns:
        List of transactions with id, date, amount, payee, notes, category, account

    Examples:
        # All transactions from last 30 days
        query_transactions()

        # Transactions in Food category
        query_transactions(category='Food')

        # Expenses over $50 in January
        query_transactions(start_date='2025-01-01', end_date='2025-01-31', max_amount=-50)

        # Search for coffee purchases
        query_transactions(search='coffee')

        # Specific account, recent
        query_transactions(accounts='Checking', start_date='2025-01-01')

        # Multiple accounts with category filter
        query_transactions(accounts=['Checking', 'Savings'], category='Transport')

        # All expenses (negative amounts)
        query_transactions(max_amount=0)
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
    logger.info("  - get_recent_transactions")
    logger.info("  - edit_transaction")
    logger.info("  - delete_transaction")
    logger.info("  - query_transactions")

    # Run the server using STDIO transport
    # This will read JSON-RPC messages from stdin and write to stdout
    mcp.run()


if __name__ == "__main__":
    main()
