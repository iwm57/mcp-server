import express from 'express';
import dotenv from 'dotenv';
import * as api from '@actual-app/api';
import fs from 'fs';
import fetch from 'node-fetch';


dotenv.config();

const app = express();
app.use(express.json());
const port = process.env.PORT || 3000;
let lastInitTime = null;
let initialized = false;

// Track the currently loaded sync_id to avoid unnecessary re-downloads
let currentSyncId = null;

async function initActual(syncId = null, filePassword = null) {
  // Use sync_id from parameter, or environment variable if not provided
  const effectiveSyncId = syncId || process.env.ACTUAL_SYNC_ID;

  // If same sync_id is already loaded, skip re-initialization
  if (effectiveSyncId && effectiveSyncId === currentSyncId) {
    console.log(`✅ Budget already loaded: ${effectiveSyncId}`);
    return api;
  }

  // Different sync_id or first load - need to download
  console.log(`🔹 Initializing Actual API for sync_id: ${effectiveSyncId}`);
  console.log('Data directory:', process.env.DATA_DIR);
  console.log('Server URL:', process.env.ACTUAL_SERVER_URL);

  try {
    // Only init the connection once (it's global)
    if (!initialized) {
      await api.init({
        dataDir: process.env.DATA_DIR,
        serverURL: process.env.ACTUAL_SERVER_URL,
        password: process.env.ACTUAL_SERVER_PASSWORD,
      });
      initialized = true;
      lastInitTime = new Date().toISOString();
    }

    // Always download the budget when sync_id changes
    await api.downloadBudget(
      effectiveSyncId,
      filePassword || process.env.ACTUAL_BUDGET_PASSWORD
        ? { password: filePassword || process.env.ACTUAL_BUDGET_PASSWORD }
        : undefined
    );

    // Update current sync_id tracker
    currentSyncId = effectiveSyncId;

    console.log(`✅ Actual API initialized for sync_id: ${effectiveSyncId}`);
    return api;
  } catch (err) {
    console.error(`❌ Error initializing sync_id ${effectiveSyncId}:`, err);
    throw err;
  }
}


// API Key authentication for /mcp routes
app.use('/mcp', (req, res, next) => {
  const apiKey = process.env.BRIDGE_API_KEY;

  // If no API key is configured, allow all requests (dev mode)
  if (!apiKey) {
    console.warn('⚠️  BRIDGE_API_KEY not set - allowing unauthenticated requests');
    return next();
  }

  const requestKey = req.headers['x-api-key'];
  if (requestKey !== apiKey) {
    console.warn(`🚫 Unauthorized request attempt from ${req.ip}`);
    return res.status(401).json({ error: 'Unauthorized - Invalid API key' });
  }

  next();
});


app.get('/mcp/capabilities', (_req, res) => {
  res.json({
    write: ['add_transaction'],
    read: [
      'list_accounts',
      'list_categories',
      'query_transactions',
      'monthly_summary',
      'category_summary'
    ],
    features: {
      dryRun: true,
      idempotency: true
    }
  });
});

app.get('/mcp/accounts', async (req, res) => {
  try {
    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);
    const accounts = await api.getAccounts();

    const result = await Promise.all(accounts.map(async (a) => {
      let balance = null;
      try {
        // Try getting a real balance
        const b = await api.getAccountBalance(a.id);
        balance = b / 100;
      } catch (e) {
        // Fallback if something goes wrong
        balance = null;
      }
      return {
        id: a.id,
        name: a.name,
        type: a.type,
        balance
      };
    }));

    res.json(result);
  } catch (err) {
    console.error('❌ Error in /mcp/accounts:', err);
    res.status(500).json({ error: err.message });
  }
});


app.get('/mcp/categories', async (req, res) => {
  try {
    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);
    const categories = await api.getCategories();

    res.json(categories.map(c => ({
      id: c.id,
      name: c.name
    })));
  } catch (err) {
    console.error('❌ Error in /mcp/categories:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/mcp/transactions/preview', express.json(), async (req, res) => {
  try {
    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    const {
      date,
      amount,
      accountId,
      categoryId,
      payee,
      notes
    } = req.body;

    if (!date || !amount || !accountId) {
      return res.status(400).json({ valid: false, error: 'Missing required fields' });
    }

    const accounts = await api.getAccounts();
    const account = accounts.find(a => a.id === accountId);
    if (!account) {
      return res.status(400).json({ valid: false, error: 'Invalid accountId' });
    }

    let category = null;
    if (categoryId) {
      const categories = await api.getCategories();
      category = categories.find(c => c.id === categoryId);
      if (!category) {
        return res.status(400).json({ valid: false, error: 'Invalid categoryId' });
      }
    }

    res.json({
      valid: true,
      resolved: {
        account: account.name,
        category: category?.name ?? null
      },
      transaction: {
        date,
        amountCents: Math.round(amount * 100),
        payee,
        notes
      }
    });
  } catch (err) {
    console.error('❌ Error in /mcp/transactions/preview:', err);
    res.status(500).json({ valid: false, error: err.message });
  }
});

const processedRequests = new Set(); // in-memory, OK for now
app.post('/mcp/transactions/add', async (req, res) => {
  try {
    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    if (!req.body) return res.status(400).json({ error: "Missing JSON body" });

    const { dryRun = false, requestId, account: accountName, category: categoryName, ...tx } = req.body;

    console.log('📝 Add transaction request:', {
      accountName,
      categoryName,
      tx,
      dryRun
    });

    // Fetch accounts and categories once
    const accounts = await api.getAccounts();
    const categories = await api.getCategories();

    const account = accounts.find(a => a.name === accountName);
    if (!account) {
      console.error('❌ Account not found:', accountName);
      console.log('Available accounts:', accounts.map(a => a.name));
      return res.status(400).json({ error: `Account not found: ${accountName}` });
    }

    let category = null;
    if (categoryName) {
      category = categories.find(c => c.name === categoryName);
      if (!category) {
        console.error('❌ Category not found:', categoryName);
        console.log('Available categories:', categories.map(c => c.name));
        return res.status(400).json({ error: `Category not found: ${categoryName}` });
      }
    }

    // Build transaction object
    // payee: ONLY for transfers between accounts (exact account name)
    // notes: For purchase descriptions (e.g., "coffee at oaks")
    const txn = {
      date: tx.date,
      amount: Math.round(tx.amount * 100),  // Convert dollars to cents
      category: category?.id,
      payee: tx.payee,           // For transfers ONLY (exact account name)
      notes: tx.notes,            // Purchase description
      imported_id: requestId
    };

    console.log('💰 Transaction to add:', txn);

    if (dryRun) {
      return res.json({
        ok: true,
        transaction: {
          account: account.name,
          category: category?.name ?? null,
          amount: tx.amount,
          date: tx.date,
          payee: txn.payee,
          notes: txn.notes
        },
        message: "✅ Dry run successful"
      });
    }

    try {
      const createdIds = await api.addTransactions(account.id, [txn]);
      console.log('✅ Transaction added with IDs:', createdIds);

      // Return a recap
      res.json({
        ok: true,
        transaction: {
          account: account.name,
          category: category?.name ?? null,
          amount: tx.amount,
          date: tx.date,
          payee: txn.payee,
          notes: txn.notes,
          id: createdIds[0] ?? null
        },
        message: "✅ Transaction added successfully"
      });
    } catch (apiErr) {
      console.error('❌ API error adding transaction:', apiErr);
      // Don't crash the server, return error to client
      res.status(500).json({
        ok: false,
        error: `Failed to add transaction: ${apiErr.message}`,
        details: apiErr.toString()
      });
    }

  } catch (err) {
    console.error("❌ Error in /mcp/transactions/add:", err);
    res.status(500).json({
      ok: false,
      error: err.message,
      stack: err.stack
    });
  }
});


// =============================================================================
// Transaction Edit/Delete Endpoints
// =============================================================================

/**
 * PUT /mcp/transactions/:id - Edit an existing transaction
 */
app.put('/mcp/transactions/:id', async (req, res) => {
  try {
    const transactionId = req.params.id;
    const { amount, date, category, notes, cleared } = req.body;

    console.log('✏️ Edit transaction request:', {
      transactionId,
      amount,
      date,
      category,
      notes,
      cleared
    });

    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    // Build the update object with only provided fields
    const updates = {};

    if (amount !== undefined) {
      updates.amount = Math.round(amount * 100);  // Convert dollars to cents
    }

    if (date) {
      updates.date = date;
    }

    if (notes !== undefined) {
      updates.notes = notes;
    }

    if (cleared !== undefined) {
      updates.cleared = cleared;
    }

    // Handle category lookup by name
    if (category) {
      const categories = await api.getCategories();
      const categoryObj = categories.find(c => c.name === category || c.id === category);
      if (categoryObj) {
        updates.category = categoryObj.id;
      } else {
        return res.status(400).json({ error: `Category not found: ${category}` });
      }
    }

    // Verify transaction exists by getting all transactions first
    const allTxns = await api.getTransactions();
    const existingTxn = allTxns.find(t => t.id === transactionId);

    if (!existingTxn) {
      return res.status(404).json({ error: `Transaction not found: ${transactionId}` });
    }

    console.log('📝 Updating transaction:', transactionId, 'with:', updates);

    // Apply the update
    await api.updateTransaction(transactionId, updates);

    // Build response from existing transaction + updates (avoids stale cache issues)
    // We don't fetch back because @actual-app/api has internal caching delays
    const result = {
      id: transactionId,
      amount: updates.amount !== undefined ? updates.amount / 100 : existingTxn.amount / 100,
      date: updates.date || existingTxn.date,
      notes: updates.notes !== undefined ? updates.notes : existingTxn.notes,
      cleared: updates.cleared !== undefined ? updates.cleared : existingTxn.cleared,
      payee: existingTxn.payee,
    };

    // Get account and category names for response
    const accounts = await api.getAccounts();
    const categories = await api.getCategories();

    const account = accounts.find(a => a.id === existingTxn.account);
    result.account = account?.name || 'Unknown';

    // Get category name (use updated category or existing)
    const categoryId = updates.category || existingTxn.category;
    const categoryObj = categoryId ? categories.find(c => c.id === categoryId) : null;
    result.category = categoryObj?.name || null;

    console.log('✅ Transaction updated:', transactionId);

    res.json({
      ok: true,
      transaction: result,
      message: "✅ Transaction updated successfully"
    });
  } catch (err) {
    console.error('❌ Error in /mcp/transactions/:id (PUT):', err);
    res.status(500).json({
      ok: false,
      error: err.message,
      stack: err.stack
    });
  }
});

/**
 * DELETE /mcp/transactions/:id - Delete a transaction
 */
app.delete('/mcp/transactions/:id', async (req, res) => {
  try {
    const transactionId = req.params.id;

    console.log('🗑️ Delete transaction request:', transactionId);

    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    // Verify transaction exists before deleting
    const allTxns = await api.getTransactions();
    const existingTxn = allTxns.find(t => t.id === transactionId);

    if (!existingTxn) {
      return res.status(404).json({ error: `Transaction not found: ${transactionId}` });
    }

    // Get account name for response
    const accounts = await api.getAccounts();
    const account = accounts.find(a => a.id === existingTxn.account);

    // Delete the transaction
    await api.deleteTransaction(transactionId);

    console.log('✅ Transaction deleted:', transactionId);

    res.json({
      ok: true,
      deleted: {
        id: transactionId,
        account: account?.name || 'Unknown',
        amount: existingTxn.amount / 100,
        date: existingTxn.date
      },
      message: "✅ Transaction deleted successfully"
    });
  } catch (err) {
    console.error('❌ Error in /mcp/transactions/:id (DELETE):', err);
    res.status(500).json({
      ok: false,
      error: err.message,
      stack: err.stack
    });
  }
});

/**
 * POST /mcp/transactions/query - Query transactions with flexible filters
 *
 * Uses ActualQL runQuery for powerful filtering:
 * - Filter by account(s), category, date range, amount range, search text
 * - Multiple accounts supported
 * - All parameters optional
 *
 * Body:
 * {
 *   accounts: string | string[],  // Account name(s) - default: all accounts
 *   category: string,             // Category name - optional
 *   start_date: string,           // YYYY-MM-DD - optional
 *   end_date: string,             // YYYY-MM-DD - optional
 *   min_amount: number,           // Minimum amount in dollars - optional
 *   max_amount: number,           // Maximum amount in dollars - optional
 *   search: string,               // Search in notes/payee - optional
 *   limit: number                 // Max results - default: 100
 * }
 */
app.post('/mcp/transactions/query', async (req, res) => {
  try {
    const {
      accounts,
      category,
      start_date,
      end_date,
      min_amount,
      max_amount,
      search,
      limit = 100
    } = req.body;

    console.log('🔍 Query transactions request:', {
      accounts,
      category,
      start_date,
      end_date,
      min_amount,
      max_amount,
      search,
      limit
    });

    // Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    // Get accounts and categories for ID lookup
    const allAccounts = await api.getAccounts();
    const allCategories = await api.getCategories();

    // Build filter conditions for ActualQL
    const conditions = [];

    // Account filter - resolve names to IDs
    if (accounts) {
      const accountList = Array.isArray(accounts) ? accounts : [accounts];
      const accountIds = accountList
        .map(name => allAccounts.find(a => a.name === name))
        .filter(a => a)
        .map(a => `'${a.id}'`);

      if (accountIds.length > 0) {
        conditions.push(`transaction.account IN (${accountIds.join(', ')})`);
      }
    }

    // Category filter - resolve name to ID
    if (category) {
      const categoryObj = allCategories.find(c => c.name === category);
      if (categoryObj) {
        conditions.push(`transaction.category = '${categoryObj.id}'`);
      } else {
        // Category not found - return empty results
        console.log(`⚠️ Category not found: ${category}`);
        return res.json([]);
      }
    }

    // Date range filter
    if (start_date) {
      conditions.push(`transaction.date >= '${start_date}'`);
    }
    if (end_date) {
      conditions.push(`transaction.date <= '${end_date}'`);
    }

    // Amount range filter (convert dollars to cents)
    if (min_amount !== undefined) {
      conditions.push(`transaction.amount >= ${Math.round(min_amount * 100)}`);
    }
    if (max_amount !== undefined) {
      conditions.push(`transaction.amount <= ${Math.round(max_amount * 100)}`);
    }

    // Search in notes/payee/imported_payee
    if (search) {
      const searchTerm = search.replace(/'/g, "''"); // Escape quotes
      conditions.push(`(
        transaction.notes LIKE '%${searchTerm}%' OR
        transaction.payee_name LIKE '%${searchTerm}%' OR
        transaction.imported_payee LIKE '%${searchTerm}%'
      )`);
    }

    // Build the ActualQL query
    let query = `
      SELECT {
        id: t.id,
        account: t.account,
        amount: t.amount,
        date: t.date,
        payee: t.payee,
        payee_name: t.payee_name,
        imported_payee: t.imported_payee,
        notes: t.notes,
        category: t.category,
        cleared: t.cleared
      }
      FROM transactions t
    `;

    if (conditions.length > 0) {
      query += ` WHERE ${conditions.join(' AND ')}`;
    }

    // Add sorting and limit
    query += ` ORDER BY t.date DESC LIMIT ${limit}`;

    console.log(`🔍 Running ActualQL query: ${query.replace(/\n/g, ' ').trim()}`);

    // Execute the query
    const result = await api.runQuery({ query });

    console.log(`✅ Found ${result?.length || 0} transactions`);

    // Format results with account and category names
    const accountMap = new Map(allAccounts.map(a => [a.id, a.name]));
    const categoryMap = new Map(allCategories.map(c => [c.id, c.name]));

    const formatted = result.map(t => {
      // Get payee display name (prefer payee_name over imported_payee)
      const payeeDisplay = t.payee_name || t.imported_payee || null;

      return {
        id: t.id,
        account: accountMap.get(t.account) || 'Unknown',
        amount: t.amount / 100,  // Convert cents to dollars
        date: t.date,
        payee: payeeDisplay,
        notes: t.notes,
        category: t.category ? categoryMap.get(t.category) || null : null,
        cleared: t.cleared
      };
    });

    res.json(formatted);
  } catch (err) {
    console.error('❌ Error in /mcp/transactions/query:', err);
    res.status(500).json({
      error: err.message,
      stack: err.stack
    });
  }
});


app.get('/mcp/summary/month', async (req, res) => {
  try {
    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);
    const { month } = req.query;

    if (!month) {
      return res.status(400).json({ error: 'month required (YYYY-MM)' });
    }

    const budget = await api.getBudgetMonth(month);

    const income = budget.totalIncome / 100;
    const expenses = budget.totalSpent / 100;

    res.json({
      month,
      income,
      expenses,
      net: income + expenses
    });
  } catch (err) {
    console.error('❌ Error in /mcp/summary/month:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/mcp/status', (_req, res) => {
  res.json({
    initialized,
    budgetLoaded: initialized,
    lastInit: lastInitTime,
    // NEW: Include budget cache info
    cachedBudgets: Array.from(initializedBudgets.keys())
  });
});


/**
 * Health check
 */
app.get('/health', async (_req, res) => {
  console.log('🩺 Health check ping');
  res.json({ ok: true });
});

app.get('/debug', async (_req, res) => {
  try {
    // Check environment variables
    const env = {
      DATA_DIR: process.env.DATA_DIR,
      ACTUAL_SERVER_URL: process.env.ACTUAL_SERVER_URL,
      ACTUAL_SERVER_PASSWORD: !!process.env.ACTUAL_SERVER_PASSWORD,
      ACTUAL_BUDGET_PASSWORD: !!process.env.ACTUAL_BUDGET_PASSWORD,
      ACTUAL_SYNC_ID: process.env.ACTUAL_SYNC_ID,
      PORT: process.env.PORT
    };

    // Check if dataDir exists and is writable
    let dataDirStatus = {};
    try {
      const fs = await import('fs');
      if (!env.DATA_DIR) {
        dataDirStatus.exists = false;
        dataDirStatus.error = 'DATA_DIR not set';
      } else {
        const exists = fs.existsSync(env.DATA_DIR);
        dataDirStatus.exists = exists;
        if (exists) {
          dataDirStatus.files = fs.readdirSync(env.DATA_DIR);
          // Try writing a test file
          const testFile = `${env.DATA_DIR}/.bridge_test`;
          fs.writeFileSync(testFile, 'ok');
          fs.unlinkSync(testFile);
          dataDirStatus.writable = true;
        } else {
          dataDirStatus.files = null;
          dataDirStatus.writable = false;
        }
      }
    } catch (err) {
      dataDirStatus.error = err.message;
    }

    res.json({
      env,
      dataDirStatus,
      // NEW: Include budget cache info
      cachedBudgets: Array.from(initializedBudgets.keys())
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});


/**
 * Monthly budget snapshot
 */
app.get('/budget/:month', async (req, res) => {
  try {
    console.log('📅 Fetching budget for month:', req.params.month);

    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);
    const budget = await api.getBudgetMonth(req.params.month);
    res.json(budget);
  } catch (err) {
    console.error('❌ Error fetching budget:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * Accounts list
 */
app.get('/accounts', async (req, res) => {
  try {
    console.log('💼 Fetching accounts');

    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);
    const accounts = await api.getAccounts();
    res.json(accounts);
  } catch (err) {
    console.error('❌ Error fetching accounts:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * Recent transactions
 * FIXED: Get all transactions and filter by date locally
 */
app.get('/transactions/recent', async (req, res) => {
  try {
    const since = req.query.since;
    console.log('💳 Fetching recent transactions' + (since ? ` since ${since}` : ''));

    // NEW: Read sync_id from header
    const syncId = req.headers['x-actual-sync-id'];
    const filePassword = req.headers['x-actual-file-password'];

    if (!syncId) {
      return res.status(400).json({ error: 'Missing x-actual-sync-id header' });
    }

    await initActual(syncId, filePassword);

    // Get all transactions (API doesn't support date filtering directly)
    console.log('Fetching all transactions...');
    const txns = await api.getTransactions();
    console.log(`✅ Retrieved ${txns?.length || 0} total transactions`);

    // Filter by date if 'since' parameter provided
    let filtered = txns || [];
    if (since) {
      const sinceDate = new Date(since);
      filtered = txns.filter(t => {
        const txnDate = new Date(t.date);
        return txnDate >= sinceDate;
      });
      console.log(`✅ Filtered to ${filtered.length} transactions since ${since}`);
    }

    // Get accounts for mapping account IDs to names
    const accounts = await api.getAccounts();
    const accountMap = new Map(accounts.map(a => [a.id, a.name]));

    // Sort by date descending (newest first)
    filtered.sort((a, b) => new Date(b.date) - new Date(a.date));

    // Limit to 100 most recent, add account_name, and convert cents to dollars
    const recent = filtered.slice(0, 100).map(t => ({
      ...t,
      account_name: accountMap.get(t.account) || 'Unknown',
      amount: t.amount / 100  // Convert cents to dollars for consistent API
    }));
    console.log(`✅ Returning ${recent.length} most recent transactions`);

    res.json(recent);
  } catch (err) {
    console.error('❌ Error fetching transactions:', err);
    console.error('Error stack:', err.stack);
    res.status(500).json({
      error: err.message,
      hint: 'Error retrieving transactions from Actual Budget API'
    });
  }
});

process.on('SIGTERM', async () => {
  console.log('⚠️ SIGTERM received, shutting down API');
  await api.shutdown();
  process.exit(0);
});

app.listen(port, () => {
  console.log(`🚀 Actual bridge listening on :${port}`);
});