export const mockProfile = {
  username: "demo",
  wins: 3, losses: 1, streak: 2,
  recentRuns: [
    { id: "r1", pnl: 725.50, maxDDPct: 1.8, date: "2023-01-10" },
    { id: "r2", pnl: -120.00, maxDDPct: 2.5, date: "2023-01-12" }
  ]
};

export const mockBattles = [
  { id: "b1", name: "ES Jan Window", status: "finished" },
  { id: "b2", name: "ES Feb Window", status: "running" }
];

export const mockEquity = [
  { t: "2023-01-03T14:31:00Z", equity: 100000 },
  { t: "2023-01-03T14:32:00Z", equity: 100050 },
  { t: "2023-01-03T14:33:00Z", equity: 100120 }
];

