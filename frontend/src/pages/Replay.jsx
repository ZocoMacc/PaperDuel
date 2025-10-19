import { useEffect, useRef } from 'react';
import * as LightweightCharts from 'lightweight-charts';

export default function Replay() {
  const chartContainerRef = useRef(null);

  useEffect(() => {
    const el = chartContainerRef.current;
    const chart = LightweightCharts.createChart(el, {
      width: el.clientWidth || 600,
      height: 360,
    });
    const series = chart.addCandlestickSeries();

    series.setData([
      { time: 1672756260, open: 3860, high: 3860.25, low: 3859.75, close: 3860 },
      { time: 1672756320, open: 3860, high: 3860.75, low: 3859.75, close: 3860.5 },
    ]);

    return () => chart.remove();
  }, []);

  return (
    <div
      ref={chartContainerRef}
      style={{ width: '100%', minWidth: 320, height: 360, border: '1px solid #eee' }}
    />
  );
}

