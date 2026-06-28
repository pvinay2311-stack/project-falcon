#!/usr/bin/env python3
"""
Project Falcon Backtester CLI
Run ORB (Opening Range Breakout) backtests on OHLCV data
"""

import sys
from pathlib import Path
from backtest_engine import FalconBacktester


def main():
    # Default test data path
    csv_path = "backtests/sample_data.csv"
    
    # Allow overriding CSV path from command line
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    # Check if file exists
    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        print(f"Usage: python3 backtester.py [path_to_csv]")
        sys.exit(1)
    
    # Run backtest
    print(f"Running ORB backtest on: {csv_path}")
    print("-" * 80)
    
    bt = FalconBacktester(
        contract_multiplier=50,
        stop_points=10,
        target_points=20
    )
    
    try:
        results = bt.run_orb_backtest(csv_path)
        
        if results.empty:
            print("No trades generated from backtest.")
        else:
            print(f"\nBacktest Results ({len(results)} trades):")
            print(results.to_string())
            print("-" * 80)
            print(f"Net PnL: ${results['pnl'].sum():.2f}")
            print(f"Win Rate: {(results['pnl'] > 0).sum() / len(results) * 100:.1f}%")
            print(f"Max Win: ${results['pnl'].max():.2f}")
            print(f"Max Loss: ${results['pnl'].min():.2f}")
    
    except Exception as e:
        print(f"Error running backtest: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
