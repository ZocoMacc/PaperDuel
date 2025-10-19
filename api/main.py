import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from typing import Dict, Any, Optional, List

# NOTE: The import path assumes that 'worker' and 'api' are siblings in the project root.
# We import the core BattleService logic from the worker directory.
try:
    from worker.services.battle_service import BattleService, BATTLES
    from worker.services.data_loader import AVAILABLE_ASSETS
except ImportError:
    # Fallback for simple local testing structures if imports fail
    from services.battle_service import BattleService, BATTLES
    from services.data_loader import AVAILABLE_ASSETS


# --- Pydantic Schemas for API Input/Output ---

class DuelStartRequest(BaseModel):
    asset: str
    user_ids: List[str]

class TradeActionRequest(BaseModel):
    battle_id: str
    user_id: str
    action: str
    size: Optional[int] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    traded_asset: Optional[str] = None


# --- FASTAPI APP INITIALIZATION ---

# The root endpoint for your application (e.g., http://127.0.0.1:8000/)
app = FastAPI(title="PaperDuel Competitive Backtesting API", version="1.0")
templates = Jinja2Templates(directory="paperduel_py/templates")


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
def serve_frontend(request: Request):
    """Serves the index.html template when accessing the root URL."""
    # Note: You must add 'from starlette.requests import Request' at the top with other imports
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/battle/start")
def start_battle(request: DuelStartRequest):
    """
    Initializes a new battle session.
    This is called when the user clicks 'Start Duel' on the frontend.
    """
    # 1. Validate Asset
    asset = request.asset.upper()
    if asset not in AVAILABLE_ASSETS:
        raise HTTPException(status_code=400, detail="Invalid asset. Choose ES or NQ.")
    
    # 2. Start the Duel (Worker logic)
    # The list of user_ids is passed to the BattleService worker
    result = BattleService.start_new_battle(asset, request.user_ids)
    
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    
    # 3. Get the initial state (30 bars are seeded client-side)
    initial_battle: BattleService = BATTLES[result['battle_id']]
    initial_state = initial_battle.get_state()
    
    return {
        "battle_id": result['battle_id'],
        "total_bars": result['total_bars'],
        "initial_state": initial_state
    }


@app.post("/battle/{battle_id}/advance")
def advance_bar(battle_id: str):
    """
    Advances the backtesting engine one bar for the specified battle.
    Called repeatedly by the 'Next Bar' or 'Play' button.
    """
    if battle_id not in BATTLES:
        raise HTTPException(status_code=404, detail="Battle not found.")
        
    battle_instance: BattleService = BATTLES[battle_id]
    
    # Advance state (Worker logic)
    return battle_instance.advance_bar()


@app.post("/battle/trade")
def place_trade(request: TradeActionRequest):
    """
    Processes a trade entry or exit for a specific user in a specific battle.
    Called when a user clicks BUY, SELL, or CLOSE.
    """
    if request.battle_id not in BATTLES:
        raise HTTPException(status_code=404, detail="Battle not found.")
        
    battle_instance: BattleService = BATTLES[request.battle_id]
    
    # Execute trade (Worker logic)
    result = battle_instance.execute_market_order(
        action=request.action.upper(),
        size=request.size,
        sl=request.sl,
        tp=request.tp,
        user_id=request.user_id,         # CRITICAL: Identifies which user's state to update
        traded_asset=request.traded_asset.upper()
    )
    
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result
