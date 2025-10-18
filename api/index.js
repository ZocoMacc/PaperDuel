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
  writeSampleRun(runId);  // later: call your real worker instead
  res.json({ runId });
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
app.get("/battle/:id/leaderboard", (req, res) => {
  res.json([
    { user: "alice", finalPnl: 1800, maxDrawdownPct: 2.1 },
    { user: "bob",   finalPnl: 1350, maxDrawdownPct: 1.9 },
    { user: "demo",  finalPnl: 350,  maxDrawdownPct: 1.1 }
  ]);
});

// ---- Start server ----
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`API running on http://localhost:${PORT}`);
});

