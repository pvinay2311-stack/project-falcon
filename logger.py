import csv
import os


class TradeLogger:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fields = [
            "received_at",
            "action",
            "symbol",
            "price",
            "strategy",
            "tradingview_time",
            "decision",
            "reason"
        ]

        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()

    def log(self, row: dict):
        with open(self.file_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writerow(row)
