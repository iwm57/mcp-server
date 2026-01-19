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

    # Run the server using STDIO transport
    # This will read JSON-RPC messages from stdin and write to stdout
    mcp.run()


if __name__ == "__main__":
    main()
