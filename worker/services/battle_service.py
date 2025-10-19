import uuid
from typing import Dict, Any, Optional, List
from .data_loader import load_asset_data, get_asset_rules, COMMISSION_ROUND_TURN, AVAILABLE_ASSETS 

# --- SIMULATED DATABASE (Simplified for Prototype) ---
BATTLES: Dict[str, Any] = {}
USERS: Dict[str, Any] = {
    "user_1": {"username": "testuser", "wins": 0, "rating": 1000},
    "user_2_opponent": {"username": "opponent", "wins": 0, "rating": 1000} # User for dual testing
}
# --- END SIMULATED DATABASE ---


class BattleService:
    """
    The core Worker component. Manages the state, execution, and competitive rules 
    for an interactive backtesting duel between multiple users.
    """
    
    def __init__(self, battle_id: str, asset_symbol: str, user_ids: List[str], initial_equity: float = 100000.0):
        # 1. Basic Setup
        self.id = battle_id
        self.user_ids = user_ids
        self.asset = asset_symbol # The asset that was chosen when starting the battle
        
        # 2. LOAD ALL DATA (Must happen first)
        self.all_data = {}
        for asset in AVAILABLE_ASSETS:
            self.all_data[asset] = load_asset_data(asset)
            if self.all_data[asset] is None:
                raise ValueError(f"Could not load data for asset: {asset}. Check 'data' folder.")

        self.rules = get_asset_rules(asset_symbol)
        self.total_bars = len(self.all_data[asset_symbol]) # Now safe to calculate
        
        # 3. INITIALIZE TRADERS STATE (CRITICAL: All state is in this dictionary)
        self.current_index = 0
        self.active_traders: Dict[str, Dict[str, Any]] = {}
        
        for user_id in user_ids:
            self.active_traders[user_id] = {
                'equity': initial_equity,
                'in_position': False,
                'position_direction': 0,
                'entry_price_points': 0.0,
                'active_position_size': 0,
                'stop_loss_level': None,
                'take_profit_level': None,
                'max_equity': initial_equity,
            }
        
        # 4. GENERAL BATTLE STATE
        self.max_drawdown_percent = 0.05
        self.max_trades = 100           
        self.trade_count = 0
        self.status = "RUNNING"
        
        BATTLES[self.id] = self

    # ----------------------------------------------------------------------
    # 1. AUTHENTICATION & BATTLE SETUP HANDLERS (Called from API/Test)
    # ----------------------------------------------------------------------

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[str]:
        """CRITICAL FIX: Added @staticmethod."""
        if username == "testuser" and password == "password": 
            return "user_1" 
        return None

    @staticmethod
    def start_new_battle(asset_symbol: str, user_ids: List[str]) -> Dict[str, Any]:
        """Creates and initializes a new battle session for a list of users."""
        new_id = str(uuid.uuid4())
        try:
            # Passes the list of user IDs to the __init__ method
            new_battle = BattleService(new_id, asset_symbol, user_ids)
            return {"battle_id": new_id, "asset": asset_symbol, "total_bars": new_battle.total_bars}
        except ValueError as e:
            return {"error": str(e)}

    # ----------------------------------------------------------------------
    # 2. CORE UTILITY METHODS
    # ----------------------------------------------------------------------
    
    def _calculate_pnl_for_user(self, user_state: Dict[str, Any], final_exit_price: float) -> float:
        """Calculates realized P&L using a specific user's state dictionary."""
        pnl_points = (final_exit_price - user_state['entry_price_points']) * user_state['position_direction']
        
        # NOTE: This uses the battle's initial rules (self.rules)
        gross_pnl_usd = pnl_points * self.rules['multiplier'] * user_state['active_position_size']
        net_pnl_usd = gross_pnl_usd - (self.rules['commission_round_turn'] * user_state['active_position_size'])
        return net_pnl_usd

    def _reset_position_for_user(self, user_id: str):
        """Resets position state for a specific user."""
        user_state = self.active_traders[user_id]
        user_state['in_position'] = False
        user_state['position_direction'] = 0
        user_state['entry_price_points'] = 0.0
        user_state['active_position_size'] = 0
        user_state['stop_loss_level'] = None
        user_state['take_profit_level'] = None
        self.trade_count += 1
        
    def _check_drawdown(self) -> bool:
        """Checks and updates max drawdown for all active users."""
        
        for user_id, state in self.active_traders.items():
            state['max_equity'] = max(state['max_equity'], state['equity'])
            drawdown_limit = state['max_equity'] * (1 - self.max_drawdown_percent)
            
            if state['equity'] < drawdown_limit:
                # If a user loses, we may want to stop the battle entirely or just disqualify them
                self.status = f"LOST_DRAWDOWN_{user_id}" 
                return True
        return False
    
    # ----------------------------------------------------------------------
    # 3. INTERACTIVE EXECUTION (Core Loop Logic)
    # ----------------------------------------------------------------------

    def advance_bar(self) -> Dict[str, Any]:
        """Advances the session one bar, checks SL/TP for all users, and checks drawdown."""
        
        exit_message = None 
        
        if self.current_index + 1 >= self.total_bars:
            self.status = "ENDED_DATA_EXHAUSTED"
            return self.get_state(status=self.status, exit_message=exit_message)

        self.current_index += 1
        
        # Loop through all traders to check their auto-exit conditions
        for user_id, user_state in self.active_traders.items():
            
            if user_state['in_position']:
                current_bar = self.all_data[self.asset].iloc[self.current_index] 
                
                triggered = False
                exit_price = None
                exit_reason = None 

                # --- CHECK SL/TP ---
                if user_state['position_direction'] == 1: # LONG POSITION
                    if user_state['stop_loss_level'] is not None and current_bar['low'] <= user_state['stop_loss_level']:
                        triggered = True
                        exit_price = user_state['stop_loss_level']
                        exit_reason = "STOP_LOSS"
                    elif user_state['take_profit_level'] is not None and current_bar['high'] >= user_state['take_profit_level']:
                        triggered = True
                        exit_price = user_state['take_profit_level']
                        exit_reason = "TAKE_PROFIT"

                elif user_state['position_direction'] == -1: # SHORT POSITION
                    if user_state['stop_loss_level'] is not None and current_bar['high'] >= user_state['stop_loss_level']:
                        triggered = True
                        exit_price = user_state['stop_loss_level']
                        exit_reason = "STOP_LOSS"
                    elif user_state['take_profit_level'] is not None and current_bar['low'] <= user_state['take_profit_level']:
                        triggered = True
                        exit_price = user_state['take_profit_level']
                        exit_reason = "TAKE_PROFIT"

                if triggered:
                    net_pnl_usd = self._calculate_pnl_for_user(user_state, exit_price)
                    user_state['equity'] += net_pnl_usd
                    
                    exit_message = (
                        f"({user_id}) 🛑 AUTO-FILLED: {exit_reason} hit at {exit_price:.2f}. "
                        f"Realized PnL: ${net_pnl_usd:.2f}"
                    )
                    self._reset_position_for_user(user_id)


        # --- ENFORCE BATTLE RULES (Drawdown) ---
        if self._check_drawdown():
            return self.get_state(status=self.status, exit_message=exit_message)
        
        return self.get_state(exit_message=exit_message)

    def execute_market_order(self, action: str, size: Optional[int] = None, sl: Optional[float] = None, tp: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """
        Processes a trade entry or exit (triggered by BUY, SELL, CLOSE buttons).
        Requires 'user_id' from kwargs.
        """
        target_user_id = kwargs.get('user_id')
        if not target_user_id or target_user_id not in self.active_traders:
             return {"error": "User ID is required or invalid for this battle."}
        
        user_state = self.active_traders[target_user_id]
        
        traded_asset = kwargs.get('traded_asset', self.asset) 
        traded_rules = get_asset_rules(traded_asset)
        
        if self.current_index + 1 >= self.total_bars:
            return {"error": "Cannot execute: End of data reached."}
            
        next_bar = self.all_data[traded_asset].iloc[self.current_index + 1]
        base_price = next_bar['open']
        
        response = {"action": action, "result": "Failed"}
        slippage_points = traded_rules['slippage_points']

        # --- EXIT LOGIC (Manual Close) ---
        if action == 'CLOSE' and user_state['in_position']:
            
            if traded_asset != self.asset:
                 response["error"] = f"Cannot close {traded_asset}: Position is currently open in {self.asset}."
                 return response
                 
            # Apply Slippage 
            if user_state['position_direction'] == 1: 
                final_exit_price = base_price - slippage_points
            else:
                final_exit_price = base_price + slippage_points
                
            net_pnl_usd = self._calculate_pnl_for_user(user_state, final_exit_price)
            user_state['equity'] += net_pnl_usd
            self._reset_position_for_user(target_user_id) # Reset using user_id
            
            response.update({
                "result": "Closed", 
                "pnl_usd": round(net_pnl_usd, 2), 
                "new_equity": round(user_state['equity'], 2)
            })

        # --- ENTRY LOGIC (Buy or Sell) ---
        elif action in ('BUY', 'SELL') and not user_state['in_position']:
            
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

            # 2. VALIDATE SL/TP AGAINST THE CALCULATED ENTRY PRICE
            is_invalid = False
            if sl is not None:
                if (direction == 1 and sl >= final_entry_price): 
                    is_invalid = True
                elif (direction == -1 and sl <= final_entry_price): 
                    is_invalid = True
            
            if tp is not None:
                if (direction == 1 and tp <= final_entry_price): 
                    is_invalid = True
                elif (direction == -1 and tp >= final_entry_price): 
                    is_invalid = True

            if is_invalid:
                response["error"] = "Invalid SL and/or TP: SL must be set against direction, TP must be set in favor of direction."
                return response
                
            # 3. Set State (Success)
            user_state['in_position'] = True
            user_state['position_direction'] = direction
            user_state['entry_price_points'] = final_entry_price
            user_state['active_position_size'] = entry_size 
            user_state['stop_loss_level'] = sl
            user_state['take_profit_level'] = tp
            user_state['position_asset'] = traded_asset
            
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
        """Formats and returns the essential battle state data, including dual-asset prices and PnL per user."""
        
        if self.status != "RUNNING":
             status = self.status
             
        # Use .get() to safely pull synchronized asset data
        bar_es = self.all_data.get('ES').iloc[self.current_index]
        bar_nq = self.all_data.get('NQ').iloc[self.current_index]
        
        # --- CRITICAL: CALCULATE P&L FOR EACH TRADER BEFORE RETURNING ---
        for user_id, state in self.active_traders.items():
            if state['in_position']:
                # The asset the user is actively holding is stored in their state dictionary
                asset_to_check = state['position_asset'] 
                
                # Retrieve the bar and rules for the asset the user is holding
                current_bar = self.all_data.get(asset_to_check).iloc[self.current_index]
                current_rules = get_asset_rules(asset_to_check)
                
                # Calculate PnL points based on the current close price
                pnl_points = (current_bar['close'] - state['entry_price_points']) * state['position_direction']
                
                # Convert to USD using the specific multiplier and size
                unrealized_pnl_usd = pnl_points * current_rules['multiplier'] * state['active_position_size']
                
                # Update the state dictionary with the PnL
                state['unrealized_pnl_usd'] = round(unrealized_pnl_usd, 2)
                state['position_asset_symbol'] = asset_to_check # Symbol for display
            else:
                state['unrealized_pnl_usd'] = 0.0
                state['position_asset_symbol'] = 'FLAT'
        # --- END P&L CALCULATION LOOP ---

        return {
            "battle_id": self.id,
            "user_ids": self.user_ids, 
            "status": status if status else self.status,
            "exit_notification": exit_message,
            "bar_data": {
                "timestamp": bar_es.name.strftime('%Y-%m-%d %H:%M:%S'),
                "close_es": round(bar_es['close'], 2), 
                "close_nq": round(bar_nq['close'], 2),
            },
            # Returns the full list of updated user states, including the PnL
            "active_traders": self.active_traders 
        }