import sys
import os
import time

# --- Setup Python Path for Imports ---
sys.path.append(os.path.dirname(os.getcwd()))

try:
    from services.battle_service import BattleService, BATTLES
    from services.data_loader import AVAILABLE_ASSETS 
except ImportError as e:
    print(f"❌ ERROR: Could not import worker services: {e}")
    sys.exit()

# --- TEST PARAMETERS ---
SIMULATION_BARS = 50 
TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'password'
START_ASSET = 'ES' # Default asset to start the session

# --- 1. LOGIN SIMULATION ---
print("\n--- 1. Testing User Authentication ---")
user_id = BattleService.authenticate_user(TEST_USERNAME, TEST_PASSWORD)
if not user_id:
    print(f"❌ FAILED: Authentication failed for {TEST_USERNAME}.")
    sys.exit()
print(f"✅ User Authenticated. User ID: {user_id}")


# --- 2. START BATTLE SIMULATION ---
print("\n--- 2. Starting Battle Session (Default ES) ---")
battle_info = BattleService.start_new_battle(START_ASSET, user_id)
if 'error' in battle_info:
    print(f"❌ FAILED to start battle: {battle_info['error']}")
    sys.exit()

battle_id = battle_info['battle_id']
current_battle: BattleService = BATTLES[battle_id]

print(f"✅ Battle Started. ID: {battle_id}, Asset: {START_ASSET}")
print("--- Session Rules: Max Drawdown 5.0% ---")


# --- 3. INTERACTIVE TRADING LOOP ---
print("\n--- 3. ENTERING INTERACTIVE MODE ---")

# Run 2 bars initially
current_battle.advance_bar()
current_battle.advance_bar()

# NEW COMMAND FORMAT INSTRUCTIONS
print("\nCOMMAND FORMATS:")
print("  - Next Bar: N")
print("  - Buy: B <size> <asset> [SL price] [TP price] (e.g., B 5 NQ 24650 24800)")
print("  - Sell: S <size> <asset> [SL price] [TP price]")
print("  - Close: C")

while current_battle.status == "RUNNING":
    
    # 3a. Get Current State
    state = current_battle.get_state()
    bar = state['bar_data']
    stats = state['stats']
    
    # --- UPDATED PRINT STATEMENT ---
    print("\n----------------------------------------------------------------------")
    print(f" TIME: {bar['timestamp']}")
    print(f" CLOSE: ES {bar['close_es']:.2f} | NQ {bar['close_nq']:.2f} | EQUITY: ${stats['equity']:.2f}")
    print(f" POS: {stats['position_size']} contracts ({stats['position_asset']}) | PnL: ${stats['unrealized_pnl_usd']:.2f}")
    print(f" ENTRY: {stats['entry_price']:.2f} | SL: {stats['sl_level']} | TP: {stats['tp_level']}")
    
    # --- Check and Print Auto-Exit Notification ---
    if state['exit_notification']:
        print(f"\n📢 {state['exit_notification']}")
        
    # --- END UPDATED PRINT STATEMENT ---

    # 3b. Read input and split it into parts
    user_input = input("COMMAND (N, B, S, C, X): ").split()
    
    if not user_input:
        continue

    action = user_input[0].upper()
    
    if action == 'X':
        print("\n--- Test Manually Halted ---")
        break
    
    if action == 'N':
        current_battle.advance_bar()
        
    elif action in ('B', 'S'):
        # --- Handle Entry Command: B/S <size> <asset> [SL] [TP] ---
        try:
            # 1. PARSE MANDATORY SIZE (index 1) AND ASSET (index 2)
            size = int(user_input[1])
            traded_asset = user_input[2].upper()

            if traded_asset not in AVAILABLE_ASSETS:
                print(f"   >>> FAILED: Asset {traded_asset} is invalid. Use ES or NQ.")
                continue

            # 2. PARSE OPTIONAL SL/TP
            sl = float(user_input[3]) if len(user_input) > 3 else None
            tp = float(user_input[4]) if len(user_input) > 4 else None

            # 3. EXECUTE ORDER
            action_name = 'BUY' if action == 'B' else 'SELL'
            result = current_battle.execute_market_order(
                action_name, 
                size=size, 
                sl=sl, 
                tp=tp,
                traded_asset=traded_asset 
            )
            
            if 'Executed' in result.get('result', ''):
                current_battle.advance_bar()
                
            print(f"   >>> TRADE RESULT: {result.get('error') or result.get('result')}")
            
        except IndexError:
            print("   >>> FAILED: Format: B/S <size> <asset> [SL] [TP] (Asset and Size are mandatory!)")
        except ValueError:
            print("   >>> FAILED: Invalid number format (Size must be integer; Prices must be numbers).")
        except Exception as e:
            print(f"   >>> UNEXPECTED ERROR: {e}")


    elif action == 'C':
        # --- Handle Close Command ---
        result = current_battle.execute_market_order('CLOSE')
        
        if 'Closed' in result.get('result', ''):
            current_battle.advance_bar()

        print(f"   >>> TRADE RESULT: {result.get('error') or result.get('result')} | PnL: ${result.get('pnl_usd', 0):.2f}")
            
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