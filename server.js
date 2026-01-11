import express from 'express';
import dotenv from 'dotenv';
import * as api from '@actual-app/api';
import fs from 'fs';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

let initialized = false;

async function initActual() {
  if (initialized) return;

  console.log('🔹 Initializing Actual API...');
  console.log('Data directory:', process.env.DATA_DIR);
  console.log('Server URL:', process.env.ACTUAL_SERVER_URL);
  console.log('Sync ID:', process.env.ACTUAL_SYNC_ID);
  console.log('Password provided?', !!process.env.ACTUAL_SERVER_PASSWORD);
  console.log('Budget password provided?', !!process.env.ACTUAL_BUDGET_PASSWORD);

  // Check if dataDir exists
  try {
    if (!fs.existsSync(process.env.DATA_DIR)) {
      console.warn('⚠️ dataDir does not exist! Creating...');
      fs.mkdirSync(process.env.DATA_DIR, { recursive: true });
    }
    const files = fs.readdirSync(process.env.DATA_DIR);
    console.log('Current files in dataDir:', files);
  } catch (err) {
    console.error('❌ Error reading/creating dataDir:', err);
  }

  try {
    await api.init({
      dataDir: process.env.DATA_DIR,
      serverURL: process.env.ACTUAL_SERVER_URL,
      password: process.env.ACTUAL_SERVER_PASSWORD,
    });
    console.log('✅ API init complete');

    await api.downloadBudget(
      process.env.ACTUAL_SYNC_ID,
      process.env.ACTUAL_BUDGET_PASSWORD
        ? { password: process.env.ACTUAL_BUDGET_PASSWORD }
        : undefined
    );
    console.log('✅ Budget download complete');

    initialized = true;
  } catch (err) {
    console.error('❌ Error initializing Actual API:', err);
    throw err; // rethrow so endpoint shows error
  }
}

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

app.get('/debug/full', async (_req, res) => {
  try {
    console.log('🔹 Starting full debug of Actual API');

    await api.init({
      dataDir: process.env.DATA_DIR,
      serverURL: process.env.ACTUAL_SERVER_URL,
      password: process.env.ACTUAL_SERVER_PASSWORD,
    });

    try {
      await api.downloadBudget(
        process.env.ACTUAL_SYNC_ID,
        process.env.ACTUAL_BUDGET_PASSWORD
          ? { password: process.env.ACTUAL_BUDGET_PASSWORD }
          : undefined
      );
      res.json({
        message: 'Budget download succeeded',
        dataDirFiles: fs.readdirSync(process.env.DATA_DIR)
      });
    } catch (err) {
      res.json({
        message: 'Budget download failed',
        error: err.message
      });
    } finally {
      await api.shutdown();
    }
  } catch (err) {
    res.json({ error: 'API init failed', details: err.message });
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
 */
app.get('/transactions/recent', async (req, res) => {
  try {
    const since = req.query.since || '2026-01-01';
    console.log('💳 Fetching recent transactions since', since);
    await initActual();
    const txns = await api.getTransactions({ since });
    res.json(txns);
  } catch (err) {
    console.error('❌ Error fetching transactions:', err);
    res.status(500).json({ error: err.message });
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
