const express = require('express');
const actual = require('@actual-app/api');

const {
  ACTUAL_SERVER_URL,
  ACTUAL_SERVER_PASSWORD,
  ACTUAL_BUDGET_SYNC_ID,
  ACTUAL_BUDGET_PASSWORD
} = process.env;

const app = express();
let ready = false;

async function init() {
  await actual.init({
    serverURL: ACTUAL_SERVER_URL,
    password: ACTUAL_SERVER_PASSWORD,
    dataDir: '/data/cache'
  });
  await actual.downloadBudget(
    ACTUAL_BUDGET_SYNC_ID,
    ACTUAL_BUDGET_PASSWORD ? { password: ACTUAL_BUDGET_PASSWORD } : undefined
  );
  ready = true;
  console.log('Bridge ready');
}
init().catch(err => { console.error(err); process.exit(1); });

app.get('/health', (_req, res) => res.json({ ok: ready }));

app.get('/balance', async (_req, res) => {
  if (!ready) return res.status(503).json({ error: 'Not ready' });
  try {
    const accounts = await actual.getAccounts();
    const onBudget = accounts.filter(a => !a.offbudget);
    let total = 0;
    for (const acc of onBudget)
      total += await actual.getAccountBalance(acc.id);
    res.json({ cents: total });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(process.env.PORT || 8000, () =>
  console.log('Listening on port', process.env.PORT || 8000)
);
