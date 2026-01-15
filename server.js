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

async function initActual() {
  if (initialized) return;

  console.log('🔹 Initializing Actual API...');
  console.log('Data directory:', process.env.DATA_DIR);
  console.log('Server URL:', process.env.ACTUAL_SERVER_URL);
  console.log('Sync ID:', process.env.ACTUAL_SYNC_ID);

  try {
    await api.init({
      dataDir: process.env.DATA_DIR,
      serverURL: process.env.ACTUAL_SERVER_URL,
      password: process.env.ACTUAL_SERVER_PASSWORD,
    });

    await api.downloadBudget(
      process.env.ACTUAL_SYNC_ID,
      process.env.ACTUAL_BUDGET_PASSWORD
        ? { password: process.env.ACTUAL_BUDGET_PASSWORD }
        : undefined
    );

    initialized = true;
    lastInitTime = new Date().toISOString();

    console.log('✅ Actual API initialized');
  } catch (err) {
    console.error('❌ Error initializing Actual API:', err);
    throw err;
  }
}


//utilize API key
// app.use('/mcp', (req, res, next) => {
//   if (!process.env.BRIDGE_API_KEY) return next();

//   if (req.headers['x-api-key'] !== process.env.BRIDGE_API_KEY) {
//     return res.status(401).json({ error: 'Unauthorized' });
//   }
//   next();
// });


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

app.get('/mcp/accounts', async (_req, res) => {
  try {
    await initActual();
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


app.get('/mcp/categories', async (_req, res) => {
  try {
    await initActual();
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
    await initActual();

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
    await initActual();

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

    const txn = {
      date: tx.date,
      amount: Math.round(tx.amount * 100),
      category: category?.id,
      payee: tx.payee_name ?? tx.payee,
      notes: tx.notes,
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



app.get('/mcp/summary/month', async (req, res) => {
  try {
    await initActual();
    const { month } = req.query;

    if (!month) {
      return res.status(400).json({ error: 'month required (YYYY-MM)' });
    }

    const budget = await api.getBudgetMonth(month);

    const income = budget.income / 100;
    const expenses = budget.spent / 100;

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
    lastInit: lastInitTime
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
      dataDirStatus
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
    await initActual();
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
app.get('/accounts', async (_req, res) => {
  try {
    console.log('💼 Fetching accounts');
    await initActual();
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
    
    await initActual();
    
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
    
    // Sort by date descending (newest first)
    filtered.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    // Limit to 100 most recent
    const recent = filtered.slice(0, 100);
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