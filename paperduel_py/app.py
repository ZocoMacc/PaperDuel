from flask import Flask, render_template, jsonify
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

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=True)
