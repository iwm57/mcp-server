# Actual Budget MCP Server

A Model Context Protocol (MCP) server that exposes Actual Budget functionality as MCP tools.

## Overview

This MCP server communicates with [actual-bridge](https://github.com/iwm57/actual-bridge) via HTTP to provide access to Actual Budget data and operations through the official MCP protocol.

## Features

Exposes 6 MCP tools:
- `list_accounts` - List all accounts with balances
- `list_categories` - List all budget categories
- `add_transaction` - Add new transactions (accepts account/category **names**, not IDs)
- `edit_transaction` - Edit existing transaction
- `delete_transaction` - Delete a transaction
- `query_transactions` - Flexible transaction search with multiple filters

## Installation

```bash
pip install -e .
```

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env`:
```bash
ACTUAL_BRIDGE_URL=http://actual-bridge:3000
```

## Usage

### Running the MCP Server

```bash
python -m mcp_server.server
```

The server uses STDIO transport for MCP communication (JSON-RPC 2.0).

### Testing with MCP Inspector

1. Install MCP Inspector:
   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```

2. Start actual-bridge first (ensure it's running)

3. Run Inspector with the MCP server:
   ```bash
   mcp-inspector python -m mcp_server.server
   ```

4. Open browser to `http://localhost:6274` to test tools

### Available Tools

#### 1. list_accounts
```python
# No parameters required
await call_tool("list_accounts", {})
```

Returns:
```json
[
  {
    "id": "account-id",
    "name": "Checking",
    "type": "checking",
    "balance": 1234.56
  }
]
```

#### 2. list_categories
```python
# No parameters required
await call_tool("list_categories", {})
```

Returns:
```json
[
  {
    "id": "category-id",
    "name": "Groceries"
  }
]
```

#### 3. add_transaction
```python
await call_tool("add_transaction", {
  "account": "Checking",  # Use NAME, not ID
  "amount": -50.00,      # Negative for expenses
  "date": "2026-01-14",
  "payee": "Whole Foods",
  "category": "Groceries"  # Use NAME, not ID
})
```

Returns:
```json
{
  "ok": true,
  "transaction": {
    "account": "Checking",
    "category": "Groceries",
    "amount": -50.00,
    "date": "2026-01-14",
    "payee": "Whole Foods",
    "id": "transaction-id"
  },
  "message": "✅ Transaction added successfully"
}
```

#### 4. edit_transaction
```python
await call_tool("edit_transaction", {
  "transaction_id": "txn-id",
  "account": "Checking",     # Optional: update account
  "amount": -75.00,          # Optional: update amount
  "date": "2026-01-15",      # Optional: update date
  "payee": "Updated Store",  # Optional: update payee
  "category": "Dining Out"   # Optional: update category
})
```

Returns:
```json
{
  "ok": true,
  "transaction": {
    "id": "txn-id",
    "account": "Checking",
    "category": "Dining Out",
    "amount": -75.00,
    "date": "2026-01-15",
    "payee": "Updated Store"
  },
  "message": "✅ Transaction updated successfully"
}
```

#### 5. delete_transaction
```python
await call_tool("delete_transaction", {
  "transaction_id": "txn-id"
})
```

Returns:
```json
{
  "ok": true,
  "message": "✅ Transaction deleted successfully"
}
```

#### 6. query_transactions
Flexible transaction search with multiple filters:
```python
await call_tool("query_transactions", {
  "accounts": ["Checking", "Credit Card"],  # Optional: filter by accounts
  "category": "Groceries",                  # Optional: filter by category
  "start_date": "2026-01-01",               # Optional: date range start
  "end_date": "2026-01-31",                 # Optional: date range end
  "min_amount": -100,                       # Optional: minimum amount (negative for expenses)
  "max_amount": -10,                        # Optional: maximum amount
  "search": "coffee",                       # Optional: text search in payee/notes
  "limit": 50                               # Optional: max results (default: 100)
})
```

Returns:
```json
[
  {
    "id": "txn-id",
    "date": "2026-01-14",
    "amount": -25.00,
    "payee": "Coffee Shop",
    "account": "Checking",
    "category": "Food & Drink"
  }
]
```

## Architecture

```
MCP Client (e.g., kb-bot)
    ↓ [STDIO: JSON-RPC 2.0]
MCP Server (this project)
    ↓ [HTTP REST API]
actual-bridge (Node.js)
    ↓ [@actual-app/api]
Actual Budget Data
```

## Design Decisions

1. **Name-based lookup**: Tools accept account/category **names** (user-friendly) instead of IDs. actual-bridge handles name-to-ID resolution internally.

2. **Decimal amounts**: All amounts use decimal format (e.g., -50.00) instead of cents. actual-bridge handles conversion to/from cents.

3. **No dry-run mode**: Per user preference, the `add_transaction` tool always executes for real.

4. **Optional parameters**: `payee`, `category`, and `notes` are optional in `add_transaction` for flexibility.

## Development

### Dependencies

- `fastmcp>=2.14` - MCP server framework
- `httpx>=0.27.0` - Async HTTP client
- `pydantic>=2.0.0` - Data validation
- `pydantic-settings>=2.0.0` - Configuration management
- `python-dotenv>=1.0.0` - Environment variables

### Project Structure

```
mcp-server/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py              # Main MCP server with 6 tools
│   └── client/
│       ├── __init__.py
│       └── actual_bridge.py    # HTTP client to actual-bridge
├── pyproject.toml              # Project configuration
├── .env.example               # Environment template
└── README.md
```

## License

MIT
