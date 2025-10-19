from flask import Flask, render_template, jsonify, request
from battle_service import BattleService, BATTLES  # adjust import path if it's a package

import csv, os

app = Flask(__name__)

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "es_minute.csv")

def load_es():
  bars = []
  if not os.path.exists(CSV_PATH):
    return bars
  with open(CSV_PATH, newline="") as f:
    reader = csv.reader(f)
    rows = list(reader)
    # detect header (first cell has letters?)
    start = 1 if rows and any(c.isalpha() for c in rows[0][0]) else 0
    for r in rows[start:]:
      if len(r) < 9:  # your wide CSV example
        continue
      t = r[0]
      try:
        o, h, l, c = float(r[4]), float(r[5]), float(r[6]), float(r[7])
      except:
        continue
      bars.append({"t": t, "open": o, "high": h, "low": l, "close": c})
  return bars

@app.route("/")
def home():
  return render_template("index.html")

@app.route("/data/es")
def data_es():
  bars = load_es()
  return jsonify(bars)

# ------------------- BATTLE_SERVICE INTEGRATION ROUTES -------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    user_id = BattleService.authenticate_user(data.get("username",""), data.get("password",""))
    if not user_id:
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify({"user_id": user_id})

@app.route("/api/battle/start", methods=["POST"])
def api_battle_start():
    data = request.get_json(force=True)
    asset = data.get("asset", "ES")
    user_id = data.get("user_id", "user_1")
    result = BattleService.start_new_battle(asset, user_id)
    return jsonify(result), (200 if "battle_id" in result else 400)

@app.route("/api/battle/<battle_id>/state", methods=["GET"])
def api_battle_state(battle_id):
    b = BATTLES.get(battle_id)
    if not b:
        return jsonify({"error": "battle not found"}), 404
    return jsonify(b.get_state())

@app.route("/api/battle/<battle_id>/advance", methods=["POST"])
def api_battle_advance(battle_id):
    b = BATTLES.get(battle_id)
    if not b:
        return jsonify({"error": "battle not found"}), 404
    return jsonify(b.advance_bar())

@app.route("/api/battle/<battle_id>/order", methods=["POST"])
def api_battle_order(battle_id):
    b = BATTLES.get(battle_id)
    if not b:
        return jsonify({"error": "battle not found"}), 404
    data = request.get_json(force=True)
    action = data.get("action")            # "BUY" | "SELL" | "CLOSE"
    size   = data.get("size")              # int (required for BUY/SELL)
    sl     = data.get("sl")                # optional float
    tp     = data.get("tp")                # optional float
    return jsonify(b.execute_market_order(action, size=size, sl=sl, tp=tp))

# See active battles
@app.route("/api/battle", methods=["GET"])
def list_battles():
    return {"active": list(BATTLES.keys())}



if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=False)
