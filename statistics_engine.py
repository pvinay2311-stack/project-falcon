def calculate_stats(trades):
    total = len(trades)

    return {
        "total_trades": total,
        "win_rate": 0,
        "profit_factor": 0,
        "net_pnl": 0
    }
