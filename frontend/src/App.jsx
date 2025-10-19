import { useEffect, useRef, useState } from 'react';
import * as LightweightCharts from 'lightweight-charts';

const API = 'http://localhost:3001';
const START_CAPITAL = 100000;
const MULTIPLIER = 50;
const TICK_SIZE = 0.25;
const SLIPPAGE_TICKS = 0.5;
const COMMISSION = 1.25;
const WINDOW = 120; // keep last 120 candles visible

const fallbackBars = [
  { t: '2023-01-03T14:31:00Z', open: 3860.00, high: 3860.25, low: 3859.75, close: 3860.00 },
  { t: '2023-01-03T14:32:00Z', open: 3860.00, high: 3860.75, low: 3859.75, close: 3860.50 },
  { t: '2023-01-03T14:33:00Z', open: 3860.50, high: 3861.00, low: 3860.25, close: 3860.75 },
  { t: '2023-01-03T14:34:00Z', open: 3860.75, high: 3861.00, low: 3860.25, close: 3860.50 },
];

const tsToSec = (iso) => Math.floor(new Date(iso.replace('.000000000Z','Z')).getTime()/1000);
const round2 = (x) => Math.round(x*100)/100;

export default function Replay() {
  const chartEl = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);

  const [bars, setBars] = useState([]);
  const [pos, setPos] = useState(0);
  const [cash, setCash] = useState(START_CAPITAL);
  const [trades, setTrades] = useState([]);

  // runtime refs (avoid stale closures)
  const timerRef = useRef(null);
  const idxRef   = useRef(0);

  // 1) Create chart once
  useEffect(() => {
    const el = chartEl.current;
    const chart = LightweightCharts.createChart(el, {
      width: el.clientWidth || 600,
      height: 380,
      layout: { background: { color: 'white' }, textColor: '#222' },
      grid:   { vertLines: { color: '#eee' }, horzLines: { color: '#eee' } },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        barSpacing: 6,
        fixLeftEdge: true,
        lockVisibleTimeRangeOnResize: true,
        rightOffset: 0,
      },
    });
    const series = chart.addCandlestickSeries();
    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);

    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  // 2) Load bars (API or fallback)
  useEffect(() => {
    fetch(`${API}/data/es`)
      .then(r => r.json())
      .then(data => {
        const cleaned = (Array.isArray(data) && data.length)
          ? data.map(b => ({ t:b.t, open:+b.open, high:+b.high, low:+b.low, close:+b.close }))
          : fallbackBars;
        setBars(cleaned);
      })
      .catch(() => setBars(fallbackBars));
  }, []);

  // 3) Reset state when bars load & seed initial view
  useEffect(() => {
    if (!seriesRef.current || bars.length === 0) return;
    // clear chart
    seriesRef.current.setData([]);
    // reset runtime
    stop(); // ensure no timers
    idxRef.current = 0;
    setPos(0);
    setCash(START_CAPITAL);
    setTrades([]);
    // seed first few candles so it's not empty
    const seedN = Math.min(20, bars.length);
    const seed = bars.slice(0, seedN).map(b => ({
      time: tsToSec(b.t), open:b.open, high:b.high, low:b.low, close:b.close
    }));
    seriesRef.current.setData(seed);
    idxRef.current = seedN;
    chartRef.current.timeScale().fitContent();
  }, [bars]);

  // helpers
  function visibleClamp() {
    const to = idxRef.current;
    const from = Math.max(0, to - WINDOW);
    chartRef.current.timeScale().setVisibleLogicalRange({ from, to });
  }

  // playback
  function appendBar() {
    const k = idxRef.current;
    if (k >= bars.length) { stop(); return; }
    const b = bars[k];
    seriesRef.current.update({ time: tsToSec(b.t), open:b.open, high:b.high, low:b.low, close:b.close });
    idxRef.current = k + 1;
    visibleClamp();
  }
  function play(speedMs=350) {
    if (timerRef.current) return;            // already playing
    timerRef.current = setInterval(appendBar, speedMs);
  }
  function pause() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }
  function step() {
    appendBar();
  }
  function stop() {                          // full stop (used on unmount/reset/end)
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }

  // trading
  function marketFill(dir) {
    const k = idxRef.current;
    const next = bars[k] || bars[k-1];
    if (!next) return;
    const slip = SLIPPAGE_TICKS * TICK_SIZE;
    const fill = dir>0 ? (next.open + slip) : (next.open - slip);
    setTrades(t => [...t, { t: next.t, side: dir>0?'BUY':'SELL', qty:1, price: round2(fill), commission: COMMISSION }]);
    setPos(p => p + dir);
    setCash(c => c - dir * fill * MULTIPLIER - COMMISSION); // buy reduces cash, sell increases
  }
  const buy = () => marketFill(+1);
  const sell = () => marketFill(-1);
  function flatten() {
    if (pos === 0) return;
    const dir = pos > 0 ? -1 : +1;
    for (let i = 0; i < Math.abs(pos); i++) marketFill(dir);
  }

  function lastClose() {
    const k = Math.min(idxRef.current - 1, bars.length - 1);
    return k >= 0 ? bars[k].close : bars[0]?.close ?? 0;
  }
  const equity = round2(cash + pos * lastClose() * MULTIPLIER);

  function finish() {
    pause();
    alert(`Finished!\nBars viewed: ${idxRef.current}/${bars.length}\nPnL $${round2(equity - START_CAPITAL)}`);
  }

  return (
    <div style={{ padding: 12 }}>
      <h1>Replay</h1>
      <div
        ref={chartEl}
        style={{ width: '100%', minWidth: 320, height: 380, border: '1px solid #eee', borderRadius: 8 }}
      />
      <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => play(350)}>Play</button>
        <button onClick={pause}>Pause</button>
        <button onClick={step}>Step</button>
        <button onClick={buy}>Buy</button>
        <button onClick={sell}>Sell</button>
        <button onClick={flatten}>Flatten</button>
        <button onClick={finish}>End / Show Result</button>
      </div>

      {/* Status line so you know data is showing */}
      <div style={{ marginTop: 8 }}>
        <strong>Bars:</strong> {bars.length} &nbsp;|&nbsp;
        <strong>Shown:</strong> {idxRef.current} &nbsp;|&nbsp;
        <strong>Last:</strong> {bars[idxRef.current-1]?.t ?? '—'} @ {bars[idxRef.current-1]?.close ?? '—'}
      </div>
      <div style={{ marginTop: 4 }}>
        <strong>Pos:</strong> {pos} &nbsp;|&nbsp;
        <strong>Cash:</strong> ${round2(cash)} &nbsp;|&nbsp;
        <strong>Equity:</strong> ${equity}
      </div>

      <details style={{ marginTop: 8 }}>
        <summary>Trades</summary>
        <pre>{JSON.stringify(trades, null, 2)}</pre>
      </details>
    </div>
  );
}

