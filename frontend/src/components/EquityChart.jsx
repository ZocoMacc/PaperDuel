import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function EquityChart({ data }) {
  return (
    <div style={{ height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <XAxis dataKey="t" hide />
          <YAxis domain={["auto", "auto"]} />
          <Tooltip />
          <Line type="monotone" dataKey="equity" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
