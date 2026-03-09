"""
因子库稳定性/早停实验

目标：
- 在更长历史和更多迭代轮次下观察因子库收敛行为
- 输出稳定性、换手率、样本外表现等曲线图
"""

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from experiments.factor_library_scenario_experiment import PerformanceTestConfig
from workflows.factor_library_iteration_engine import FactorLibraryIterationEngine


@dataclass
class StabilityExperimentConfig:
    """稳定性实验配置。"""

    scenario_name: str = "stability_long_horizon"
    random_seed: int = 42
    num_stocks: int = 1000
    num_factors: int = 100
    target_size: int = 30

    # 更长历史 + 更多轮次
    num_days: int = 1200
    update_frequency: int = 21
    num_test_rounds: Optional[int] = None
    rolling_window: int = 5

    # OOS/早停参数
    oos_horizon: int = 21
    eval_mode: str = "walk_forward_test"
    train_ratio: float = 0.7
    validation_ratio: float = 0.3
    test_ratio: float = 0.0
    early_stop_window: int = 3
    early_stop_min_rounds: int = 5
    early_stop_eps_turnover: float = 0.15
    early_stop_eps_perf: float = 0.05
    early_stop_delta: float = 0.02

    # 仿真参数
    stock_return_mu: float = 0.0005
    stock_return_sigma: float = 0.0025
    good_to_good: float = 0.72


def _to_engine_config(cfg: StabilityExperimentConfig) -> PerformanceTestConfig:
    engine_cfg = PerformanceTestConfig()
    engine_cfg.SCENARIO_NAME = cfg.scenario_name
    engine_cfg.RANDOM_SEED = cfg.random_seed
    engine_cfg.NUM_STOCKS = cfg.num_stocks
    engine_cfg.NUM_FACTORS = cfg.num_factors
    engine_cfg.TARGET_SIZE = cfg.target_size
    engine_cfg.NUM_DAYS = cfg.num_days
    engine_cfg.UPDATE_FREQUENCY = cfg.update_frequency
    engine_cfg.NUM_TEST_ROUNDS = cfg.num_test_rounds
    engine_cfg.ROLLING_WINDOW = cfg.rolling_window
    engine_cfg.OOS_HORIZON = cfg.oos_horizon
    engine_cfg.EVAL_MODE = cfg.eval_mode
    engine_cfg.TRAIN_RATIO = cfg.train_ratio
    engine_cfg.VALIDATION_RATIO = cfg.validation_ratio
    engine_cfg.TEST_RATIO = cfg.test_ratio
    engine_cfg.EARLY_STOP_WINDOW = cfg.early_stop_window
    engine_cfg.EARLY_STOP_MIN_ROUNDS = cfg.early_stop_min_rounds
    engine_cfg.EARLY_STOP_EPS_TURNOVER = cfg.early_stop_eps_turnover
    engine_cfg.EARLY_STOP_EPS_PERF = cfg.early_stop_eps_perf
    engine_cfg.EARLY_STOP_DELTA = cfg.early_stop_delta
    engine_cfg.STOCK_RETURN_MU = cfg.stock_return_mu
    engine_cfg.STOCK_RETURN_SIGMA = cfg.stock_return_sigma

    engine_cfg.TRANSITION_PROBS = dict(engine_cfg.TRANSITION_PROBS)
    engine_cfg.TRANSITION_PROBS["good"] = dict(engine_cfg.TRANSITION_PROBS["good"])
    engine_cfg.TRANSITION_PROBS["good"]["good"] = cfg.good_to_good
    residual = max(1.0 - cfg.good_to_good, 0.0)
    base_mid_bad = 0.17 + 0.03
    engine_cfg.TRANSITION_PROBS["good"]["medium"] = residual * (0.17 / base_mid_bad)
    engine_cfg.TRANSITION_PROBS["good"]["bad"] = residual * (0.03 / base_mid_bad)
    return engine_cfg


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize(values: List[float], cap: float = 3.0) -> List[float]:
    out = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        val = max(0.0, v)
        out.append(min(val, cap))
    return out


def _read_round_summary(round_summary_csv: str) -> Dict[int, Dict[str, int]]:
    round_map = {}
    if not round_summary_csv or not os.path.exists(round_summary_csv):
        return round_map
    with open(round_summary_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = int(row["round"])
            round_map[rid] = {
                "selected_good": int(row.get("selected_good", 0)),
                "selected_medium": int(row.get("selected_medium", 0)),
                "selected_bad": int(row.get("selected_bad", 0)),
                "selected_success_total": int(row.get("selected_success_total", 0)),
                "selected_failure_total": int(row.get("selected_failure_total", 0)),
            }
    return round_map


def _svg_polyline(
    xs: List[float],
    ys: List[Optional[float]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    left: int,
    top: int,
    width: int,
    height: int,
    color: str,
) -> str:
    points = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = left + (x - x_min) / (x_max - x_min + 1e-8) * width
        py = top + height - (y - y_min) / (y_max - y_min + 1e-8) * height
        points.append(f"{px:.2f},{py:.2f}")
    if not points:
        return ""
    return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}" />'


def _draw_panel(
    title: str,
    xs: List[float],
    series: List[Dict],
    panel_x: int,
    panel_y: int,
    panel_w: int,
    panel_h: int,
) -> str:
    margin_l, margin_r, margin_t, margin_b = 42, 16, 24, 28
    left = panel_x + margin_l
    top = panel_y + margin_t
    width = panel_w - margin_l - margin_r
    height = panel_h - margin_t - margin_b

    all_vals = []
    for s in series:
        vals = [v for v in s["y"] if v is not None]
        all_vals.extend(vals)
    if not all_vals:
        y_min, y_max = 0.0, 1.0
    else:
        y_min = min(all_vals)
        y_max = max(all_vals)
        if abs(y_max - y_min) < 1e-9:
            y_min -= 1.0
            y_max += 1.0

    x_min, x_max = min(xs), max(xs)
    parts = []
    parts.append(
        f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" fill="white" stroke="#dddddd" />'
    )
    parts.append(f'<text x="{panel_x + 8}" y="{panel_y + 16}" font-size="13" fill="#222222">{title}</text>')
    parts.append(
        f'<line x1="{left}" y1="{top + height}" x2="{left + width}" y2="{top + height}" stroke="#999999" stroke-width="1" />'
    )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height}" stroke="#999999" stroke-width="1" />')

    # 简单网格
    for i in range(1, 4):
        gy = top + i * height / 4.0
        parts.append(f'<line x1="{left}" y1="{gy:.2f}" x2="{left + width}" y2="{gy:.2f}" stroke="#f1f1f1" />')

    for s in series:
        parts.append(
            _svg_polyline(
                xs=xs,
                ys=s["y"],
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                left=left,
                top=top,
                width=width,
                height=height,
                color=s["color"],
            )
        )

    # 图例
    legend_x = panel_x + 10
    legend_y = panel_y + panel_h - 10
    for i, s in enumerate(series):
        x0 = legend_x + i * 150
        parts.append(f'<line x1="{x0}" y1="{legend_y}" x2="{x0 + 20}" y2="{legend_y}" stroke="{s["color"]}" stroke-width="2" />')
        parts.append(f'<text x="{x0 + 24}" y="{legend_y + 4}" font-size="11" fill="#333333">{s["name"]}</text>')

    # 角标刻度
    parts.append(f'<text x="{left - 36}" y="{top + 10}" font-size="10" fill="#777">{y_max:.2f}</text>')
    parts.append(f'<text x="{left - 36}" y="{top + height}" font-size="10" fill="#777">{y_min:.2f}</text>')
    parts.append(f'<text x="{left}" y="{top + height + 18}" font-size="10" fill="#777">{int(x_min)}</text>')
    parts.append(f'<text x="{left + width - 8}" y="{top + height + 18}" font-size="10" fill="#777">{int(x_max)}</text>')
    return "\n".join(parts)


def _write_stability_svg(
    output_path: str,
    rounds: List[int],
    turnover: List[float],
    overlap: List[float],
    oos_sharpe: List[float],
    oos_icir: List[float],
    oos_ls: List[float],
    convergence_index: List[Optional[float]],
) -> None:
    width, height = 1300, 760
    panels = []
    panels.append(
        _draw_panel(
            title="Stability: turnover / overlap",
            xs=rounds,
            series=[
                {"name": "turnover", "y": turnover, "color": "#d1495b"},
                {"name": "overlap", "y": overlap, "color": "#2a9d8f"},
            ],
            panel_x=20,
            panel_y=20,
            panel_w=620,
            panel_h=340,
        )
    )
    panels.append(
        _draw_panel(
            title="OOS quality: Sharpe / ICIR",
            xs=rounds,
            series=[
                {"name": "oos_sharpe", "y": oos_sharpe, "color": "#264653"},
                {"name": "oos_icir", "y": oos_icir, "color": "#457b9d"},
            ],
            panel_x=660,
            panel_y=20,
            panel_w=620,
            panel_h=340,
        )
    )
    panels.append(
        _draw_panel(
            title="OOS LS mean",
            xs=rounds,
            series=[{"name": "oos_ls_mean", "y": oos_ls, "color": "#f4a261"}],
            panel_x=20,
            panel_y=390,
            panel_w=620,
            panel_h=340,
        )
    )
    panels.append(
        _draw_panel(
            title="Convergence Index (<=1 suggests stop-ready)",
            xs=rounds,
            series=[
                {"name": "conv_index", "y": convergence_index, "color": "#6a4c93"},
                {"name": "threshold=1", "y": [1.0] * len(rounds), "color": "#999999"},
            ],
            panel_x=660,
            panel_y=390,
            panel_w=620,
            panel_h=340,
        )
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa"/>
<text x="24" y="18" font-size="14" fill="#111111">Factor Library Stability Experiment</text>
{"".join(panels)}
</svg>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)


class StabilityExperimentRunner:
    """长周期稳定性实验运行器。"""

    def __init__(self, config: StabilityExperimentConfig):
        self.config = config

    def run(self) -> Dict:
        engine_cfg = _to_engine_config(self.config)
        engine = FactorLibraryIterationEngine(engine_cfg)
        results = engine.run_full_test()
        artifact = self._export_artifacts(results)
        results["stability_artifacts"] = artifact
        return results

    def _export_artifacts(self, results: Dict) -> Dict:
        round_metrics = results.get("round_iteration_metrics", [])
        rounds = [int(x["round"]) for x in round_metrics]
        turnover = [_safe_float(x.get("turnover")) for x in round_metrics]
        overlap = [_safe_float(x.get("overlap_prev")) for x in round_metrics]
        oos_sharpe = [_safe_float(x.get("oos_sharpe")) for x in round_metrics]
        oos_icir = [_safe_float(x.get("oos_icir")) for x in round_metrics]
        oos_ls = [_safe_float(x.get("oos_ls_mean")) for x in round_metrics]
        oos_excess = [_safe_float(x.get("oos_excess_vs_prevlib")) for x in round_metrics]

        # 归一化收敛指标: <=1 代表满足(或接近满足)早停单轮阈值
        d_sharpe = [None]
        d_icir = [None]
        for i in range(1, len(round_metrics)):
            d_sharpe.append(abs(oos_sharpe[i] - oos_sharpe[i - 1]))
            d_icir.append(abs(oos_icir[i] - oos_icir[i - 1]))

        turnover_norm = _normalize([v / max(self.config.early_stop_eps_turnover, 1e-8) for v in turnover])
        d_sharpe_norm = _normalize([
            (v / max(self.config.early_stop_eps_perf, 1e-8)) if v is not None else None for v in d_sharpe
        ])
        d_icir_norm = _normalize([
            (v / max(self.config.early_stop_eps_perf, 1e-8)) if v is not None else None for v in d_icir
        ])
        excess_norm = _normalize([
            max(0.0, -(v + self.config.early_stop_delta) / max(self.config.early_stop_delta, 1e-8))
            for v in oos_excess
        ])

        convergence_index = []
        for i in range(len(rounds)):
            candidates = [turnover_norm[i], excess_norm[i]]
            if d_sharpe_norm[i] is not None:
                candidates.append(d_sharpe_norm[i])
            if d_icir_norm[i] is not None:
                candidates.append(d_icir_norm[i])
            convergence_index.append(max(candidates) if candidates else None)

        tracking_output = results.get("tracking_output", {})
        round_summary = _read_round_summary(tracking_output.get("round_summary_csv", ""))
        selected_good = [round_summary.get(r, {}).get("selected_good", 0) for r in rounds]
        selected_medium = [round_summary.get(r, {}).get("selected_medium", 0) for r in rounds]
        selected_bad = [round_summary.get(r, {}).get("selected_bad", 0) for r in rounds]
        selected_success = [round_summary.get(r, {}).get("selected_success_total", 0) for r in rounds]
        selected_failure = [round_summary.get(r, {}).get("selected_failure_total", 0) for r in rounds]

        output_dir = tracking_output.get("output_dir", "outputs/performance_tracking")
        stability_dir = os.path.join(output_dir, "stability_experiment")
        os.makedirs(stability_dir, exist_ok=True)

        svg_path = os.path.join(stability_dir, "stability_convergence.svg")
        _write_stability_svg(
            output_path=svg_path,
            rounds=rounds,
            turnover=turnover,
            overlap=overlap,
            oos_sharpe=oos_sharpe,
            oos_icir=oos_icir,
            oos_ls=oos_ls,
            convergence_index=convergence_index,
        )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(stability_dir, f"stability_report_{ts}.json")
        report = {
            "scenario": self.config.scenario_name,
            "dataset_split": results.get("dataset_split", {}),
            "rounds": rounds,
            "series": {
                "turnover": turnover,
                "overlap": overlap,
                "oos_sharpe": oos_sharpe,
                "oos_icir": oos_icir,
                "oos_ls_mean": oos_ls,
                "oos_excess_vs_prevlib": oos_excess,
                "turnover_norm": turnover_norm,
                "delta_oos_sharpe_norm": d_sharpe_norm,
                "delta_oos_icir_norm": d_icir_norm,
                "excess_gap_norm": excess_norm,
                "convergence_index": convergence_index,
                "selected_good": selected_good,
                "selected_medium": selected_medium,
                "selected_bad": selected_bad,
                "selected_success_total": selected_success,
                "selected_failure_total": selected_failure,
            },
            "early_stop": results.get("early_stop", {}),
            "final_library": results.get("final_library", {}),
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return {
            "stability_output_dir": stability_dir,
            "stability_svg": svg_path,
            "stability_report_json": report_path,
        }
