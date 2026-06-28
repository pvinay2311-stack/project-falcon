def calculate_stats(trades):
    """Calculate trading statistics from closed trades"""
    closed = []

    for t in trades:
        pnl = t[9] if len(t) > 9 else None  # P&L column
        if pnl is not None:
            closed.append(float(pnl))

    total = len(trades)
    wins = [p for p in closed if p > 0]
    losses = [p for p in closed if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "total_trades": total,
        "closed_trades": len(closed),
        "win_rate": round((len(wins) / len(closed)) * 100, 2) if closed else 0,
        "net_pnl": round(sum(closed), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    }
