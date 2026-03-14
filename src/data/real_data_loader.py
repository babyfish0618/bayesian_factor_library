"""
真实数据加载器（CSV）。

目标:
- 对齐当前模拟导出格式（`data/sim_progress_demo`）；
- 输出引擎可直接消费的统一面板结构；
- 在缺失值、重复记录、字段错误时给出明确错误。

输入格式（long table）:
- daily returns: `end_date,stock_code,rtn`
- factor file: `end_date,stock_code,score`
- pool file (optional): `end_date,stock_code,in_pool`
"""

import csv
import glob
import logging
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


LOGGER = logging.getLogger(__name__)


@dataclass
class _AlignedAxis:
    """统一面板轴信息。"""

    dates: List[str]
    stocks: List[str]
    date_index: Dict[str, int]
    stock_index: Dict[str, int]


class RealDataLoader:
    """从本地 CSV 读取收益、因子暴露与股票池。

    参数
    ----------
    daily_returns_file : str
        `base/daily_returns.csv` 路径。
    factors_dir : str
        因子文件目录，每个文件对应一个因子。
    pool_file : str, optional
        股票池文件路径。若不提供，则默认“有收益记录即在池”。
    factor_glob : str
        因子文件匹配模式，默认 `*.csv`。
    """

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
        """读取并对齐为统一面板结构。

        Returns
        -------
        Dict[str, object]
            - dates: List[str]
            - stock_codes: List[str]
            - returns: ndarray[stocks, dates]
            - in_pool: ndarray[stocks, dates] (bool)
            - factor_scores: Dict[factor_id, ndarray[stocks, dates]]
        """
        axis, returns = self._load_daily_returns()
        in_pool = self._load_pool(axis, returns)
        factor_scores = self._load_factor_scores(axis)
        return {
            "dates": axis.dates,
            "stock_codes": axis.stocks,
            "returns": returns,
            "in_pool": in_pool,
            "factor_scores": factor_scores,
        }

    @staticmethod
    def _read_rows(path: str) -> Iterable[Dict[str, str]]:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    @staticmethod
    def _require_columns(path: str, columns: Iterable[str], row: Dict[str, str]) -> None:
        missing = [c for c in columns if c not in row]
        if missing:
            raise ValueError(f"{path} 缺少列: {missing}")

    @staticmethod
    def _to_float(value: str, *, path: str, col: str, allow_nan: bool = True) -> float:
        try:
            out = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{path} 列 `{col}` 存在非法数值: {value!r}")
        if not allow_nan and (math.isnan(out) or math.isinf(out)):
            raise ValueError(f"{path} 列 `{col}` 不允许 NaN/Inf: {value!r}")
        return out

    @staticmethod
    def _to_bool(value: str) -> bool:
        v = str(value).strip().lower()
        return v in {"1", "true", "t", "yes", "y"}

    def _load_daily_returns(self) -> Tuple[_AlignedAxis, np.ndarray]:
        if not os.path.exists(self.daily_returns_file):
            raise FileNotFoundError(f"daily returns file not found: {self.daily_returns_file}")

        rows: List[Tuple[str, str, float]] = []
        date_set = set()
        stock_set = set()

        for row in self._read_rows(self.daily_returns_file):
            self._require_columns(self.daily_returns_file, ("end_date", "stock_code", "rtn"), row)
            d = str(row["end_date"]).strip()
            s = str(row["stock_code"]).strip()
            r = self._to_float(row["rtn"], path=self.daily_returns_file, col="rtn", allow_nan=False)
            if not d or not s:
                continue
            rows.append((d, s, r))
            date_set.add(d)
            stock_set.add(s)

        if not rows:
            raise ValueError(f"{self.daily_returns_file} 没有有效记录")

        dates = sorted(date_set)
        stocks = sorted(stock_set)
        axis = _AlignedAxis(
            dates=dates,
            stocks=stocks,
            date_index={d: i for i, d in enumerate(dates)},
            stock_index={s: i for i, s in enumerate(stocks)},
        )

        arr = np.full((len(stocks), len(dates)), np.nan, dtype=float)
        dup_count = 0
        for d, s, r in rows:
            i = axis.stock_index[s]
            j = axis.date_index[d]
            if not np.isnan(arr[i, j]):
                dup_count += 1
            arr[i, j] = r
        if dup_count > 0:
            LOGGER.warning("daily_returns 存在重复键 (end_date, stock_code)，已使用最后一条覆盖: %d", dup_count)

        return axis, arr

    def _load_pool(self, axis: _AlignedAxis, returns: np.ndarray) -> np.ndarray:
        # 默认策略：收益可用即视为在池；与真实数据常见“停牌/缺失收益”兼容。
        if not self.pool_file:
            return ~np.isnan(returns)
        if not os.path.exists(self.pool_file):
            raise FileNotFoundError(f"pool file not found: {self.pool_file}")

        arr = np.zeros((len(axis.stocks), len(axis.dates)), dtype=bool)
        seen = np.zeros((len(axis.stocks), len(axis.dates)), dtype=bool)
        dup_count = 0

        for row in self._read_rows(self.pool_file):
            self._require_columns(self.pool_file, ("end_date", "stock_code", "in_pool"), row)
            d = str(row["end_date"]).strip()
            s = str(row["stock_code"]).strip()
            if d not in axis.date_index or s not in axis.stock_index:
                continue
            i = axis.stock_index[s]
            j = axis.date_index[d]
            if seen[i, j]:
                dup_count += 1
            seen[i, j] = True
            arr[i, j] = self._to_bool(row["in_pool"])

        if dup_count > 0:
            LOGGER.warning("pool 文件存在重复键 (end_date, stock_code)，已使用最后一条覆盖: %d", dup_count)

        # 常见问题: pool 文件时间跨度短于收益/因子，导致后半段全部 out-of-pool。
        date_covered = np.sum(np.any(seen, axis=0))
        if date_covered < len(axis.dates):
            LOGGER.warning(
                "pool 日期覆盖不足: covered_dates=%d total_dates=%d; "
                "未覆盖日期将被视为不在池内，可能导致 OOS 评估为 0。",
                int(date_covered),
                int(len(axis.dates)),
            )

        return arr

    def _load_factor_scores(self, axis: _AlignedAxis) -> Dict[str, np.ndarray]:
        if not os.path.isdir(self.factors_dir):
            raise FileNotFoundError(f"factors dir not found: {self.factors_dir}")

        factor_files = sorted(glob.glob(os.path.join(self.factors_dir, self.factor_glob)))
        if not factor_files:
            raise ValueError(f"no factor files found in {self.factors_dir} with glob {self.factor_glob}")

        out: Dict[str, np.ndarray] = {}
        for path in factor_files:
            factor_id = os.path.splitext(os.path.basename(path))[0]
            arr = np.full((len(axis.stocks), len(axis.dates)), np.nan, dtype=float)
            dup_count = 0

            for row in self._read_rows(path):
                self._require_columns(path, ("end_date", "stock_code", "score"), row)
                d = str(row["end_date"]).strip()
                s = str(row["stock_code"]).strip()
                if d not in axis.date_index or s not in axis.stock_index:
                    continue
                i = axis.stock_index[s]
                j = axis.date_index[d]
                if not np.isnan(arr[i, j]):
                    dup_count += 1
                arr[i, j] = self._to_float(row["score"], path=path, col="score", allow_nan=True)

            if dup_count > 0:
                LOGGER.warning(
                    "factor `%s` 存在重复键 (end_date, stock_code)，已使用最后一条覆盖: %d",
                    factor_id,
                    dup_count,
                )
            if np.isnan(arr).all():
                LOGGER.warning("factor `%s` 与收益面板没有重合样本，已保留但全为 NaN", factor_id)
            out[factor_id] = arr

        return out
