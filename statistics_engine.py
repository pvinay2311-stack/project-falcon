def calculate_stats(trades):
    total = len(trades)
    pnl_values = [row[9] for row in trades if len(row) > 9 and row[9] is not None]
    wins = [p for p in pnl_values if p > 0]
    losses = [p for p in pnl_values if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    net_pnl = sum(pnl_values)

    return {
        "total_trades": total,
        "closed_trades": len(pnl_values),
        "win_rate": round((len(wins) / len(pnl_values)) * 100, 2) if pnl_values else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        "net_pnl": round(net_pnl, 2)
    }
