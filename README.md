# PaperDuel
PaperDuel is a web-based simulation where traders can compete head-to-head using real market data.
It combines a realistic backtesting engine built in Python (FastAPI + pandas) with a responsive frontend using Lightweight Charts, letting users trade in real time and see their performance side-by-side.

---

### Demo
Live Demo: https://performed-describing-send-derby.trycloudflare.com
- Click **Start Duel** to begin the game!

---

### Features
- Real-time replay of historical market data
- Two-user battle system with unique battle_ids
- BUY/SELL/CLOSE trading system with SL/TP and slippage
- Live equity, PnL, and position tracking
- Terminal-style interface with live logs

### How to run the app locally
1. Clone the repository
```bash
git clone https://github.com/ZocoMacc/PaperDuel.git
cd PaperDuel
```

3. Create and activate a virtual environment
```
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

5. Install dependencies
```
pip install -r requirements.txt
```

7. Run the backend server
```
uvicorn api.main:app --reload
```
- You should see something like:
    ```
    Uvicorn running on http://127.0.0.1:8000
    ```

8. Go to http://127.0.0.1:8000 and start playing! :)
