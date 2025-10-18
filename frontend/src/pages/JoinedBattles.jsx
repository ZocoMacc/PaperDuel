// src/pages/JoinedBattles.jsx
import { useState } from "react";
const API = "http://localhost:3001";

export default function JoinedBattles({ battles }) {
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);

  async function startRun(battleId) {
    setStatus("Starting…");
    setResult(null);

    const res = await fetch(`${API}/battle/${battleId}/run`, { method: "POST" });
    const { runId } = await res.json();
    setStatus(`Running (${runId})…`);

    // poll for completion
    const poll = setInterval(async () => {
      const r = await fetch(`${API}/run/${runId}`).then(x => x.json());
      if (r.status === "completed") {
        clearInterval(poll);
        setStatus("Completed");
        setResult(r);
      } else {
        setStatus("Running…");
      }
    }, 1000);
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>Joined Battles</h1>
      <ul>
        {battles.map(b => (
          <li key={b.id} style={{ marginBottom: 8 }}>
            {b.name} — {b.status}
            <button style={{ marginLeft: 8 }} onClick={() => startRun(b.id)}>Run</button>
          </li>
        ))}
      </ul>

      {status && <p>{status}</p>}

      {result && (
        <div style={{ marginTop: 16 }}>
          <h2>Result</h2>
          <div>Final PnL: ${result.finalPnl.toFixed(2)}</div>
          <div>Return: {result.returnPct}%</div>
          <div>Max Drawdown: {result.maxDrawdownPct}%</div>
          <details style={{ marginTop: 8 }}>
            <summary>Trades</summary>
            <pre>{JSON.stringify(result.trades, null, 2)}</pre>
          </details>
          <details style={{ marginTop: 8 }}>
            <summary>Equity Curve</summary>
            <pre>{JSON.stringify(result.equityCurve.slice(0, 5), null, 2)} …</pre>
          </details>
        </div>
      )}
    </div>
  );
}

