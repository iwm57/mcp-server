import express from 'express';
import dotenv from 'dotenv';
import * as api from '@actual-app/api';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

let initialized = false;

async function initActual() {
  if (initialized) return;

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
}

/**
 * Health check (Coolify / MCP sanity)
 */
app.get('/health', async (_req, res) => {
  res.json({ ok: true });
});

/**
 * Example: monthly budget snapshot
 */
app.get('/budget/:month', async (req, res) => {
  try {
    await initActual();
    const budget = await api.getBudgetMonth(req.params.month);
    res.json(budget);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * Example: accounts list
 */
app.get('/accounts', async (_req, res) => {
  try {
    await initActual();
    const accounts = await api.getAccounts();
    res.json(accounts);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * Example: recent transactions (MCP-friendly)
 */
app.get('/transactions/recent', async (req, res) => {
  try {
    await initActual();
    const since = req.query.since || '2026-01-01';
    const txns = await api.getTransactions({ since });
    res.json(txns);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

process.on('SIGTERM', async () => {
  await api.shutdown();
  process.exit(0);
});

app.listen(port, () => {
  console.log(`Actual bridge listening on :${port}`);
});
