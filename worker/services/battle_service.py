import uuid
from typing import Dict, Any, Optional
# CRITICAL IMPORT FIX: Need AVAILABLE_ASSETS from data_loader for multi-asset init
from .data_loader import load_asset_data, get_asset_rules, COMMISSION_ROUND_TURN, AVAILABLE_ASSETS 

# --- SIMULATED DATABASE (Simplified for Prototype) ---
BATTLES: Dict[str, Any] = {}
USERS: Dict[str, Any] = {
    "user_1": {"username": "testuser", "wins": 0, "rating": 1000}
}
# --- END SIMULATED DATABASE ---


class BattleService:
    """
    The core Worker component. Manages session state, executes trades, 
    enforces rules, and supports dual-asset playback (ES/NQ).
    """
    
    def __init__(self, battle_id: str, asset_symbol: str, user_id: str, initial_equity: float = 100000.0):
        self.id = battle_id
        self.user_id = user_id
        self.asset = asset_symbol
        
        self.rules = get_asset_rules(asset_symbol)
        
        self.all_data = {}
        for asset in AVAILABLE_ASSETS:
            self.all_data[asset] = load_asset_data(asset)
            if self.all_data[asset] is None:
                raise ValueError(f"Could not load data for asset: {asset}. Check 'data' folder.")

        self.total_bars = len(self.all_data[asset_symbol])
        self.current_index = 0
        self.equity = initial_equity
        self.in_position = False
        self.position_direction = 0     
        self.entry_price_points = 0.0
        self.active_position_size = 0 
        self.stop_loss_level = None
        self.take_profit_level = None
        self.max_equity = self.equity
        self.max_drawdown_percent = 0.05
        self.max_trades = 100           
        self.trade_count = 0
        self.status = "RUNNING"
        
        BATTLES[self.id] = self

    # ----------------------------------------------------------------------
    # 1. AUTHENTICATION & BATTLE SETUP HANDLERS (CRITICAL FIX: Added @staticmethod)
    # ----------------------------------------------------------------------

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[str]:
        """Authenticates user (tied to the API's /login endpoint)."""
        if username == "testuser" and password == "password": 
            return "user_1" 
        return None

    @staticmethod
    def start_new_battle(asset_symbol: str, user_id: str) -> Dict[str, Any]:
        """Creates and initializes a new battle session."""
        new_id = str(uuid.uuid4())
        try:
            new_battle = BattleService(new_id, asset_symbol, user_id)
            return {"battle_id": new_id, "asset": asset_symbol, "total_bars": new_battle.total_bars}
        except ValueError as e:
            return {"error": str(e)}

    # ----------------------------------------------------------------------
    # 2. CORE UTILITY METHODS
    # ----------------------------------------------------------------------
    
    def _calculate_pnl(self, final_exit_price: float) -> float:
        """Calculates realized P&L in USD based on current open position and rules."""
        pnl_points = (final_exit_price - self.entry_price_points) * self.position_direction
        gross_pnl_usd = pnl_points * self.rules['multiplier'] * self.active_position_size
        net_pnl_usd = gross_pnl_usd - (self.rules['commission_round_turn'] * self.active_position_size)
        return net_pnl_usd

    def _reset_position(self):
        """Resets all position-related state variables upon successful trade exit."""
        self.in_position = False
        self.position_direction = 0
        self.entry_price_points = 0.0
        self.active_position_size = 0
        self.stop_loss_level = None
        self.take_profit_level = None
        self.trade_count += 1
        
    def _check_drawdown(self) -> bool:
        """Enforces the battle's Max Drawdown rule."""
        self.max_equity = max(self.max_equity, self.equity)
        drawdown_limit = self.max_equity * (1 - self.max_drawdown_percent)
        return self.equity < drawdown_limit

    # ----------------------------------------------------------------------
    # 3. INTERACTIVE EXECUTION (Core Loop Logic)
    # ----------------------------------------------------------------------

    def advance_bar(self) -> Dict[str, Any]:
        """Advances the session one bar and checks for auto-exits (SL/TP/Drawdown)."""
        
        exit_message = None # Initialize message to None
        
        if self.current_index + 1 >= self.total_bars:
            self.status = "ENDED_DATA_EXHAUSTED"
            return self.get_state(status=self.status, exit_message=exit_message)

        self.current_index += 1
        # Use the current asset's bar for checking
        current_bar = self.all_data[self.asset].iloc[self.current_index] 
        
        # --- CHECK AUTO-EXIT CONDITIONS (SL/TP) ---
        if self.in_position and (self.stop_loss_level is not None or self.take_profit_level is not None):
            
            triggered = False
            exit_price = None
            exit_reason = None 

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
                
                exit_message = (
                    f"🛑 AUTO-FILLED: {exit_reason} hit at {exit_price:.2f}. "
                    f"Realized PnL: ${net_pnl_usd:.2f}"
                )
                self._reset_position()


        # --- ENFORCE BATTLE RULES ---
        if self._check_drawdown():
            self.status = "LOST_MAX_DRAWDOWN"
            return self.get_state(status=self.status, exit_message=exit_message)
        
        return self.get_state(exit_message=exit_message)

    def execute_market_order(self, action: str, size: Optional[int] = None, sl: Optional[float] = None, tp: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """
        Processes a trade entry or exit (triggered by BUY, SELL, CLOSE buttons).
        Requires 'traded_asset' from kwargs if entering a new trade.
        """
        traded_asset = kwargs.get('traded_asset', self.asset) 
        traded_rules = get_asset_rules(traded_asset)
        
        if self.current_index + 1 >= self.total_bars:
            return {"error": "Cannot execute: End of data reached."}
            
        next_bar = self.all_data[traded_asset].iloc[self.current_index + 1]
        base_price = next_bar['open']
        
        response = {"action": action, "result": "Failed"}
        slippage_points = traded_rules['slippage_points']

        # --- EXIT LOGIC (Manual Close) ---
        if action == 'CLOSE' and self.in_position:
            
            if traded_asset != self.asset:
                 response["error"] = f"Cannot close {traded_asset}: Position is currently open in {self.asset}."
                 return response
                 
            # Apply Slippage 
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
            
            entry_size = size if size is not None else 0
            if entry_size <= 0:
                response["error"] = "Position size is required and must be positive."
                return response
            if self.trade_count >= self.max_trades:
                 response["error"] = "Trade limit reached for this battle."
                 return response
                 
            direction = 1 if action == 'BUY' else -1

            # 1. Calculate Entry Price with Slippage
            if direction == 1:
                final_entry_price = base_price + slippage_points
            else:
                final_entry_price = base_price - slippage_points

            # 2. VALIDATE SL/TP AGAINST THE CALCULATED ENTRY PRICE (Fixing the logic bug)
            is_invalid = False
            if sl is not None:
                # LONG: SL must be BELOW entry
                if (direction == 1 and sl >= final_entry_price): 
                    is_invalid = True
                # SHORT: SL must be ABOVE entry
                elif (direction == -1 and sl <= final_entry_price): 
                    is_invalid = True
            
            if tp is not None:
                # LONG: TP must be ABOVE entry
                if (direction == 1 and tp <= final_entry_price): 
                    is_invalid = True
                # SHORT: TP must be BELOW entry
                elif (direction == -1 and tp >= final_entry_price): 
                    is_invalid = True

            if is_invalid:
                response["error"] = "Invalid SL and/or TP: SL must be set against direction, TP must be set in favor of direction."
                return response
                
            # 3. Set State (Success)
            self.in_position = True
            self.position_direction = direction
            self.entry_price_points = final_entry_price
            self.active_position_size = entry_size 
            self.stop_loss_level = sl
            self.take_profit_level = tp
            self.asset = traded_asset 
            
            response.update({
                "result": "Executed",
                "entry_price": round(final_entry_price, 2),
                "direction": direction,
                "size": entry_size,
            })

        else:
             response["error"] = "Invalid trade state or action."

        return response
        
    # --- STATE RETURNER ---
    
    def get_state(self, status: Optional[str] = None, exit_message: Optional[str] = None) -> Dict[str, Any]:
        """CRITICAL FIX: Added exit_message to signature. Formats and returns the essential battle state data, including dual-asset prices."""
        
        if self.status != "RUNNING":
             status = self.status
             
        bar_es = self.all_data.get('ES').iloc[self.current_index]
        bar_nq = self.all_data.get('NQ').iloc[self.current_index]
        
        # --- UNREALIZED P&L CALCULATION ---
        unrealized_pnl_usd = 0.0
        # Check against the currently open position's asset
        if self.in_position and self.asset in self.all_data:
            current_rules = get_asset_rules(self.asset) 
            current_bar = self.all_data[self.asset].iloc[self.current_index]
            
            pnl_points = (current_bar['close'] - self.entry_price_points) * self.position_direction
            unrealized_pnl_usd = pnl_points * current_rules['multiplier'] * self.active_position_size
        
        return {
            "battle_id": self.id,
            "user_id": self.user_id,
            "asset": self.asset,
            "status": status if status else self.status,
            "exit_notification": exit_message, # Return the message
            "bar_data": {
                "timestamp": bar_es.name.strftime('%Y-%m-%d %H:%M:%S'),
                "close_es": round(bar_es['close'], 2), 
                "close_nq": round(bar_nq['close'], 2),
            },
            "stats": {
                "equity": round(self.equity, 2),
                "position_asset": self.asset if self.in_position else 'FLAT', 
                "position_direction": self.position_direction,
                "position_size": self.active_position_size,
                "entry_price": round(self.entry_price_points, 2) if self.in_position else 0.0,
                "unrealized_pnl_usd": round(unrealized_pnl_usd, 2),
                "sl_level": self.stop_loss_level,
                "tp_level": self.take_profit_level,
                "trades_remaining": self.max_trades - self.trade_count,
            }
        }