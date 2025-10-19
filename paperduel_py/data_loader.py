import pandas as pd
from typing import Dict, Any, Optional

# --- FUTURES CONTRACT CONFIGURATION ---
SLIPPAGE_TICKS = 0.5
COMMISSION_PER_SIDE = 1.25
COMMISSION_ROUND_TURN = COMMISSION_PER_SIDE * 2.0

ASSET_CONFIG: Dict[str, Any] = {
    'ES': {
        'MULTIPLIER': 50.0,
        'TICK_VALUE': 12.50,
        # Path relative to the project root where the worker is executed
        'DATA_FILE': 'data/es_minute.csv'
    },
    'NQ': {
        'MULTIPLIER': 20.0,
        'TICK_VALUE': 5.00,
        'DATA_FILE': 'data/nq_minute.csv'
    }
}

def load_asset_data(asset_symbol: str) -> Optional[pd.DataFrame]:
    """Loads OHLCV data from the corresponding CSV file."""
    if asset_symbol not in ASSET_CONFIG:
        return None

    file_path = ASSET_CONFIG[asset_symbol]['DATA_FILE']
    
    try:
        df = pd.read_csv(file_path, index_col='ts_event', parse_dates=True)
        # We only need the OHLCV columns for backtesting
        return df[['open', 'high', 'low', 'close', 'volume']].dropna()
    except FileNotFoundError:
        print(f"ERROR: Data file not found at {file_path}")
        return None

def get_asset_rules(asset_symbol: str) -> Optional[Dict[str, float]]:
    """Retrieves and calculates all financial constants for the asset."""
    if asset_symbol not in ASSET_CONFIG:
        return None

    config = ASSET_CONFIG[asset_symbol]
    
    # Calculate all required backtesting constants
    slippage_dollar = SLIPPAGE_TICKS * config['TICK_VALUE']
    
    return {
        'symbol': asset_symbol,
        'multiplier': config['MULTIPLIER'],
        'tick_value': config['TICK_VALUE'],
        'slippage_dollar': slippage_dollar,
        'slippage_points': slippage_dollar / config['MULTIPLIER'],
        'commission_round_turn': COMMISSION_ROUND_TURN,
    }

# This is a public placeholder list of available assets for the frontend/API
AVAILABLE_ASSETS = list(ASSET_CONFIG.keys())
