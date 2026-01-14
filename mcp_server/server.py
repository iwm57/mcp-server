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
    payee: str = None,
    category: str = None,
    notes: str = None
) -> dict:
    """Add a new transaction to Actual Budget.

    Args:
        account: Account name (e.g., 'Checking') or ID
        amount: Transaction amount in decimal format (negative for expense, positive for income)
                 Example: -50.00 for $50 expense, 1000.00 for $1000 income
        date: Transaction date in 'YYYY-MM-DD' format
        payee: Payee name or description (optional)
        category: Category name (e.g., 'Groceries') or ID (optional)
        notes: Additional notes or memo (optional)

    Returns:
        Confirmation with transaction details including generated ID

    Example:
        add_transaction(account='Checking', amount=-50.00, date='2026-01-14',
                       payee='Whole Foods', category='Groceries')
    """
    async with ActualBridgeClient() as client:
        result = await client.add_transaction(account, amount, date, payee, category, notes)
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
