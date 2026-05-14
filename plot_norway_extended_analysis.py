"""Plot extended Norway sensitivity and throughput-scaling results.

Run after ``norway_sensitivity.py`` and ``norway_throughput_scaling.py``.
Figures use restrained styling so they remain legible in the thesis PDF.

Plotting conventions:
- Norway monetary inputs and outputs are displayed in NOK.
- NPV axes are displayed in MNOK to avoid scientific-notation axes.
- The old ``break_even_selling_price_per_kwh`` tornado is not generated; it is
  an alias for annual break-even selling price and created duplicate figures.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import cm

DATA_DIR = Path("data")
FIG_DIR = Path("Figures") / "norway_extended"
FIG_DIR.mkdir(parents=True, exist_ok=True)

MNOK = 1_000_000.0
FIG_DPI = 260

# Keep thesis figures legible when embedded at roughly 0.9\textwidth.
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "lines.linewidth": 2.0,
    "lines.markersize": 6,
    "figure.constrained_layout.use": True,
})

# Metrics for which selling_price_per_kwh must be excluded from tornado
# charts because the plotted metric IS a break-even selling price.
_BREAK_EVEN_SELLING_PRICE_METRICS = {
    "annual_break_even_selling_price_per_kwh",
    "break_even_selling_price_per_kwh",
    "npv_break_even_selling_price_per_kwh",
}

# Sensitivity CSV values are already stored in the scenario currency. For the
# Norwegian thesis figures this means NOK, so no plot-time currency conversion
# is needed.

_PARAM_LABELS = {
    "cell_fault_rate": "Cell fault rate",
    "cell_soh_mean": "Mean cell SoH",
    "cell_soh_std": "Cell SoH std.",
    "min_remaining_energy_fraction": "Acceptance threshold",
    "purchase_price_per_kwh_nameplate": "Purchase price [NOK/kWh-nameplate]",
    "selling_price_per_kwh": "Selling price [NOK/kWh]",
    "discount_rate": "Discount rate",
}

_METRIC_LABELS = {
    "npv": "NPV [MNOK]",
    "annual_break_even_selling_price_per_kwh": "Annual break-even selling price [NOK/kWh]",
    "npv_break_even_selling_price_per_kwh": "NPV break-even selling price [NOK/kWh]",
    "break_even_purchase_price_per_unit": "Annual break-even purchase price [NOK/unit]",
}

_COMPONENT_LABELS = {
    "leaf": "Leaf module",
    "leaf_pack": "Leaf pack",
    "tesla": "Tesla module",
}

# Base values used for the one-at-a-time sensitivity sweeps. These are used
# only for plotting base-case markers on the tornado charts; changing these
# values does not change the model calculations.
_BASE_PARAMETER_VALUES = {
    "leaf": {
        "cell_fault_rate": 5e-5,
        "cell_soh_mean": 0.64,
        "cell_soh_std": 0.04,
        "min_remaining_energy_fraction": 0.55,
        "purchase_price_per_kwh_nameplate": 36.0,
        "selling_price_per_kwh": 1600.0,
        "discount_rate": 0.10,
    },
    "leaf_pack": {
        "cell_fault_rate": 5e-5,
        "cell_soh_mean": 0.64,
        "cell_soh_std": 0.04,
        "min_remaining_energy_fraction": 0.55,
        "purchase_price_per_kwh_nameplate": 36.0,
        "selling_price_per_kwh": 1600.0,
        "discount_rate": 0.10,
    },
    "tesla": {
        "cell_fault_rate": 5e-5,
        "cell_soh_mean": 0.80,
        "cell_soh_std": 0.04,
        "min_remaining_energy_fraction": 0.55,
        "purchase_price_per_kwh_nameplate": 230.0 / 5.3,
        "selling_price_per_kwh": 1400.0,
        "discount_rate": 0.10,
    },
}


def _finish_figure(fig: plt.Figure, filename: str) -> None:
    """Save a thesis figure with consistent padding and tight bounding box."""
    fig.savefig(FIG_DIR / filename, dpi=FIG_DPI, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def _style_legend(ax: plt.Axes, *, loc: str | None = None) -> None:
    """Apply consistent legend styling without covering too much plot area."""
    kwargs = {"frameon": True, "framealpha": 0.9}
    if loc is not None:
        kwargs["loc"] = loc
    ax.legend(**kwargs)


def _display_parameter_value(parameter: str, value: float) -> float:
    """Return parameter values as stored in the scenario-currency CSV."""
    return value


def _display_metric_values(values: pd.Series, metric: str) -> pd.Series:
    """Return metric values in units used by the figure axes."""
    if metric == "npv":
        return values / MNOK
    return values


def _clean_component_label(component: str) -> str:
    """Return readable component labels for sensitivity figures."""
    return _COMPONENT_LABELS.get(component, component.replace("_", " ").title())


def _clean_group_label(group: str) -> str:
    """Return readable labels for throughput component groups."""
    labels = {
        "tesla": "Tesla module",
        "leaf": "Leaf module",
        "leaf_pack_to_modules": "Leaf pack-to-modules",
        "leaf_pack_triage": "Leaf pack triage",
        "leaf_pack": "Leaf complete-pack",
    }
    return labels.get(group, group.replace("_", " ").title())


def _base_metric_value_for_parameter(
    sub: pd.DataFrame,
    component: str,
    parameter: str,
    metric: str,
) -> float | None:
    """Return the plotted metric value nearest to the base parameter setting."""
    base_value = _BASE_PARAMETER_VALUES.get(component, {}).get(parameter)
    if base_value is None or sub.empty:
        return None

    nearest_idx = (sub["value"] - base_value).abs().idxmin()
    value = sub.loc[nearest_idx, metric]
    if pd.isna(value):
        return None
    if metric == "npv":
        return float(value) / MNOK
    return float(value)


def _component_group(case: str) -> str:
    """Map throughput case names to a readable component group."""
    if case.startswith("leaf_pack_to_modules"):
        return "leaf_pack_to_modules"
    if case.startswith("leaf_pack_triage"):
        return "leaf_pack_triage"
    if case.startswith("leaf_pack"):
        return "leaf_pack"
    if case.startswith("leaf"):
        return "leaf"
    if case.startswith("tesla"):
        return "tesla"
    return "other"


def _case_sort_key(case: str) -> tuple[int, int, str]:
    """Sort cases by component and scenario severity."""
    component_order = {"tesla": 0, "leaf": 1, "leaf_pack_to_modules": 2, "leaf_pack_triage": 3, "leaf_pack": 4, "other": 5}
    scenario_order = {
        "reference": 0,
        "base": 0,
        "market": 1,
        "market_push": 1,
        "feasibility": 2,
        "optimistic": 2,
    }
    group = _component_group(case)
    idx = 99
    for name, order in scenario_order.items():
        if name in case:
            idx = order
            break
    return (component_order.get(group, 99), idx, case)


def _clean_case_label(case: str) -> str:
    """Return compact labels aligned with the thesis terminology."""
    labels = {
        "leaf_base": "Leaf module base/reference",
        "leaf_optimistic": "Leaf module optimistic process",
        "leaf_market_push": "Leaf module high-value push",
        "leaf_pack_base": "Leaf pack base/reference",
        "leaf_pack_optimistic": "Leaf pack optimistic process",
        "leaf_pack_market_push": "Leaf pack high-value push",
        "leaf_pack_to_modules_base": "Leaf pack-to-modules base/reference",
        "leaf_pack_to_modules_optimistic": "Leaf pack-to-modules optimistic process",
        "leaf_pack_to_modules_market_push": "Leaf pack-to-modules high-value push",
        "leaf_pack_triage_base": "Leaf pack triage base/reference",
        "leaf_pack_triage_optimistic": "Leaf pack triage optimistic process",
        "leaf_pack_triage_market_push": "Leaf pack triage high-value push",
        "tesla_base": "Tesla base/reference",
        "tesla_optimistic": "Tesla optimistic process",
        "tesla_market_push": "Tesla high-value push",
    }
    return labels.get(case, case.replace("_", " "))


def _plot_throughput_npv(df: pd.DataFrame, cases: list[str], filename: str, title: str) -> None:
    colors = cm.viridis([i / max(1, len(cases) - 1) for i in range(len(cases))])
    fig, ax = plt.subplots(figsize=(10.0, 6.0))
    for color, case in zip(colors, cases):
        sub = df[df["case"] == case].sort_values("target_annual_throughput_kwh")
        ax.plot(
            sub["target_annual_throughput_kwh"],
            sub["npv"] / MNOK,
            marker="o",
            label=_clean_case_label(case),
            color=color,
        )
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xscale("log")
    ax.set_xlabel("Target annual throughput [kWh/year]")
    ax.set_ylabel("NPV [MNOK]")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    _style_legend(ax)
    _finish_figure(fig, filename)


def _plot_throughput_break_even_price(
    df: pd.DataFrame,
    cases: list[str],
    filename: str,
    title: str,
) -> None:
    colors = cm.viridis([i / max(1, len(cases) - 1) for i in range(len(cases))])
    fig, ax = plt.subplots(figsize=(10.0, 6.0))
    for color, case in zip(colors, cases):
        sub = df[df["case"] == case].sort_values("target_annual_throughput_kwh")
        ax.plot(
            sub["target_annual_throughput_kwh"],
            sub["break_even_selling_price_per_kwh"],
            marker="o",
            label=_clean_case_label(case),
            color=color,
        )
    ax.set_xscale("log")
    ax.set_xlabel("Target annual throughput [kWh/year]")
    ax.set_ylabel("Annual break-even selling price [NOK/kWh]")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    _style_legend(ax)
    _finish_figure(fig, filename)


def plot_throughput_scaling():
    path = DATA_DIR / "norway_throughput_scaling_results.csv"
    if not path.exists():
        print(f"Skipping throughput plot; missing {path}")
        return

    df = pd.read_csv(path)
    cases = sorted(df["case"].unique(), key=_case_sort_key)

    # The combined throughput figure becomes cluttered when the pack-to-modules
    # pathway is included.  Generate component/pathway-specific figures instead.
    for group in ("tesla", "leaf", "leaf_pack_to_modules", "leaf_pack_triage", "leaf_pack"):
        group_cases = [case for case in cases if _component_group(case) == group]
        if not group_cases:
            continue
        readable = _clean_group_label(group)
        _plot_throughput_npv(
            df,
            group_cases,
            f"throughput_scaling_npv_{group}.png",
            f"{readable}: throughput scaling NPV",
        )
        _plot_throughput_break_even_price(
            df,
            group_cases,
            f"throughput_scaling_breakeven_price_{group}.png",
            f"{readable}: break-even selling price vs throughput",
        )


def plot_sensitivity_tornado(metric: str = "npv") -> None:
    """Plot a one-at-a-time sensitivity range chart for ``metric``.

    Each horizontal bar spans the minimum to maximum model result obtained when
    one input parameter is swept across its sensitivity range. The black tick
    marks the nearest base-case value within that sweep. This is tornado-style
    ranking by spread, not a probability distribution.
    """
    path = DATA_DIR / "norway_sensitivity_results.csv"
    if not path.exists():
        print(f"Skipping sensitivity plot; missing {path}")
        return

    df = pd.read_csv(path)
    if metric not in df.columns:
        print(f"Skipping tornado for '{metric}'; column not found in {path}")
        return

    exclude_params = set()
    if metric in _BREAK_EVEN_SELLING_PRICE_METRICS:
        exclude_params.add("selling_price_per_kwh")

    for component in sorted(df["component"].unique()):
        sub_component = df[df["component"] == component]
        summary = []
        for parameter in sorted(sub_component["parameter"].unique()):
            if parameter in exclude_params:
                continue
            sub = sub_component[sub_component["parameter"] == parameter]
            metric_values = _display_metric_values(sub[metric].dropna(), metric)
            if metric_values.empty:
                continue
            summary.append({
                "parameter": parameter,
                "min": metric_values.min(),
                "max": metric_values.max(),
                "spread": metric_values.max() - metric_values.min(),
                "base": _base_metric_value_for_parameter(sub, component, parameter, metric),
            })
        if not summary:
            continue

        summary_df = pd.DataFrame(summary).sort_values("spread")
        n = len(summary_df)
        metric_label = _METRIC_LABELS.get(metric, metric.replace("_", " "))

        fig, ax = plt.subplots(figsize=(10.6, max(5.8, 0.55 * n + 1.9)))
        base_label_drawn = False
        for idx, (_, row) in enumerate(summary_df.iterrows()):
            ax.hlines(
                idx,
                row["min"],
                row["max"],
                linewidth=7.0,
                color="0.45",
                zorder=1,
            )
            ax.scatter(
                [row["min"], row["max"]],
                [idx, idx],
                s=34,
                facecolors="white",
                edgecolors="black",
                linewidths=0.8,
                zorder=2,
            )
            if row["base"] is not None and not pd.isna(row["base"]):
                ax.scatter(
                    row["base"],
                    idx,
                    marker="|",
                    s=220,
                    color="black",
                    linewidths=2.2,
                    label="Base-case result" if not base_label_drawn else "",
                    zorder=3,
                )
                base_label_drawn = True

        ax.set_yticks(range(n))
        ax.set_yticklabels([_PARAM_LABELS.get(p, p) for p in summary_df["parameter"]])
        ax.set_xlabel(metric_label)
        ax.set_title(
            f"{_clean_component_label(component)}: one-at-a-time sensitivity range"
        )
        if metric == "npv":
            ax.axvline(0, color="black", linewidth=1, linestyle="--")
        ax.grid(True, axis="x", alpha=0.3)
        if base_label_drawn:
            _style_legend(ax, loc="best")
        _finish_figure(fig, f"{component}_{metric}_tornado.png")


def plot_npv_vs_selling_price() -> None:
    """Line plot of NPV vs selling price for each component."""
    path = DATA_DIR / "norway_sensitivity_results.csv"
    if not path.exists():
        return

    df = pd.read_csv(path)
    df_sp = df[df["parameter"] == "selling_price_per_kwh"].copy()
    if df_sp.empty:
        return

    df_sp["selling_price_nok"] = df_sp["value"]

    components = sorted(df_sp["component"].unique())
    colors = cm.viridis([i / max(1, len(components) - 1) for i in range(len(components))])

    fig, ax = plt.subplots(figsize=(9.8, 6.0))
    for color, component in zip(colors, components):
        sub = df_sp[df_sp["component"] == component].sort_values("selling_price_nok")
        ax.plot(
            sub["selling_price_nok"],
            sub["npv"] / MNOK,
            marker="o",
            label=_clean_component_label(component),
            color=color,
        )
    ax.axhline(0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("Selling price [NOK/kWh]")
    ax.set_ylabel("NPV [MNOK]")
    ax.set_title("NPV vs selling price (Norway)")
    ax.grid(True, alpha=0.3)
    _style_legend(ax)
    _finish_figure(fig, "npv_vs_selling_price.png")


def plot_purchase_price_feasibility() -> None:
    """Plot NPV vs purchase price."""
    path = DATA_DIR / "norway_sensitivity_results.csv"
    if not path.exists():
        return

    df = pd.read_csv(path)
    df_pp = df[df["parameter"] == "purchase_price_per_kwh_nameplate"].copy()
    if df_pp.empty:
        return

    df_pp["purchase_price_nok"] = df_pp["value"]

    components = sorted(df_pp["component"].unique())
    colors = cm.viridis([i / max(1, len(components) - 1) for i in range(len(components))])

    fig, ax = plt.subplots(figsize=(9.8, 6.0))
    for color, component in zip(colors, components):
        sub = df_pp[df_pp["component"] == component].sort_values("purchase_price_nok")
        ax.plot(
            sub["purchase_price_nok"],
            sub["npv"] / MNOK,
            marker="o",
            label=_clean_component_label(component),
            color=color,
        )
    ax.axhline(0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("Purchase price [NOK/kWh-nameplate]")
    ax.set_ylabel("NPV [MNOK]")
    ax.set_title("NPV vs purchase price (Norway)")
    ax.grid(True, alpha=0.3)
    _style_legend(ax)
    _finish_figure(fig, "npv_vs_purchase_price.png")


def plot_leaf_threshold_sensitivity() -> None:
    """Leaf acceptance threshold vs usable fraction and NPV."""
    path = DATA_DIR / "norway_sensitivity_results.csv"
    if not path.exists():
        return

    df = pd.read_csv(path)
    df_leaf = df[
        (df["component"] == "leaf")
        & (df["parameter"] == "min_remaining_energy_fraction")
    ].copy()
    if df_leaf.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))

    axes[0].plot(
        df_leaf["value"],
        df_leaf["usable_fraction"],
        marker="o",
        color=cm.viridis(0.4),
    )
    axes[0].set_xlabel("Acceptance threshold")
    axes[0].set_ylabel("Usable fraction")
    axes[0].set_title("Leaf: threshold vs usable fraction")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(
        df_leaf["value"],
        df_leaf["npv"] / MNOK,
        marker="o",
        color=cm.viridis(0.7),
    )
    axes[1].axhline(0, color="black", linewidth=1, linestyle="--")
    axes[1].set_xlabel("Acceptance threshold")
    axes[1].set_ylabel("NPV [MNOK]")
    axes[1].set_title("Leaf: threshold vs NPV")
    axes[1].grid(True, alpha=0.3)

    _finish_figure(fig, "leaf_threshold_sensitivity.png")


def plot_current_vs_npv_break_even_selling_price() -> None:
    """Compare scenario selling price with NPV break-even selling price.

    This plot should be based on the thesis scenario table, not on the selling
    price sensitivity sweep. The sensitivity sweep makes the break-even price
    look like a flat line against the input price, which is correct but not
    informative.
    """
    thesis_path = DATA_DIR / "thesis_scenario_results.csv"
    if not thesis_path.exists():
        print(f"Skipping scenario-vs-break-even selling price; missing {thesis_path}")
        return

    df = pd.read_csv(thesis_path)
    required = {
        "case",
        "case_type",
        "currency",
        "revenue_per_sellable_kwh",
        "npv_break_even_selling_price_per_kwh",
    }
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required - set(df.columns)))
        print(f"Skipping scenario-vs-break-even selling price; missing columns: {missing}")
        return

    df = df[df["currency"].str.upper() == "NOK"].copy()
    df = df.dropna(
        subset=[
            "revenue_per_sellable_kwh",
            "npv_break_even_selling_price_per_kwh",
        ]
    )
    if df.empty:
        return

    df = df.sort_values("case", key=lambda s: s.map(_case_sort_key))
    y_positions = list(range(len(df)))

    fig, ax = plt.subplots(figsize=(12.8, max(6.8, 0.52 * len(df) + 1.8)))
    profitable_label_drawn = False
    for y, (_, row) in zip(y_positions, df.iterrows()):
        current = row["revenue_per_sellable_kwh"]
        breakeven = row["npv_break_even_selling_price_per_kwh"]
        lower = min(current, breakeven)
        upper = max(current, breakeven)
        ax.hlines(y, lower, upper, linewidth=2.5, color="0.60")
        ax.scatter(
            current,
            y,
            marker="o",
            s=60,
            facecolors="white",
            edgecolors="black",
            linewidths=1.1,
            label="Scenario selling price" if y == 0 else "",
            zorder=3,
        )
        ax.scatter(
            breakeven,
            y,
            marker="D",
            s=55,
            facecolors="white",
            edgecolors="black",
            linewidths=1.1,
            label="NPV break-even selling price" if y == 0 else "",
            zorder=3,
        )
        if current >= breakeven:
            marker_x = upper + 15
            ax.scatter(
                marker_x,
                y,
                marker="s",
                s=40,
                facecolors="black",
                edgecolors="black",
                label="Scenario price ≥ break-even price" if not profitable_label_drawn else "",
                zorder=3,
            )
            profitable_label_drawn = True

    ax.set_yticks(y_positions)
    labels = [
        f"{_clean_case_label(row.case)}"
        for row in df.itertuples()
    ]
    ax.set_yticklabels(labels)
    ax.set_xlabel("Selling price [NOK/kWh]")
    ax.set_title("Scenario selling price vs NPV break-even selling price")
    ax.margins(x=0.12)
    ax.grid(True, axis="x", alpha=0.3)
    _style_legend(ax)
    _finish_figure(fig, "current_vs_npv_break_even_selling_price.png")


def plot_units_required_for_1gwh() -> None:
    """Plot physical handling volume required for 1 GWh annual throughput.

    The bar is split into the first handling unit in the pathway and additional
    module tests after disassembly. This makes the hybrid triage workload visible:
    it starts with pack-level handling, but adds module tests only for failed packs.
    """
    path = DATA_DIR / "throughput_unit_requirements_1gwh.csv"
    if not path.exists():
        print(f"Skipping unit-requirement plot; missing {path}")
        return

    df = pd.read_csv(path)
    if df.empty:
        return

    if "primary_units_per_year" not in df.columns:
        df["primary_units_per_year"] = df["processed_units_per_year"]
    if "additional_module_tests_per_year" not in df.columns:
        df["additional_module_tests_per_year"] = 0.0

    df["primary_units_per_year"] = pd.to_numeric(df["primary_units_per_year"], errors="coerce").fillna(0.0)
    df["additional_module_tests_per_year"] = pd.to_numeric(df["additional_module_tests_per_year"], errors="coerce").fillna(0.0)
    df["total_work_items_per_year"] = df["primary_units_per_year"] + df["additional_module_tests_per_year"]
    df = df.sort_values("total_work_items_per_year", ascending=False)

    fig, ax = plt.subplots(figsize=(10.2, 5.9))
    y = range(len(df))
    primary_color = cm.viridis(0.35)
    additional_color = cm.viridis(0.78)
    ax.barh(
        y,
        df["primary_units_per_year"],
        color=primary_color,
        edgecolor="black",
        linewidth=0.4,
        label="Primary units handled",
    )
    ax.barh(
        y,
        df["additional_module_tests_per_year"],
        left=df["primary_units_per_year"],
        color=additional_color,
        edgecolor="black",
        linewidth=0.4,
        label="Additional module tests after disassembly",
    )
    ax.set_yticks(list(y))
    ax.set_yticklabels(df["pathway"])
    ax.set_xlabel("Physical work items per year for 1 GWh")
    ax.set_title("Handling volume required for 1 GWh annual throughput")
    ax.grid(True, axis="x", alpha=0.3)
    _style_legend(ax)

    xmax = max(df["total_work_items_per_year"].max(), 1.0)
    ax.set_xlim(0, xmax * 1.16)
    for idx, (_, row) in enumerate(df.iterrows()):
        total = row["total_work_items_per_year"]
        extra = row["additional_module_tests_per_year"]
        label = f"{total:,.0f} total"
        if extra > 0:
            label += f" ({extra:,.0f} module tests)"
        ax.text(total + xmax * 0.015, idx, label, va="center", fontsize=10)

    _finish_figure(fig, "throughput_units_required_1gwh.png")


def cleanup_obsolete_figures() -> None:
    """Remove obsolete duplicate figures no longer generated by this script."""
    obsolete_patterns = [
        "*_break_even_selling_price_per_kwh_tornado.png",
    ]
    for pattern in obsolete_patterns:
        for path in FIG_DIR.glob(pattern):
            # Keep the explicitly named annual and NPV break-even tornado charts.
            if "annual_" in path.name or "npv_" in path.name:
                continue
            path.unlink(missing_ok=True)


def main():
    cleanup_obsolete_figures()
    plot_throughput_scaling()
    plot_units_required_for_1gwh()
    plot_sensitivity_tornado("npv")
    plot_sensitivity_tornado("annual_break_even_selling_price_per_kwh")
    plot_sensitivity_tornado("npv_break_even_selling_price_per_kwh")
    plot_npv_vs_selling_price()
    plot_purchase_price_feasibility()
    plot_leaf_threshold_sensitivity()
    plot_current_vs_npv_break_even_selling_price()
    print(f"Saved figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
