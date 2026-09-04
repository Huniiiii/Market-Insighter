"""Generate deterministic demo data, charts, and the sample research PDF."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.commentary import generate_market_commentary
from src.event_study import aggregate_event_paths, run_event_study
from src.indicators import correlation_matrix, latest_change_table, rolling_correlation
from src.risk import portfolio_returns, risk_metrics, stress_test


DATA_DIR = ROOT / "data" / "sample"
CHART_DIR = ROOT / "charts"
REPORT_DIR = ROOT / "reports"

NAVY = colors.HexColor("#0B1730")
TEAL = colors.HexColor("#1AAE9F")
SLATE = colors.HexColor("#53657A")
LIGHT = colors.HexColor("#E8EEF4")
FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

pdfmetrics.registerFont(TTFont(FONT, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont(FONT_BOLD, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))


def _stress_mask(index: pd.DatetimeIndex, start: str, end: str) -> np.ndarray:
    return (index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))


def generate_levels() -> pd.DataFrame:
    """Create synthetic cross-asset history with interpretable relationships."""
    rng = np.random.default_rng(20260904)
    index = pd.bdate_range("2007-01-02", "2026-08-31")
    n = len(index)

    risk = rng.normal(0, 1, n)
    oil_factor = 0.25 * risk + rng.normal(0, 0.97, n)
    rates_factor = -0.15 * risk + rng.normal(0, 0.98, n)
    asia_factor = 0.30 * risk + rng.normal(0, 0.95, n)

    gfc = _stress_mask(index, "2008-09-15", "2009-03-09")
    covid = _stress_mask(index, "2020-02-19", "2020-03-23")
    rates_2022 = _stress_mask(index, "2022-01-03", "2022-10-14")
    risk[gfc] += rng.normal(-0.45, 2.1, gfc.sum())
    oil_factor[gfc] += rng.normal(-0.35, 1.7, gfc.sum())
    risk[covid] += rng.normal(-0.80, 2.8, covid.sum())
    oil_factor[covid] += rng.normal(-0.75, 2.5, covid.sum())
    rates_factor[rates_2022] += rng.normal(0.32, 1.0, rates_2022.sum())

    spy_r = 0.00034 + 0.0087 * risk - 0.0018 * rates_factor
    xlf_r = 0.00028 + 0.0102 * risk + 0.0010 * rates_factor
    xle_r = 0.00030 + 0.0055 * risk + 0.0082 * oil_factor
    wti_r = 0.00022 + 0.0030 * risk + 0.0160 * oil_factor
    usdcad_r = 0.00001 - 0.0024 * oil_factor - 0.0012 * risk + rng.normal(0, 0.0021, n)
    usdkrw_r = 0.00002 + 0.0024 * asia_factor + 0.0020 * risk + rng.normal(0, 0.0024, n)

    levels = pd.DataFrame(index=index)
    for name, start, returns in (
        ("SPY", 140.0, spy_r),
        ("XLF", 28.0, xlf_r),
        ("XLE", 52.0, xle_r),
        ("WTI", 62.0, wti_r),
        ("USDCAD", 1.16, usdcad_r),
        ("USDKRW", 930.0, usdkrw_r),
    ):
        levels[name] = start * np.exp(np.cumsum(returns))

    yield_changes = 0.9 * rates_factor + 0.15 * rng.normal(size=n)
    yield_changes[rates_2022] += 0.45
    us10y = np.empty(n)
    us10y[0] = 4.65
    for i in range(1, n):
        mean_reversion = 0.002 * (3.25 - us10y[i - 1])
        us10y[i] = np.clip(us10y[i - 1] + mean_reversion + yield_changes[i] / 100.0, 0.35, 6.5)
    levels["US10Y"] = us10y

    year = index.year
    fed_funds = np.select(
        [
            year <= 2007,
            (year >= 2008) & (year <= 2015),
            (year >= 2016) & (year <= 2018),
            year == 2019,
            (year >= 2020) & (year <= 2021),
            year == 2022,
            (year >= 2023) & (year <= 2024),
            year >= 2025,
        ],
        [5.0, 0.25, 1.4, 1.8, 0.15, 3.0, 5.25, 4.25],
        default=2.0,
    ).astype(float)
    levels["FEDFUNDS"] = fed_funds

    monthly_index = pd.date_range(index.min(), index.max(), freq="MS")
    monthly_inflation = 0.0019 + rng.normal(0, 0.0012, len(monthly_index))
    monthly_inflation[(monthly_index >= "2021-04-01") & (monthly_index <= "2022-12-01")] += 0.0040
    cpi = 200.0 * np.exp(np.cumsum(monthly_inflation))
    cpi_series = pd.Series(cpi, index=monthly_index)
    levels["CPI"] = cpi_series.reindex(index)
    levels.index.name = "date"
    return levels


def generate_events() -> pd.DataFrame:
    rng = np.random.default_rng(31415)
    dates = pd.date_range("2008-01-15", "2026-07-15", freq="180D")
    categories = np.resize(np.array(["US CPI", "Fed Decision", "Oil Shock", "Geopolitical Risk"]), len(dates))
    consensus = rng.normal(0.25, 0.08, len(dates)).round(2)
    surprise = rng.normal(0, 0.12, len(dates)).round(2)
    actual = (consensus + surprise).round(2)
    events = pd.DataFrame(
        {
            "date": dates,
            "event": [f"Illustrative {category} Event {i + 1}" for i, category in enumerate(categories)],
            "category": categories,
            "actual": actual,
            "consensus": consensus,
            "surprise": surprise,
        }
    )
    return events


def save_charts(levels: pd.DataFrame, events: pd.DataFrame) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    palette = ["#0B6E75", "#D98C26", "#2A5CAA", "#A44747", "#7758A6", "#2687A8"]

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=160)
    normalized = levels[["SPY", "XLF", "XLE", "WTI"]].dropna()
    normalized = normalized / normalized.iloc[0] * 100
    normalized.plot(ax=ax, color=palette[:4], linewidth=1.4)
    ax.set_title("Illustrative Cross-Asset Performance", loc="left", fontweight="bold", color="#0B1730")
    ax.set_ylabel("Start = 100")
    ax.legend(frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "cross_asset_performance.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=160)
    corr = rolling_correlation(levels, "WTI", "USDCAD", 60)
    ax.plot(corr.index, corr, color=palette[0], linewidth=1.3)
    ax.axhline(0, color="#6B7280", linestyle="--", linewidth=0.8)
    ax.fill_between(corr.index, corr, 0, where=corr <= 0, color="#1AAE9F", alpha=0.2)
    ax.set_ylim(-1, 1)
    ax.set_title("60-Day Rolling Correlation: WTI vs USD/CAD", loc="left", fontweight="bold", color="#0B1730")
    ax.set_ylabel("Correlation")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "wti_usdcad_rolling_correlation.png", bbox_inches="tight")
    plt.close(fig)

    study = run_event_study(levels, events[events["category"] == "US CPI"], ["SPY", "XLF", "WTI", "USDCAD"], 5, 10)
    aggregate = aggregate_event_paths(study)
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=160)
    for i, (asset, group) in enumerate(aggregate.groupby("asset")):
        ax.plot(group["relative_day"], group["mean"], label=asset, color=palette[i], linewidth=1.8)
    ax.axvline(0, color="#D98C26", linestyle="--", linewidth=1)
    ax.axhline(0, color="#6B7280", linestyle=":", linewidth=0.8)
    ax.set_title("Average Response Around Illustrative CPI Events", loc="left", fontweight="bold", color="#0B1730")
    ax.set_xlabel("Relative trading day")
    ax.set_ylabel("Cumulative return (%)")
    ax.legend(frameon=False, ncol=4)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "cpi_event_study.png", bbox_inches="tight")
    plt.close(fig)


def _header_footer(canvas, document) -> None:
    canvas.saveState()
    width, height = letter
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(1.2)
    canvas.line(0.55 * inch, height - 0.43 * inch, width - 0.55 * inch, height - 0.43 * inch)
    canvas.setFillColor(NAVY)
    canvas.setFont(FONT_BOLD, 8)
    canvas.drawString(0.55 * inch, height - 0.3 * inch, "MARKET INSIGHTER | CROSS-ASSET STRATEGY LAB")
    canvas.setFillColor(SLATE)
    canvas.setFont(FONT, 7.5)
    canvas.drawString(0.55 * inch, 0.35 * inch, "Illustrative synthetic data | Educational use only")
    canvas.drawRightString(width - 0.55 * inch, 0.35 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_report(levels: pd.DataFrame, events: pd.DataFrame) -> None:
    output = REPORT_DIR / "sample_market_report.pdf"
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Kicker", parent=styles["Normal"], textColor=TEAL, fontName=FONT_BOLD, fontSize=8, leading=10, spaceAfter=8))
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=NAVY, fontName=FONT_BOLD, fontSize=25, leading=28, alignment=TA_LEFT, spaceAfter=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=NAVY, fontName=FONT_BOLD, fontSize=14, leading=18, spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="BodyClean", parent=styles["BodyText"], textColor=SLATE, fontName=FONT, fontSize=9.3, leading=14, spaceAfter=7))
    styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], textColor=NAVY, fontName=FONT, backColor=LIGHT, borderColor=TEAL, borderWidth=0, borderPadding=9, fontSize=10, leading=15, spaceBefore=6, spaceAfter=12))
    styles.add(ParagraphStyle(name="SmallRight", parent=styles["Normal"], textColor=SLATE, fontName=FONT, fontSize=8, alignment=TA_RIGHT))

    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.58 * inch,
        title="Market Insighter - Sample Market Report",
        author="Sanghun Kim",
    )
    story = [
        Spacer(1, 0.16 * inch),
        Paragraph("HUNI PERSONAL PROJECT", styles["Kicker"]),
        Paragraph("Macro & Cross-Asset Monitor", styles["ReportTitle"]),
        Paragraph("Sample research output | 31 August 2026", styles["SmallRight"]),
        Spacer(1, 0.1 * inch),
    ]

    commentary = generate_market_commentary(levels)
    story.append(Paragraph("Executive view", styles["Section"]))
    story.append(Paragraph(" ".join(commentary[:4]), styles["Callout"]))

    changes = latest_change_table(levels).loc[["SPY", "XLF", "XLE", "WTI", "USDCAD", "USDKRW", "US10Y"]]
    table_data = [["Series", "Level", "1D", "1W", "1M"]]
    for name, row in changes.iterrows():
        unit = " bps" if row["change_unit"] == "bps" else "%"
        table_data.append(
            [
                name,
                f"{row['level']:,.2f}",
                f"{row['1D']:+.2f}{unit}",
                f"{row['1W']:+.2f}{unit}",
                f"{row['1M']:+.2f}{unit}",
            ]
        )
    market_table = Table(table_data, colWidths=[1.25 * inch, 1.15 * inch, 1.05 * inch, 1.05 * inch, 1.05 * inch], repeatRows=1)
    market_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (0, -1), FONT_BOLD),
                ("FONTNAME", (1, 1), (-1, -1), FONT),
                ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D2DF")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            Paragraph("Market dashboard", styles["Section"]),
            market_table,
            Spacer(1, 0.12 * inch),
            Paragraph(
                "Reading the screen: price and FX moves are shown in percent; yield moves are shown in basis points. FX pairs are quoted as US dollars against local currency, so a decline in USD/CAD or USD/KRW represents local-currency appreciation.",
                styles["BodyClean"],
            ),
        ]
    )

    story.extend([PageBreak(), Paragraph("Cross-asset transmission", styles["Section"])])
    corr = correlation_matrix(levels[["SPY", "XLF", "XLE", "WTI", "USDCAD", "USDKRW", "US10Y"]]).round(2)
    focus_corr = corr.loc[["WTI", "US10Y"], ["SPY", "XLF", "XLE", "USDCAD", "USDKRW"]]
    corr_data = [["Driver"] + list(focus_corr.columns)] + [
        [idx] + [f"{value:+.2f}" for value in row] for idx, row in focus_corr.iterrows()
    ]
    corr_table = Table(corr_data, colWidths=[1.2 * inch] + [1.0 * inch] * 5)
    corr_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (0, -1), TEAL),
                ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C7D2DF")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(Paragraph("Selected daily-move correlations", styles["BodyClean"]))
    story.append(corr_table)
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "The sign of an FX pair matters. A decline in USD/CAD means CAD appreciation; therefore a negative WTI/USD-CAD correlation is consistent with stronger oil prices coinciding with a firmer Canadian dollar. Correlation is time-varying and should be treated as a monitoring signal, not a structural coefficient.",
            styles["BodyClean"],
        )
    )
    story.append(Image(str(CHART_DIR / "wti_usdcad_rolling_correlation.png"), width=7.25 * inch, height=3.48 * inch))

    story.extend([PageBreak(), Paragraph("Event study & portfolio risk", styles["Section"])])
    story.append(Image(str(CHART_DIR / "cpi_event_study.png"), width=7.25 * inch, height=3.48 * inch))
    weights = {"SPY": 0.40, "XLF": 0.25, "XLE": 0.20, "WTI": 0.15}
    portfolio = portfolio_returns(levels, weights)
    benchmark_returns = levels["SPY"].pct_change(fill_method=None)
    metrics = risk_metrics(portfolio, benchmark_returns)
    metric_data = [
        ["Portfolio metric", "Estimate"],
        ["Annualized return", f"{metrics['Annualized Return']:.1%}"],
        ["Annualized volatility", f"{metrics['Annualized Volatility']:.1%}"],
        ["Sharpe ratio", f"{metrics['Sharpe Ratio']:.2f}"],
        ["Beta vs SPY", f"{metrics['Beta vs SPY']:.2f}"],
        ["Maximum drawdown", f"{metrics['Maximum Drawdown']:.1%}"],
    ]
    metric_table = Table(metric_data, colWidths=[2.4 * inch, 1.5 * inch])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), FONT_BOLD),
                ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D2DF")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    stresses = stress_test(portfolio)
    stress_data = [["Scenario", "Return", "Volatility", "Max drawdown"]]
    for idx, row in stresses.iterrows():
        stress_data.append(
            [
                Paragraph(idx, styles["BodyClean"]),
                f"{row['Cumulative Return']:.1%}",
                f"{row['Volatility']:.1%}",
                f"{row['Max Drawdown']:.1%}",
            ]
        )
    stress_table = Table(stress_data, colWidths=[2.35 * inch, 1.25 * inch, 1.25 * inch, 1.35 * inch])
    stress_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, -1), FONT_BOLD), ("FONTSIZE", (0, 0), (-1, -1), 8.2), ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C7D2DF")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend(
        [
            Paragraph("Illustrative portfolio: 40% SPY / 25% XLF / 20% XLE / 15% WTI", styles["BodyClean"]),
            metric_table,
            Spacer(1, 0.10 * inch),
            Paragraph("Historical stress windows", styles["BodyClean"]),
            stress_table,
            Spacer(1, 0.08 * inch),
            Paragraph("Methodology and limitations", styles["Section"]),
            Paragraph(
                "Returns are close-to-close and assume daily rebalancing with no transaction costs. VaR and Expected Shortfall use the historical distribution. Event paths use trading-day windows and a day -1 baseline. The bundled dataset and event calendar are synthetic, designed to make the project reproducible when live APIs are unavailable. They must not be used for investment decisions.",
                styles["BodyClean"],
            ),
        ]
    )
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    levels = generate_levels()
    events = generate_events()
    levels.to_csv(DATA_DIR / "market_data.csv", float_format="%.6f")
    events.to_csv(DATA_DIR / "events.csv", index=False)
    pd.DataFrame({"ticker": ["SPY", "XLF", "XLE", "WTI"], "weight": [0.40, 0.25, 0.20, 0.15]}).to_csv(DATA_DIR / "portfolio.csv", index=False)
    save_charts(levels, events)
    build_report(levels, events)
    print(f"Generated {len(levels):,} observations, {len(events)} events, 3 charts, and 1 PDF.")


if __name__ == "__main__":
    main()
