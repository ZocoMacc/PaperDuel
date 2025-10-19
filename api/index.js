// api/index.js
const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(cors());            // allow frontend dev server to call the API
app.use(express.json());    // parse JSON bodies

// ---- Helpers ----
const RUNS_DIR = path.join(__dirname, "..", "runs");
if (!fs.existsSync(RUNS_DIR)) fs.mkdirSync(RUNS_DIR, { recursive: true });

// quick helper: write a tiny fake run so the UI can load something
function writeSampleRun(runId) {
  const outPath = path.join(RUNS_DIR, `${runId}.json`);
  const result = {
    runId,
    finalPnl: 350.00,
    returnPct: 0.35,
    maxDrawdownPct: 1.1,
    trades: [
      { t:"2023-01-03T14:31:00Z", side:"BUY",  qty:1, price:3860.00, commission:1.25 },
      { t:"2023-01-03T14:33:00Z", side:"SELL", qty:1, price:3860.75, commission:1.25 }
    ],
    equityCurve: [
      { t:"2023-01-03T14:31:00Z", equity:100000 },
      { t:"2023-01-03T14:32:00Z", equity:100120 },
      { t:"2023-01-03T14:33:00Z", equity:100350 }
    ],
    status: "completed"
  };
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
  return outPath;
}


const DATA_CSV = path.join(__dirname, "..", "data", "es_minute.csv");

// ES constants
const MULTIPLIER = 50;          // $ per index point
const TICK_SIZE = 0.25;         // index points per tick
const SLIPPAGE_TICKS = 0.5;     // slippage per market fill
const COMMISSION = 1.25;        // $ per side per contract

function parseCsvMinimal(csvText) {
  const lines = csvText.trim().split(/\r?\n/);
  const header = lines[0].split(",");
  const idx = {
    ts: header.indexOf("timestamp"),
    open: header.indexOf("open"),
    high: header.indexOf("high"),
    low: header.indexOf("low"),
    close: header.indexOf("close")
  };
  return lines.slice(1).map(line => {
    const c = line.split(",");
    return {
      t: c[idx.ts],
      open: parseFloat(c[idx.open]),
      high: parseFloat(c[idx.high]),
      low: parseFloat(c[idx.low]),
      close: parseFloat(c[idx.close])
    };
  }).filter(r => Number.isFinite(r.open) && Number.isFinite(r.close));
}

function runBuyHold(runId) {
  if (!fs.existsSync(DATA_CSV)) throw new Error("Missing data/es_minute.csv");
  const rows = parseCsvMinimal(fs.readFileSync(DATA_CSV, "utf8"));
  if (rows.length < 2) throw new Error("Not enough rows");

  // Buy 1 contract at first bar open (+ slippage), sell at last bar close (− slippage)
  const entry = rows[0];
  const exit  = rows[rows.length - 1];

  const entryPrice = entry.open + SLIPPAGE_TICKS * TICK_SIZE;       // worse fill
  const exitPrice  = exit.close - SLIPPAGE_TICKS * TICK_SIZE;       // worse fill
  const points     = exitPrice - entryPrice;                        // index points
  const grossPnL   = points * MULTIPLIER;                           // dollars
  const fees       = COMMISSION * 2;                                 // in/out
  const finalPnl   = grossPnL - fees;

  // Simple equity curve: start 100k, track close prices as if holding long
  let equity = 100000;
  const equityCurve = rows.map((r, i) => {
    const price = r.close;
    const holdPoints = (price - entryPrice);
    const holdPnl = holdPoints * MULTIPLIER;
    return { t: r.t, equity: equity + holdPnl };
  });
  // apply exit slippage & fees at the end
  equityCurve[equityCurve.length - 1].equity = 100000 + finalPnl;

  // Max drawdown (simple)
  let peak = -Infinity, maxDD = 0;
  for (const e of equityCurve) {
    peak = Math.max(peak, e.equity);
    maxDD = Math.max(maxDD, (peak - e.equity) / peak);
  }

  const result = {
    runId,
    finalPnl: Number(finalPnl.toFixed(2)),
    returnPct: Number((finalPnl / 100000 * 100).toFixed(2)),
    maxDrawdownPct: Number((maxDD * 100).toFixed(2)),
    trades: [
      { t: entry.t, side: "BUY",  qty: 1, price: Number(entryPrice.toFixed(2)), commission: COMMISSION },
      { t: exit.t,  side: "SELL", qty: 1, price: Number(exitPrice.toFixed(2)),  commission: COMMISSION }
    ],
    equityCurve,
    status: "completed"
  };

  const out = path.join(RUNS_DIR, `${runId}.json`);
  fs.writeFileSync(out, JSON.stringify(result, null, 2));
  return out;
}




// ---- Routes ----

// 1) Home Profile data
app.get("/user/profile", (req, res) => {
  res.json({
    username: "demo",
    wins: 3,
    losses: 1,
    streak: 2,
    recentRuns: [
      { id: "seed_run_1", pnl: 725.5, maxDDPct: 1.8, date: "2023-01-10" },
      { id: "seed_run_2", pnl: -120.0, maxDDPct: 2.5, date: "2023-01-12" }
    ]
  });
});

// 2) Joined Battles list
app.get("/user/joined-battles", (req, res) => {
  res.json([
    { id: "b1", name: "ES Jan Window", status: "finished" },
    { id: "b2", name: "ES Feb Window", status: "running" }
  ]);
});

// 3) Kick off a run (returns a runId)
// For now: immediately write a sample result file so the UI has something to read.
app.post("/battle/:id/run", (req, res) => {
  const runId = `run_${Date.now()}`;
  try {
    runBuyHold(runId);  // real result from CSV
    res.json({ runId });
  } catch (e) {
    console.error(e);
    // fallback to sample so demo never breaks
    writeSampleRun(runId);
    res.json({ runId, note: "fallback sample used (missing/invalid CSV)" });
  }
});


// 4) Get run result (poll this from the frontend)
app.get("/run/:id", (req, res) => {
  const filePath = path.join(RUNS_DIR, `${req.params.id}.json`);
  if (fs.existsSync(filePath)) {
    const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
    res.json(data);
  } else {
    res.json({ status: "queued" }); // not ready yet
  }
});

// 5) Battle leaderboard (simple, static for now)
app.get("/data/es", (req, res) => {
  const p = path.join(__dirname, "..", "data", "es_minute.csv");
  if (!fs.existsSync(p)) {
    return res.status(404).json({ error: "Missing data/es_minute.csv" });
  }
  const txt = fs.readFileSync(p, "utf8").trim().split(/\r?\n/);
  const header = txt[0].split(",");
  const I = (k) => header.indexOf(k);
  const out = txt.slice(1).map(line => {
    const c = line.split(",");
    return { t: c[I("timestamp")], open:+c[I("open")], high:+c[I("high")], low:+c[I("low")], close:+c[I("close")] };
  }).filter(r => Number.isFinite(r.open));
  res.json(out);
});

// ---- Start server ----
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`API running on http://localhost:${PORT}`);
});

