"""因子库动态可视化（SVG）。"""

from typing import Dict, List, Optional


def _points(xs, ys, x_min, x_max, y_min, y_max, left, top, width, height):
    out = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = left + (x - x_min) / (x_max - x_min + 1e-8) * width
        py = top + height - (y - y_min) / (y_max - y_min + 1e-8) * height
        out.append((px, py))
    return out


def _panel(
    title: str,
    rounds: List[int],
    values: List[Optional[float]],
    color: str,
    stability_flags: List[bool],
    selected_round: Optional[int],
    last_round: Optional[int],
    x: int,
    y: int,
    w: int,
    h: int,
):
    ml, mr, mt, mb = 44, 16, 24, 30
    left = x + ml
    top = y + mt
    width = w - ml - mr
    height = h - mt - mb
    vals = [v for v in values if v is not None]
    if not vals:
        y_min, y_max = 0.0, 1.0
    else:
        y_min, y_max = min(vals), max(vals)
        if abs(y_max - y_min) < 1e-8:
            y_min -= 1.0
            y_max += 1.0
    x_min, x_max = min(rounds), max(rounds)

    out = []
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="#dddddd"/>')
    out.append(f'<text x="{x+8}" y="{y+16}" font-size="13" fill="#222">{title}</text>')
    out.append(f'<line x1="{left}" y1="{top+height}" x2="{left+width}" y2="{top+height}" stroke="#999"/>')
    out.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+height}" stroke="#999"/>')
    for i in range(1, 4):
        gy = top + i * height / 4.0
        out.append(f'<line x1="{left}" y1="{gy:.2f}" x2="{left+width}" y2="{gy:.2f}" stroke="#f1f1f1"/>')

    pts = _points(rounds, values, x_min, x_max, y_min, y_max, left, top, width, height)
    out.append(
        '<polyline fill="none" stroke="{}" stroke-width="2" points="{}"/>'.format(
            color, " ".join([f"{px:.2f},{py:.2f}" for px, py in pts])
        )
    )

    idx_map = {r: i for i, r in enumerate(rounds)}
    for r, ok in zip(rounds, stability_flags):
        if not ok:
            continue
        i = idx_map[r]
        yv = values[i]
        if yv is None:
            continue
        px, py = _points([r], [yv], x_min, x_max, y_min, y_max, left, top, width, height)[0]
        out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="white" stroke="#2a9d8f" stroke-width="2"/>')

    # 出库轮次（橙色实心圆）
    if selected_round is not None and selected_round in idx_map:
        i = idx_map[selected_round]
        yv = values[i]
        if yv is not None:
            px, py = _points([selected_round], [yv], x_min, x_max, y_min, y_max, left, top, width, height)[0]
            out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="#f4a261" stroke="#9c5b18" stroke-width="1"/>')

    # 最后一轮（蓝色方块）
    if last_round is not None and last_round in idx_map:
        i = idx_map[last_round]
        yv = values[i]
        if yv is not None:
            px, py = _points([last_round], [yv], x_min, x_max, y_min, y_max, left, top, width, height)[0]
            out.append(f'<rect x="{px-4:.2f}" y="{py-4:.2f}" width="8" height="8" fill="#457b9d" stroke="#1f4760"/>')

    out.append(f'<text x="{left-36}" y="{top+10}" font-size="10" fill="#777">{y_max:.3f}</text>')
    out.append(f'<text x="{left-36}" y="{top+height}" font-size="10" fill="#777">{y_min:.3f}</text>')
    out.append(f'<text x="{left}" y="{top+height+18}" font-size="10" fill="#777">{x_min}</text>')
    out.append(f'<text x="{left+width-8}" y="{top+height+18}" font-size="10" fill="#777">{x_max}</text>')
    return "\n".join(out)


def export_validation_dynamics_svg(
    output_path: str,
    round_metrics: List[Dict],
    selected_round: Optional[int],
    last_round: Optional[int],
    title_suffix: str = "",
) -> None:
    rounds = [int(m["round"]) for m in round_metrics]
    if not rounds:
        return
    stability_flags = [bool(m.get("stability_pass", False)) for m in round_metrics]
    stable_cnt = sum(1 for x in stability_flags if x)

    series = {
        "oos_sharpe": [float(m.get("oos_sharpe", 0.0)) for m in round_metrics],
        "oos_icir": [float(m.get("oos_icir", 0.0)) for m in round_metrics],
        "oos_ls_mean": [float(m.get("oos_ls_mean", 0.0)) for m in round_metrics],
        "turnover": [float(m.get("turnover", 0.0)) for m in round_metrics],
        "oos_excess_vs_prevlib": [float(m.get("oos_excess_vs_prevlib", 0.0)) for m in round_metrics],
        "abs_d_oos_sharpe": [None if m.get("d_oos_sharpe") is None else float(m.get("d_oos_sharpe")) for m in round_metrics],
        "abs_d_oos_icir": [None if m.get("d_oos_icir") is None else float(m.get("d_oos_icir")) for m in round_metrics],
    }
    colors = {
        "oos_sharpe": "#264653",
        "oos_icir": "#457b9d",
        "oos_ls_mean": "#f4a261",
        "turnover": "#d1495b",
        "oos_excess_vs_prevlib": "#2a9d8f",
        "abs_d_oos_sharpe": "#b56576",
        "abs_d_oos_icir": "#6a4c93",
    }
    titles = {
        "oos_sharpe": "Validation OOS Sharpe",
        "oos_icir": "Validation OOS ICIR",
        "oos_ls_mean": "Validation OOS rtn (LS mean)",
        "turnover": "Turnover",
        "oos_excess_vs_prevlib": "OOS Excess vs Prev Library",
        "abs_d_oos_sharpe": "|Δ OOS Sharpe|",
        "abs_d_oos_icir": "|Δ OOS ICIR|",
    }
    order = [
        "oos_sharpe",
        "oos_icir",
        "oos_ls_mean",
        "turnover",
        "oos_excess_vs_prevlib",
        "abs_d_oos_sharpe",
        "abs_d_oos_icir",
    ]

    rows = (len(order) + 1) // 2
    W, H = 1320, 40 + rows * 340 + 30
    panels = []
    for i, key in enumerate(order):
        row, col = divmod(i, 2)
        panels.append(
            _panel(
                title=titles[key],
                rounds=rounds,
                values=series[key],
                color=colors[key],
                stability_flags=stability_flags,
                selected_round=selected_round,
                last_round=last_round,
                x=20 + col * 640,
                y=40 + row * 340,
                w=620,
                h=320,
            )
        )

    legend_y = H - 24
    legend = []
    legend.append('<circle cx="36" cy="{}" r="4" fill="white" stroke="#2a9d8f" stroke-width="2"/>'.format(legend_y))
    legend.append('<text x="48" y="{}" font-size="11" fill="#333">stability_pass=True</text>'.format(legend_y + 4))
    legend.append('<circle cx="230" cy="{}" r="5" fill="#f4a261" stroke="#9c5b18" stroke-width="1"/>'.format(legend_y))
    legend.append('<text x="243" y="{}" font-size="11" fill="#333">selected_round (final export)</text>'.format(legend_y + 4))
    legend.append('<rect x="470" y="{}" width="8" height="8" fill="#457b9d" stroke="#1f4760"/>'.format(legend_y - 4))
    legend.append('<text x="482" y="{}" font-size="11" fill="#333">last_round</text>'.format(legend_y + 4))

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">
<rect x="0" y="0" width="{W}" height="{H}" fill="#fafafa"/>
<text x="24" y="22" font-size="14" fill="#111">Validation Dynamics {title_suffix}</text>
<text x="24" y="36" font-size="11" fill="#555">stable rounds: {stable_cnt}/{len(rounds)} | selected_round: {selected_round} | last_round: {last_round}</text>
{''.join(panels)}
{''.join(legend)}
</svg>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)


def export_test_dynamics_svg(
    output_path: str,
    round_metrics: List[Dict],
    selected_round: Optional[int],
    last_round: Optional[int],
    title_suffix: str = "",
) -> None:
    rounds = [int(m["round"]) for m in round_metrics]
    if not rounds:
        return
    stability_flags = [bool(m.get("stability_pass", False)) for m in round_metrics]
    stable_cnt = sum(1 for x in stability_flags if x)

    icir = [m.get("test_oos_icir") for m in round_metrics]
    sharpe = [m.get("test_oos_sharpe") for m in round_metrics]
    rtn = [m.get("test_oos_ls_mean") for m in round_metrics]
    # 若无测试集，直接返回空图提示
    if all(v is None for v in icir) and all(v is None for v in sharpe) and all(v is None for v in rtn):
        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="920" height="160">
<rect x="0" y="0" width="920" height="160" fill="#fafafa"/>
<text x="20" y="28" font-size="14" fill="#111">Test Dynamics</text>
<text x="20" y="56" font-size="12" fill="#555">No test split configured (TEST_RATIO=0)</text>
</svg>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg)
        return

    W, H = 1320, 560
    p1 = _panel(
        title="Test ICIR",
        rounds=rounds,
        values=[None if v is None else float(v) for v in icir],
        color="#457b9d",
        stability_flags=stability_flags,
        selected_round=selected_round,
        last_round=last_round,
        x=20,
        y=40,
        w=420,
        h=320,
    )
    p2 = _panel(
        title="Test Sharpe (LS)",
        rounds=rounds,
        values=[None if v is None else float(v) for v in sharpe],
        color="#264653",
        stability_flags=stability_flags,
        selected_round=selected_round,
        last_round=last_round,
        x=450,
        y=40,
        w=420,
        h=320,
    )
    p3 = _panel(
        title="Test rtn (LS mean)",
        rounds=rounds,
        values=[None if v is None else float(v) for v in rtn],
        color="#f4a261",
        stability_flags=stability_flags,
        selected_round=selected_round,
        last_round=last_round,
        x=880,
        y=40,
        w=420,
        h=320,
    )

    legend_y = H - 24
    legend = []
    legend.append('<circle cx="36" cy="{}" r="4" fill="white" stroke="#2a9d8f" stroke-width="2"/>'.format(legend_y))
    legend.append('<text x="48" y="{}" font-size="11" fill="#333">stability_pass=True</text>'.format(legend_y + 4))
    legend.append('<circle cx="230" cy="{}" r="5" fill="#f4a261" stroke="#9c5b18" stroke-width="1"/>'.format(legend_y))
    legend.append('<text x="243" y="{}" font-size="11" fill="#333">selected_round</text>'.format(legend_y + 4))
    legend.append('<rect x="360" y="{}" width="8" height="8" fill="#457b9d" stroke="#1f4760"/>'.format(legend_y - 4))
    legend.append('<text x="372" y="{}" font-size="11" fill="#333">last_round</text>'.format(legend_y + 4))

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">
<rect x="0" y="0" width="{W}" height="{H}" fill="#fafafa"/>
<text x="24" y="22" font-size="14" fill="#111">Test Dynamics {title_suffix}</text>
<text x="24" y="36" font-size="11" fill="#555">stable rounds: {stable_cnt}/{len(rounds)} | selected_round: {selected_round} | last_round: {last_round}</text>
{p1}{p2}{p3}
{''.join(legend)}
</svg>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)
