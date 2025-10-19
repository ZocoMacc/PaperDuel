import sys
import os
import time

# --- Setup Python Path for Imports ---
# Ensures 'test.py' can find the 'services' package inside the 'worker' directory.
sys.path.append(os.path.dirname(os.getcwd()))

try:
    from services.battle_service import BattleService, BATTLES
    from services.data_loader import AVAILABLE_ASSETS 
except ImportError as e:
    print(f"❌ ERROR: Could not import worker services: {e}")
    print("Check your __init__.py and ensure BATTLES is defined in battle_service.py.")
    sys.exit()

# --- TEST PARAMETERS ---
SIMULATION_BARS = 50 
TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'password'
START_ASSET = 'ES' # Default asset to start the session (ES/NQ)

# Define the two competing users for the test
USER_A_ID = 'user_1'
USER_B_ID = 'user_2_opponent' # Assuming the service creates this ID later

# --- 1. LOGIN SIMULATION (Simulated for setup) ---
print("\n--- 1. Testing User Authentication ---")
user_a_id = BattleService.authenticate_user(TEST_USERNAME, TEST_PASSWORD)
if not user_a_id:
    print(f"❌ FAILED: Authentication failed for {TEST_USERNAME}.")
    sys.exit()
print(f"✅ User A Authenticated. ID: {user_a_id}")


# --- 2. START COMPETITIVE BATTLE SIMULATION ---
print("\n--- 2. Starting Dual Battle Session (Syncing both users to the same data) ---")
BATTLE_USERS = [USER_A_ID, USER_B_ID] # Pass a list of users
battle_info = BattleService.start_new_battle(START_ASSET, BATTLE_USERS)

if 'error' in battle_info:
    print(f"❌ FAILED to start battle: {battle_info['error']}")
    sys.exit()

battle_id = battle_info['battle_id']
current_battle: BattleService = BATTLES[battle_id]

print(f"✅ Battle Started. ID: {battle_id}, Asset: {START_ASSET}")
print(f"Users in Battle: {BATTLE_USERS}")


# --- 3. INTERACTIVE TRADING LOOP ---
print("\n--- 3. ENTERING INTERACTIVE MODE ---")

# Run 2 bars initially
current_battle.advance_bar()
current_battle.advance_bar()

# NEW COMMAND FORMAT INSTRUCTIONS
print("\nCOMMAND FORMATS:")
print("  - Next Bar: N")
print("  - Buy: B <size> <asset> <user> [SL] [TP] (e.g., B 5 NQ A 24650 24800)")
print("  - Sell: S <size> <asset> <user> [SL] [TP]")
print("  - Close: C <user>")


while current_battle.status == "RUNNING":
    
    # 3a. Get Current State
    state = current_battle.get_state()
    bar = state['bar_data']
    
    # --- UPDATED PRINT STATEMENT (Shows DUAL ASSET + DUAL USER STATE) ---
    print("\n----------------------------------------------------------------------")
    print(f" TIME: {bar['timestamp']}")
    print(f" CLOSE: ES {bar['close_es']:.2f} | NQ {bar['close_nq']:.2f}")
    
    # Print Individual User Stats
    for user_id in BATTLE_USERS:
        stats = current_battle.active_traders.get(user_id)
        if stats:
            user_alias = 'A' if user_id == USER_A_ID else 'B'
            
            # The PnL is now directly available inside the stats dictionary (thanks to the logic in battle_service.py)
            unrealized_pnl = stats['unrealized_pnl_usd']
            
            # Use the currently tracked asset for the display
            position_status = current_battle.asset if stats['active_position_size'] > 0 else 'FLAT'

            print(f"  [{user_alias}] EQ: ${stats['equity']:.2f} | POS: {stats['active_position_size']} contracts ({position_status}) | PnL: ${unrealized_pnl:.2f}")
            
            if stats['in_position']:
                print(f"    ENTRY: {stats['entry_price_points']:.2f} | SL: {stats['stop_loss_level']} | TP: {stats['take_profit_level']}")

    # Check and Print Auto-Exit Notification
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
        # --- Handle Entry Command: B/S <size> <asset> <user> [SL] [TP] ---
        try:
            # 1. PARSE MANDATORY SIZE (index 1), ASSET (index 2), and USER (index 3)
            size = int(user_input[1])
            traded_asset = user_input[2].upper()
            user_alias = user_input[3].upper() # A or B
            
            # Map alias to ID
            target_user_id = USER_A_ID if user_alias == 'A' else (USER_B_ID if user_alias == 'B' else None)

            if target_user_id is None:
                print("   >>> FAILED: User must be A or B.")
                continue
            if traded_asset not in AVAILABLE_ASSETS:
                print(f"   >>> FAILED: Asset {traded_asset} is invalid. Use ES or NQ.")
                continue

            # 2. PARSE OPTIONAL SL/TP
            sl = float(user_input[4]) if len(user_input) > 4 else None
            tp = float(user_input[5]) if len(user_input) > 5 else None

            # 3. EXECUTE ORDER - Passing the target user's ID
            action_name = 'BUY' if action == 'B' else 'SELL'
            result = current_battle.execute_market_order(
                action_name, 
                size=size, 
                sl=sl, 
                tp=tp,
                user_id=target_user_id, # CRITICAL: Identify the trader
                traded_asset=traded_asset 
            )
            
            if 'Executed' in result.get('result', ''):
                current_battle.advance_bar()
                
            print(f"   >>> TRADE RESULT for {user_alias}: {result.get('error') or result.get('result')}")
            
        except IndexError:
            print("   >>> FAILED: Format: B/S <size> <asset> <user> [SL] [TP]")
        except ValueError:
            print("   >>> FAILED: Invalid number format for size, SL, or TP.")
        except Exception as e:
            print(f"   >>> UNEXPECTED ERROR: {e}")


    elif action == 'C':
        # --- Handle Close Command: C <user> ---
        try:
            user_alias = user_input[1].upper()
            target_user_id = USER_A_ID if user_alias == 'A' else (USER_B_ID if user_alias == 'B' else None)

            if target_user_id is None:
                print("   >>> FAILED: User must be A or B.")
                continue
            
            result = current_battle.execute_market_order('CLOSE', user_id=target_user_id)
            
            if 'Closed' in result.get('result', ''):
                current_battle.advance_bar()

            print(f"   >>> TRADE RESULT for {user_alias}: {result.get('error') or result.get('result')} | PnL: ${result.get('pnl_usd', 0):.2f}")
        
        except IndexError:
             print("   >>> FAILED: Format: C <user> (e.g., C A)")
        except Exception as e:
            print(f"   >>> UNEXPECTED ERROR: {e}")

            
    else:
        print("Invalid command. Use N, B, S, C, or X.")


# --- 4. FINAL RESULTS ---
final_state = current_battle.get_state()
final_equity_a = current_battle.active_traders[USER_A_ID]['equity']
final_equity_b = current_battle.active_traders[USER_B_ID]['equity']
starting_equity = 100000.0

print("\n--- 4. Final Battle Summary ---")
print(f"STATUS: {final_state['status']}")
print(f"User A Final P&L: ${(final_equity_a - starting_equity):.2f} (Equity: ${final_equity_a:.2f})")
print(f"User B Final P&L: ${(final_equity_b - starting_equity):.2f} (Equity: ${final_equity_b:.2f})")