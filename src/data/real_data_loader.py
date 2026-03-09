"""
真实数据文件夹读取器

读取约定目录下的:
- base/daily_returns.csv
- factors/*.csv
- pools/<pool_name>.csv (可选)
"""

import csv
import glob
import os
from typing import Dict, List, Optional

import numpy as np


class RealDataLoader:
    """从本地CSV读取收益率、因子暴露、股票池。"""

    def __init__(
        self,
        daily_returns_file: str,
        factors_dir: str,
        pool_file: Optional[str] = None,
        factor_glob: str = "*.csv",
    ):
        self.daily_returns_file = daily_returns_file
        self.factors_dir = factors_dir
        self.pool_file = pool_file
        self.factor_glob = factor_glob

    def load(self) -> Dict[str, object]:
        dates, stock_codes, returns = self._load_daily_returns()
        in_pool = self._load_pool(dates, stock_codes)
        factor_scores = self._load_factor_scores(dates, stock_codes)
        return {
            "dates": dates,
            "stock_codes": stock_codes,
            "returns": returns,      # shape: [n_stocks, n_days]
            "in_pool": in_pool,      # shape: [n_stocks, n_days]
            "factor_scores": factor_scores,  # factor_id -> [n_stocks, n_days]
        }

    def _load_daily_returns(self):
        date_set = set()
        stock_set = set()
        rows = []
        with open(self.daily_returns_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row["end_date"]
                s = row["stock_code"]
                r = float(row["rtn"])
                rows.append((d, s, r))
                date_set.add(d)
                stock_set.add(s)

        dates = sorted(date_set)
        stocks = sorted(stock_set)
        d_map = {d: i for i, d in enumerate(dates)}
        s_map = {s: i for i, s in enumerate(stocks)}

        arr = np.full((len(stocks), len(dates)), np.nan, dtype=float)
        for d, s, r in rows:
            arr[s_map[s], d_map[d]] = r
        return dates, stocks, arr

    def _load_pool(self, dates: List[str], stocks: List[str]) -> np.ndarray:
        if not self.pool_file:
            return np.ones((len(stocks), len(dates)), dtype=bool)
        if not os.path.exists(self.pool_file):
            raise FileNotFoundError(f"pool file not found: {self.pool_file}")

        d_map = {d: i for i, d in enumerate(dates)}
        s_map = {s: i for i, s in enumerate(stocks)}
        arr = np.zeros((len(stocks), len(dates)), dtype=bool)

        with open(self.pool_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row.get("end_date")
                s = row.get("stock_code")
                if d not in d_map or s not in s_map:
                    continue
                val = row.get("in_pool", "0")
                arr[s_map[s], d_map[d]] = (str(val).strip() in {"1", "true", "True", "TRUE"})
        return arr

    def _load_factor_scores(self, dates: List[str], stocks: List[str]) -> Dict[str, np.ndarray]:
        d_map = {d: i for i, d in enumerate(dates)}
        s_map = {s: i for i, s in enumerate(stocks)}
        factor_files = sorted(glob.glob(os.path.join(self.factors_dir, self.factor_glob)))
        if not factor_files:
            raise ValueError(f"no factor files found in {self.factors_dir} with glob {self.factor_glob}")

        out: Dict[str, np.ndarray] = {}
        for path in factor_files:
            factor_id = os.path.splitext(os.path.basename(path))[0]
            arr = np.full((len(stocks), len(dates)), np.nan, dtype=float)
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d = row.get("end_date")
                    s = row.get("stock_code")
                    if d not in d_map or s not in s_map:
                        continue
                    arr[s_map[s], d_map[d]] = float(row["score"])
            out[factor_id] = arr
        return out
