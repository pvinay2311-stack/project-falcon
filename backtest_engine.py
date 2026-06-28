import pandas as pd


class FalconBacktester:
    def __init__(self, contract_multiplier=50, stop_points=10, target_points=20):
        self.contract_multiplier = contract_multiplier
        self.stop_points = stop_points
        self.target_points = target_points

    def run_orb_backtest(self, csv_path: str):
        df = pd.read_csv(csv_path)

        required = {"time", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")

        df["time"] = pd.to_datetime(df["time"])
        df["date"] = df["time"].dt.date
        results = []

        for day, group in df.groupby("date"):
            group = group.sort_values("time")
            orb = group[(group["time"].dt.time >= pd.to_datetime("09:30").time()) &
                        (group["time"].dt.time <= pd.to_datetime("09:45").time())]

            trade_window = group[(group["time"].dt.time > pd.to_datetime("09:45").time()) &
                                 (group["time"].dt.time <= pd.to_datetime("11:30").time())]

            if orb.empty or trade_window.empty:
                continue

            orb_high = orb["high"].max()
            orb_low = orb["low"].min()
            position = None

            for _, row in trade_window.iterrows():
                if position is None:
                    if row["close"] > orb_high:
                        entry = row["close"]
                        position = {"side": "LONG", "entry": entry, "stop": entry - self.stop_points, "target": entry + self.target_points, "time": row["time"]}
                    elif row["close"] < orb_low:
                        entry = row["close"]
                        position = {"side": "SHORT", "entry": entry, "stop": entry + self.stop_points, "target": entry - self.target_points, "time": row["time"]}
                else:
                    if position["side"] == "LONG":
                        if row["low"] <= position["stop"]:
                            exit_price = position["stop"]
                        elif row["high"] >= position["target"]:
                            exit_price = position["target"]
                        else:
                            continue
                        pnl = (exit_price - position["entry"]) * self.contract_multiplier
                    else:
                        if row["high"] >= position["stop"]:
                            exit_price = position["stop"]
                        elif row["low"] <= position["target"]:
                            exit_price = position["target"]
                        else:
                            continue
                        pnl = (position["entry"] - exit_price) * self.contract_multiplier

                    results.append({"date": str(day), "side": position["side"], "entry_time": position["time"], "entry": position["entry"], "exit": exit_price, "pnl": pnl})
                    break

        return pd.DataFrame(results)


if __name__ == "__main__":
    bt = FalconBacktester()
    results = bt.run_orb_backtest("backtests/sample_data.csv")
    print(results)
    print("Net PnL:", results["pnl"].sum() if not results.empty else 0)
