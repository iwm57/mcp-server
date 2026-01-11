import express from "express";
import actual from "@actual-app/api";
import fs from "fs";

const {
  ACTUAL_SERVER_URL,
  ACTUAL_SERVER_PASSWORD,
  ACTUAL_BUDGET_SYNC_ID,
  ACTUAL_BUDGET_PASSWORD
} = process.env;

if (!ACTUAL_SERVER_URL || !ACTUAL_SERVER_PASSWORD || !ACTUAL_BUDGET_SYNC_ID) {
  throw new Error("Missing required ACTUAL_* env vars");
}

const DATA_DIR = "/data/user-files";
fs.mkdirSync(DATA_DIR, { recursive: true });

const app = express();
let ready = false;

async function initActual() {
  await actual.init({
    dataDir: DATA_DIR,
    serverURL: ACTUAL_SERVER_URL,
    password: ACTUAL_SERVER_PASSWORD
  });

  await actual.downloadBudget(
    ACTUAL_BUDGET_SYNC_ID,
    ACTUAL_BUDGET_PASSWORD
      ? { password: ACTUAL_BUDGET_PASSWORD }
      : undefined
  );

  ready = true;
  console.log("✅ Actual connected and budget downloaded");
}

initActual().catch(err => {
  console.error("❌ Actual init failed:", err);
  process.exit(1);
});

/* ---------- API ---------- */

app.get("/health", (_req, res) => {
  res.json({ ok: true, ready });
});

app.get("/accounts", async (_req, res) => {
  if (!ready) return res.status(503).json({ error: "Not ready" });
  const accounts = await actual.getAccounts();
  res.json(accounts);
});

app.get("/balance", async (_req, res) => {
  if (!ready) return res.status(503).json({ error: "Not ready" });
  const accounts = await actual.getAccounts();
  const total = accounts.reduce((s, a) => s + a.balance, 0);
  res.json({ balance: total });
});

app.listen(8000, () => {
  console.log("🚀 Actual bridge listening on :8000");
});
