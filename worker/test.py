# test file
import sys
import os
import time

# --- Setup Python Path for Imports ---
# This ensures 'test.py' can find the 'services' package inside the 'worker' directory.
sys.path.append(os.path.dirname(os.getcwd()))

try:
    from services.battle_service import BattleService
    from services.battle_service import BATTLES # Needed to retrieve the battle instance
except ImportError as e:
    print(f"❌ ERROR: Could not import worker services: {e}")
    print("Ensure you are running this script from the project root (PaperDuel/).")
    sys.exit()

# --- TEST PARAMETERS ---
TEST_ASSET = 'NQ' # Test the NQ contract
TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'password'

# --- 1. LOGIN SIMULATION ---
print("\n--- 1. Testing User Authentication ---")
user_id = BattleService.authenticate_user(TEST_USERNAME, TEST_PASSWORD)

if not user_id:
    print(f"❌ FAILED: Authentication failed for {TEST_USERNAME}.")
    sys.exit()

print(f"✅ User Authenticated. User ID: {user_id}")


# --- 2. START BATTLE SIMULATION ---
print("\n--- 2. Starting Battle Session ---")
battle_info = BattleService.start_new_battle(TEST_ASSET, user_id)

if 'error' in battle_info:
    print(f"❌ FAILED to start battle: {battle_info['error']}")
    sys.exit()

battle_id = battle_info['battle_id']
current_battle: BattleService = BATTLES[battle_id]

print(f"✅ Battle Started. ID: {battle_id}, Asset: {TEST_ASSET}")
print("--- Session Rules: Max Drawdown 5.0% ---")

# --- 3. INTERACTIVE TRADING LOOP ---
print("\n--- 3. ENTERING INTERACTIVE MODE (Simulated TradingView Playback) ---")

# Run 2 bars initially to show the first bar of data
current_battle.advance_bar()
current_battle.advance_bar()

# NEW INSTRUCTIONS FOR USER INPUT
print("\nCOMMAND FORMATS:")
print("  - Next Bar: N")
print("  - Buy: B <size> [SL price] [TP price] (e.g., B 5 24650 24800)")
print("  - Sell: S <size> [SL price] [TP price]")
print("  - Close: C")

while current_battle.status == "RUNNING":
    
    # 3a. Get Current State
    state = current_battle.get_state()
    bar = state['bar_data']
    stats = state['stats']
    
    print("\n----------------------------------------------------------------------")
    print(f" BAR: {bar['timestamp']} | CLOSE: {bar['close']:.2f} | EQUITY: ${stats['equity']:.2f}")
    print(f" POS: {stats['position_size']} contracts ({'LONG' if stats['position_direction'] == 1 else ('SHORT' if stats['position_direction'] == -1 else 'FLAT')}) | ENTRY: {stats['entry_price']:.2f}")
    print(f" SL: {stats['sl_level']} | TP: {stats['tp_level']}")
    
    # 3b. Read input and split it into parts
    user_input = input("COMMAND (N, B, S, C, X): ").split()
    
    if not user_input:
        continue # Loop again if nothing was entered

    action = user_input[0].upper()
    
    if action == 'X':
        print("\n--- Test Manually Halted ---")
        break
    
    if action == 'N':
        current_battle.advance_bar()
        
    elif action in ('B', 'S'):
        # --- Handle Entry Command: B/S <size> [SL] [TP] ---
        try:
            # Size is MANDATORY (index 1)
            size = int(user_input[1])
            # SL/TP are OPTIONAL (index 2 and 3)
            sl = float(user_input[2]) if len(user_input) > 2 else None
            tp = float(user_input[3]) if len(user_input) > 3 else None

            result = current_battle.execute_market_order(action, size=size, sl=sl, tp=tp)
            
            # Advance the bar to see the trade filled
            if 'Executed' in result.get('result', ''):
                current_battle.advance_bar()
                
            print(f"   >>> TRADE RESULT: {result.get('message') or result.get('result')}")
            
        except IndexError:
            print("   >>> FAILED: Position size is mandatory. Format: B <size>")
        except ValueError:
            print("   >>> FAILED: Invalid number format for size, SL, or TP.")

    elif action == 'C':
        # --- Handle Close Command ---
        result = current_battle.execute_market_order('CLOSE')
        
        # Advance the bar to see the exit fill
        if 'Closed' in result.get('result', ''):
            current_battle.advance_bar()

        print(f"   >>> TRADE RESULT: {result.get('message') or result.get('result')} | PnL: ${result.get('pnl_usd', 0):.2f}")
            
    else:
        print("Invalid command. Use N, B, S, C, or X.")


# --- 4. FINAL RESULTS ---
final_state = current_battle.get_state()
final_equity = final_state['stats']['equity']
starting_equity = 100000.0

print("\n--- 4. Final Battle Summary ---")
print(f"STATUS: {final_state['status']}")
print(f"Starting Equity: ${starting_equity:.2f}")
print(f"Final Equity: ${final_equity:.2f}")
print(f"Net Profit/Loss: ${(final_equity - starting_equity):.2f}")