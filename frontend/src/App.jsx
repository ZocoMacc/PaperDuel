// src/App.jsx
import { useEffect, useState } from "react";
import HomeProfile from "./pages/HomeProfile";
import JoinedBattles from "./pages/JoinedBattles";

const API = "http://localhost:3001";

export default function App() {
  const [tab, setTab] = useState("home");
  const [profile, setProfile] = useState(null);
  const [battles, setBattles] = useState([]);

  useEffect(() => {
    fetch(`${API}/user/profile`)
      .then(r => r.json())
      .then(setProfile)
      .catch(() => setProfile({ username:"demo", wins:0, losses:0, streak:0, recentRuns:[] }));

    fetch(`${API}/user/joined-battles`)
      .then(r => r.json())
      .then(setBattles)
      .catch(() => setBattles([]));
  }, []);

  return (
    <div>
      <nav style={{ padding: 12, borderBottom: "1px solid #eee" }}>
        <button onClick={() => setTab("home")}>Home Profile</button>
        <button onClick={() => setTab("joined")} style={{ marginLeft: 8 }}>Joined Battles</button>
      </nav>

      {tab === "home" && profile && <HomeProfile profile={profile} />}
      {tab === "joined" &&
        <JoinedBattles
          battles={battles}
          onView={(id) => window.location.hash = `#battle-${id}`}
        />}
    </div>
  );
}

