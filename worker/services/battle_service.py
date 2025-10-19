import uuid
from typing import Dict, Any, Optional
from .data_loader import load_asset_data, get_asset_rules, COMMISSION_ROUND_TURN

# --- SIMULATED DATABASE (for a working prototype) ---
BATTLES: Dict[str, Any] = {}
USERS: Dict[str, Any] = {
    "user_1": {"username": "testuser", "wins": 0, "rating": 1000}
}


class BattleService:
    """
    The core Worker component. Manages session state, executes trades, 
    enforces rules, and incorporates contract sizing and complex fills.
    """
    
    def __init__(self, battle_id: str, asset_symbol: str, user_id: str, initial_equity: float = 100000.0):
        self.id = battle_id
        self.user_id = user_id
        self.asset = asset_symbol
        
        self.rules = get_asset_rules(asset_symbol)
        self.df = load_asset_data(asset_symbol)

        if self.df is None or self.rules is None:
            raise ValueError(f"Could not initialize battle: Data or rules for {asset_symbol} missing.")
        
        # --- CORE BATTLE STATE ---
        self.total_bars = len(self.df)
        self.current_index = 0
        self.equity = initial_equity
        self.in_position = False
        self.position_direction = 0     
        self.entry_price_points = 0.0
        
        # --- CRITICAL NEW SIZING & EXIT LEVELS ---
        self.active_position_size = 0 
        self.stop_loss_level = None      # Price level (in points)
        self.take_profit_level = None    # Price level (in points)
        
        # --- GAMIFICATION/RULE STATE ---
        self.max_equity = self.equity
        self.max_drawdown_percent = 0.05 
        self.max_trades = 100           
        self.trade_count = 0
        self.status = "RUNNING"
        
        BATTLES[self.id] = self

    # --- 1. AUTHENTICATION & BATTLE SETUP HANDLERS ---

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[str]:
        if username == "testuser" and password == "password": 
            return "user_1" 
        return None

    @staticmethod
    def start_new_battle(asset_symbol: str, user_id: str) -> Dict[str, Any]:
        new_id = str(uuid.uuid4())
        try:
            new_battle = BattleService(new_id, asset_symbol, user_id)
            return {"battle_id": new_id, "asset": asset_symbol, "total_bars": new_battle.total_bars}
        except ValueError as e:
            return {"error": str(e)}

    # ----------------------------------------------------------------------
    # 2. INTERACTIVE EXECUTION (Core Loop Logic)
    # ----------------------------------------------------------------------

    def _calculate_pnl(self, final_exit_price: float) -> float:
        """Calculates P&L in USD based on current state and exit price."""
        pnl_points = (final_exit_price - self.entry_price_points) * self.position_direction
        gross_pnl_usd = pnl_points * self.rules['multiplier'] * self.active_position_size
        net_pnl_usd = gross_pnl_usd - (self.rules['commission_round_turn'] * self.active_position_size)
        return net_pnl_usd

    def _reset_position(self):
        """Resets all position-related state variables."""
        self.in_position = False
        self.position_direction = 0
        self.entry_price_points = 0.0
        self.active_position_size = 0
        self.stop_loss_level = None
        self.take_profit_level = None
        self.trade_count += 1 # Increment trade count upon successful close

    def _check_drawdown(self) -> bool:
        """Enforces the battle's Max Drawdown rule."""
        self.max_equity = max(self.max_equity, self.equity)
        drawdown_limit = self.max_equity * (1 - self.max_drawdown_percent)
        return self.equity < drawdown_limit

    def advance_bar(self) -> Dict[str, Any]:
        """
        Advances the session one bar and checks for auto-exits (SL/TP) 
        before checking termination rules.
        """
        if self.current_index + 1 >= self.total_bars:
            self.status = "ENDED_DATA_EXHAUSTED"
            return self.get_state(status=self.status)

        self.current_index += 1
        current_bar = self.df.iloc[self.current_index]
        
        # --- CHECK AUTO-EXIT CONDITIONS (SL/TP) ---
        if self.in_position and (self.stop_loss_level is not None or self.take_profit_level is not None):
            
            # Find if the HIGH or LOW of the current bar triggered the stop/profit
            triggered = False
            exit_price = None

            if self.position_direction == 1: # LONG POSITION
                if self.stop_loss_level is not None and current_bar['low'] <= self.stop_loss_level:
                    triggered = True
                    exit_price = self.stop_loss_level
                    exit_reason = "STOP_LOSS"
                elif self.take_profit_level is not None and current_bar['high'] >= self.take_profit_level:
                    triggered = True
                    exit_price = self.take_profit_level
                    exit_reason = "TAKE_PROFIT"

            elif self.position_direction == -1: # SHORT POSITION
                if self.stop_loss_level is not None and current_bar['high'] >= self.stop_loss_level:
                    triggered = True
                    exit_price = self.stop_loss_level
                    exit_reason = "STOP_LOSS"
                elif self.take_profit_level is not None and current_bar['low'] <= self.take_profit_level:
                    triggered = True
                    exit_price = self.take_profit_level
                    exit_reason = "TAKE_PROFIT"

            if triggered:
                net_pnl_usd = self._calculate_pnl(exit_price)
                self.equity += net_pnl_usd
                self._reset_position()
                print(f"   [AUTO-FILLED]: {exit_reason} executed at {exit_price:.2f}. PnL: ${net_pnl_usd:.2f}")


        # --- ENFORCE BATTLE RULES ---
        if self._check_drawdown():
            self.status = "LOST_MAX_DRAWDOWN"
            return self.get_state(status=self.status)
        
        return self.get_state()

    def execute_market_order(self, action: str, size: Optional[int] = None, sl: Optional[float] = None, tp: Optional[float] = None) -> Dict[str, Any]:
        """
        Processes a trade entry or exit.
        Includes mandatory size parameter and optional SL/TP levels.
        """
        if self.current_index + 1 >= self.total_bars:
            return {"error": "Cannot execute: End of data reached."}
            
        next_bar = self.df.iloc[self.current_index + 1]
        base_price = next_bar['open']
        response = {"action": action, "result": "Failed"}
        
        slippage_points = self.rules['slippage_points']

        # --- EXIT LOGIC (Manual Close) ---
        if action == 'CLOSE' and self.in_position:
            
            # Apply Slippage against the trade (same logic as before)
            if self.position_direction == 1: 
                final_exit_price = base_price - slippage_points
            else:
                final_exit_price = base_price + slippage_points
                
            net_pnl_usd = self._calculate_pnl(final_exit_price)
            self.equity += net_pnl_usd
            self._reset_position()
            
            response.update({
                "result": "Closed", 
                "pnl_usd": round(net_pnl_usd, 2), 
                "new_equity": round(self.equity, 2)
            })

        # --- ENTRY LOGIC (Buy or Sell) ---
        elif action in ('BUY', 'SELL') and not self.in_position:
            
            # 1. Mandatory Position Sizing Check
            entry_size = size if size is not None else 0
            if entry_size <= 0:
                response["error"] = "Position size is required and must be greater than zero."
                return response
            if self.trade_count >= self.max_trades:
                 response["error"] = "Trade limit reached for this battle."
                 return response
                 
            direction = 1 if action == 'BUY' else -1

            # 2. Apply Slippage for Fill at Next Open
            if direction == 1:
                final_entry_price = base_price + slippage_points
            else:
                final_entry_price = base_price - slippage_points
                
            # 3. Set State
            self.in_position = True
            self.position_direction = direction
            self.entry_price_points = final_entry_price
            self.active_position_size = entry_size 
            self.stop_loss_level = sl
            self.take_profit_level = tp
            
            response.update({
                "result": "Executed",
                "entry_price": round(final_entry_price, 2),
                "direction": direction,
                "size": entry_size,
                "sl_set": sl if sl else 'None',
                "tp_set": tp if tp else 'None',
            })

        else:
             response["error"] = "Invalid trade state or action."

        return response
        
    # --- STATE RETURNER ---
    
    def get_state(self, status: Optional[str] = None) -> Dict[str, Any]:
        """Formats and returns the essential battle state data for the API."""
        
        if self.status != "RUNNING":
             status = self.status
             
        bar = self.df.iloc[self.current_index]
        
        return {
            "battle_id": self.id,
            "user_id": self.user_id,
            "asset": self.asset,
            "status": status if status else self.status,
            "bar_data": {
                "timestamp": bar.name.strftime('%Y-%m-%d %H:%M:%S'),
                "open": round(bar['open'], 2),
                "high": round(bar['high'], 2),
                "low": round(bar['low'], 2),
                "close": round(bar['close'], 2),
                "volume": int(bar['volume']),
            },
            "stats": {
                "equity": round(self.equity, 2),
                "position_direction": self.position_direction,
                "position_size": self.active_position_size,
                "entry_price": round(self.entry_price_points, 2) if self.in_position else 0.0,
                "sl_level": self.stop_loss_level,
                "tp_level": self.take_profit_level,
                "trades_remaining": self.max_trades - self.trade_count,
            }
        }