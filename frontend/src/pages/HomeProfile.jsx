export default function HomeProfile({ profile }) {
  return (
    <div style={{ padding: 16 }}>
      <h1>Home Profile</h1>
      <p>User: {profile.username}</p>
      <div>Wins: {profile.wins} • Losses: {profile.losses} • Streak: {profile.streak}</div>

      <h2 style={{ marginTop: 16 }}>Recent Runs</h2>
      <ul>
        {profile.recentRuns.map(r => (
          <li key={r.id}>#{r.id} — PnL: ${r.pnl.toFixed(2)} — MaxDD: {r.maxDDPct}% — {r.date}</li>
        ))}
      </ul>
    </div>
  );
}
