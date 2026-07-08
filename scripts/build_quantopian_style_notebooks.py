#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


@dataclass(frozen=True)
class ResearchNotebookSpec:
    filename: str
    slug: str
    title: str
    quantopian_sources: tuple[str, ...]
    concept: str
    analysis_code: str
    exercises: tuple[str, ...]


CODE_EXPLANATION_MARKER = "### โค้ดช่องถัดไปทำอะไร"
OFFICIAL_SOURCES = (
    "https://developer.webull.com/apis/docs/market-data-api/getting-started",
    "https://developer.webull.com/apis/docs/reference/broker-market-data-api/bars-using-get/",
    "https://github.com/nutdnuy/quantopiandoc/tree/main",
)


def markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(source).strip() + "\n"}


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


COMMON_SETUP = r"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

NOTEBOOK_SLUG = "__NOTEBOOK_SLUG__"
LIVE_MODE = os.getenv("WEBULL_QUANTOPIAN_LIVE", "0") == "1"
OUTPUT_ROOT = Path(os.getenv("WEBULL_QUANTOPIAN_OUTPUT_DIR", "outputs/quantopian-style"))
OUTPUT_DIR = OUTPUT_ROOT / NOTEBOOK_SLUG
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

THEME = {
    "background": "#121212",
    "surface": "#1D1D1D",
    "primary": "#69F0AE",
    "profit": "#00E676",
    "loss": "#FF5252",
    "benchmark": "#03DAC6",
    "grid": "rgba(255,255,255,0.08)",
    "text": "rgba(255,255,255,0.87)",
}


def build_sample_prices(symbols=("AAPL", "MSFT", "SPY", "TSLA"), periods=252) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=periods)
    rows = []
    market = np.linspace(0, 1, periods)
    for index, symbol in enumerate(symbols):
        trend = 0.0002 + 0.00005 * index
        cycle = 0.006 * np.sin(np.linspace(0, 10 + index, periods))
        shocks = 0.004 * np.cos(np.linspace(0, 16 + index * 2, periods))
        beta_component = (0.8 + index * 0.15) * 0.002 * np.sin(market * 18)
        returns = trend + cycle + shocks + beta_component
        close = 100 * (1 + pd.Series(returns, index=dates)).cumprod()
        open_price = close.shift(1).fillna(close.iloc[0] * 0.997)
        high = pd.concat([open_price, close], axis=1).max(axis=1) * (1.003 + index * 0.0004)
        low = pd.concat([open_price, close], axis=1).min(axis=1) * (0.997 - index * 0.0003)
        volume = (
            1_000_000
            + index * 170_000
            + (np.sin(np.linspace(0, 20, periods)) + 1) * 120_000
        ).round()
        rows.append(
            pd.DataFrame(
                {
                    "symbol": symbol,
                    "date": dates,
                    "open": open_price.to_numpy(),
                    "high": high.to_numpy(),
                    "low": low.to_numpy(),
                    "close": close.to_numpy(),
                    "volume": volume,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def load_webull_or_sample_prices(symbols=("AAPL", "MSFT", "SPY", "TSLA")) -> pd.DataFrame:
    if not LIVE_MODE:
        data = build_sample_prices(symbols=symbols)
        data.to_csv(OUTPUT_DIR / "offline_webull_style_prices.csv", index=False)
        return data

    from webull_lab.clients import build_data_client
    from webull_lab.config import load_settings
    from webull_lab.market_data import get_stock_bars

    settings = load_settings()
    data_client = build_data_client(settings)
    frames = []
    for symbol in symbols:
        payload = get_stock_bars(data_client, symbol, "D")
        frame = pd.DataFrame(payload).rename(columns={"time": "date"})
        frame["symbol"] = symbol
        frames.append(frame[["symbol", "date", "open", "high", "low", "close", "volume"]])
    data = pd.concat(frames, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["date", "open", "high", "low", "close"])
    data = data.sort_values(["symbol", "date"])
    data.to_csv(OUTPUT_DIR / "live_webull_prices.csv", index=False)
    return data


def close_matrix(price_data: pd.DataFrame) -> pd.DataFrame:
    return price_data.pivot(index="date", columns="symbol", values="close").sort_index()


def daily_returns(close: pd.DataFrame) -> pd.DataFrame:
    return close.pct_change().dropna()


def save_json(name: str, payload: dict) -> Path:
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def save_plot(fig: go.Figure, name: str) -> Path:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=THEME["background"],
        plot_bgcolor=THEME["background"],
        font={"color": THEME["text"]},
        xaxis={"gridcolor": THEME["grid"]},
        yaxis={"gridcolor": THEME["grid"]},
    )
    path = OUTPUT_DIR / f"{name}.html"
    fig.write_html(path, include_plotlyjs="cdn")
    return path


prices = load_webull_or_sample_prices()
close = close_matrix(prices)
returns = daily_returns(close)
print(
    {
        "live_mode": LIVE_MODE,
        "rows": len(prices),
        "symbols": sorted(prices["symbol"].unique()),
        "output_dir": str(OUTPUT_DIR),
    }
)
"""


COMMON_INSPECT = r"""
summary = {
    "sample_start": str(close.index.min().date()),
    "sample_end": str(close.index.max().date()),
    "symbols": list(close.columns),
    "mean_daily_return": returns.mean().round(6).to_dict(),
    "daily_volatility": returns.std().round(6).to_dict(),
}
save_json("data_summary", summary)
pd.DataFrame(summary["mean_daily_return"], index=["mean_daily_return"]).T
"""


RESEARCH_NOTEBOOKS: tuple[ResearchNotebookSpec, ...] = (
    ResearchNotebookSpec(
        filename="01_research_environment.ipynb",
        slug="01-research-environment",
        title="Webull Research Environment",
        quantopian_sources=("Introduction_to_Research", "Introduction_to_Pandas", "Introduction_to_NumPy"),
        concept="เริ่มจาก Webull historical bars แล้วแปลงเป็น pandas DataFrame สำหรับ research loop",
        analysis_code=r"""
fig = go.Figure()
for symbol in close.columns:
    fig.add_trace(go.Scatter(x=close.index, y=close[symbol], name=symbol))
plot_path = save_plot(fig, "close_prices")
metadata = {
    "bars_source": "Webull Market Data API historical bars or offline sample",
    "output_plot": str(plot_path),
    "row_count": int(len(prices)),
}
save_json("research_environment_metadata", metadata)
print(metadata)
close.tail()
""",
        exercises=(
            "เปลี่ยนรายชื่อ symbol แล้วดูว่า close matrix เปลี่ยน shape อย่างไร",
            "เปิด live mode เมื่อมี credential แล้วเทียบจำนวน rows กับ offline sample",
            "เพิ่ม column return 5 วันใน DataFrame โดยไม่ใช้ข้อมูลอนาคต",
        ),
    ),
    ResearchNotebookSpec(
        filename="02_plotting_returns.ipynb",
        slug="02-plotting-returns",
        title="Plotting Prices and Returns",
        quantopian_sources=("Plotting_Data", "Means", "Variance", "Statistical_Moments"),
        concept="ใช้กราฟและ summary statistics ตรวจ distribution ของ return ก่อนสร้างกลยุทธ์",
        analysis_code=r"""
cumulative = (1 + returns).cumprod()
fig = go.Figure()
for symbol in cumulative.columns:
    fig.add_trace(go.Scatter(x=cumulative.index, y=cumulative[symbol], name=symbol))
plot_path = save_plot(fig, "cumulative_returns")

stats = returns.agg(["mean", "std", "skew", "kurt"]).T
stats["annualized_return_simple"] = returns.mean() * 252
stats["annualized_volatility"] = returns.std() * np.sqrt(252)
stats.to_csv(OUTPUT_DIR / "return_statistics.csv")
print({"plot": str(plot_path), "stats": str(OUTPUT_DIR / "return_statistics.csv")})
stats.round(4)
""",
        exercises=(
            "ลองดูว่า symbol ไหนมี volatility สูงสุด",
            "เพิ่ม histogram ของ return สำหรับ AAPL",
            "อธิบายว่าทำไม annualized return แบบ simple ยังไม่ใช่ forecast",
        ),
    ),
    ResearchNotebookSpec(
        filename="03_autocorrelation_ar.ipynb",
        slug="03-autocorrelation-ar",
        title="Autocorrelation and Simple AR Signals",
        quantopian_sources=("Autocorrelation_and_AR_Models", "Instability_of_Estimates"),
        concept="ทดสอบ autocorrelation ของ return เพื่อดูว่ามี momentum/mean reversion เบื้องต้นหรือไม่",
        analysis_code=r"""
def autocorr(series: pd.Series, lag: int) -> float:
    return float(series.corr(series.shift(lag)))

acf = pd.DataFrame(
    {
        symbol: [autocorr(returns[symbol], lag) for lag in range(1, 11)]
        for symbol in returns.columns
    },
    index=[f"lag_{lag}" for lag in range(1, 11)],
)
acf.to_csv(OUTPUT_DIR / "autocorrelation.csv")

symbol = "AAPL"
signal = np.sign(returns[symbol].shift(1)).fillna(0)
strategy_returns = signal * returns[symbol]
equity = (1 + strategy_returns).cumprod()
bench = (1 + returns[symbol]).cumprod()
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=equity.index,
        y=equity,
        name="Lag-1 signal",
        line={"color": THEME["primary"]},
    )
)
fig.add_trace(
    go.Scatter(
        x=bench.index,
        y=bench,
        name="Buy hold",
        line={"color": THEME["benchmark"], "dash": "dash"},
    )
)
plot_path = save_plot(fig, "simple_ar_signal")
save_json(
    "ar_signal_metrics",
    {
        "plot": str(plot_path),
        "final_equity": float(equity.iloc[-1]),
        "buy_hold": float(bench.iloc[-1]),
    },
)
acf.round(4)
""",
        exercises=(
            "เปลี่ยน lag จาก 1 เป็น 5 แล้วดู equity ใหม่",
            "เพิ่ม fee/slippage แบบง่ายเมื่อ signal เปลี่ยนค่า",
            "แยก train/test ช่วงแรก/ช่วงหลังเพื่อตรวจ estimate instability",
        ),
    ),
    ResearchNotebookSpec(
        filename="04_regression_beta.ipynb",
        slug="04-regression-beta",
        title="Regression Beta and CAPM Intuition",
        quantopian_sources=("Linear_Regression", "CAPM_and_Arbitrage_Pricing_Theory", "Beta_Hedging"),
        concept="ใช้ regression กับ SPY proxy เพื่อวัด beta และ residual ของหุ้นรายตัว",
        analysis_code=r"""
market = returns["SPY"]
rows = []
for symbol in [col for col in returns.columns if col != "SPY"]:
    y = returns[symbol].to_numpy()
    x = market.to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    alpha, beta = np.linalg.lstsq(X, y, rcond=None)[0]
    fitted = alpha + beta * x
    residual = y - fitted
    rows.append(
        {
            "symbol": symbol,
            "alpha_daily": alpha,
            "beta_to_spy": beta,
            "residual_vol": residual.std(),
            "r_squared": 1 - (residual.var() / y.var()),
        }
    )
beta_table = pd.DataFrame(rows).set_index("symbol")
beta_table.to_csv(OUTPUT_DIR / "beta_table.csv")

fig = go.Figure()
fig.add_trace(
    go.Bar(
        x=beta_table.index,
        y=beta_table["beta_to_spy"],
        marker_color=THEME["primary"],
        name="Beta",
    )
)
plot_path = save_plot(fig, "beta_to_spy")
save_json("beta_regression", {"plot": str(plot_path), "symbols": beta_table.index.tolist()})
beta_table.round(4)
""",
        exercises=(
            "ใช้ benchmark อื่นแทน SPY แล้วดู beta เปลี่ยนไหม",
            "เพิ่ม residual chart สำหรับหุ้นที่ beta สูงสุด",
            "อธิบายว่าทำไม beta จาก sample เดียวอาจไม่เสถียร",
        ),
    ),
    ResearchNotebookSpec(
        filename="05_pairs_trading.ipynb",
        slug="05-pairs-trading",
        title="Pairs Trading with Webull Bars",
        quantopian_sources=("Introduction_to_Pairs_Trading", "Integration_Cointegration_and_Stationarity"),
        concept="สร้าง spread ระหว่างสองสินทรัพย์จากราคาปิด แล้วทดสอบ z-score signal เบื้องต้น",
        analysis_code=r"""
pair = ("AAPL", "MSFT")
log_prices = np.log(close[list(pair)])
x = log_prices[pair[1]].to_numpy()
y = log_prices[pair[0]].to_numpy()
X = np.column_stack([np.ones(len(x)), x])
intercept, hedge_ratio = np.linalg.lstsq(X, y, rcond=None)[0]
spread = pd.Series(y - (intercept + hedge_ratio * x), index=log_prices.index, name="spread")
zscore = (spread - spread.rolling(60).mean()) / spread.rolling(60).std()
signal = (-np.sign(zscore)).where(zscore.abs() > 1.0, 0).fillna(0)
spread_return = returns[pair[0]] - hedge_ratio * returns[pair[1]]
strategy_returns = signal.shift(1).fillna(0) * spread_return
equity = (1 + strategy_returns).cumprod()

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=zscore.index,
        y=zscore,
        name="Spread z-score",
        line={"color": THEME["primary"]},
    )
)
fig.add_hline(y=1, line_dash="dash", line_color=THEME["loss"])
fig.add_hline(y=-1, line_dash="dash", line_color=THEME["profit"])
plot_path = save_plot(fig, "pair_zscore")
save_json(
    "pairs_summary",
    {
        "pair": pair,
        "hedge_ratio": float(hedge_ratio),
        "final_equity": float(equity.iloc[-1]),
        "plot": str(plot_path),
    },
)
pd.DataFrame({"spread": spread, "zscore": zscore, "signal": signal, "equity": equity}).tail()
""",
        exercises=(
            "ลอง pair อื่นแล้วเปรียบเทียบ hedge ratio",
            "เพิ่ม stop rule เมื่อ z-score เกิน 3",
            "แยก calibration window กับ trading window เพื่อลด lookahead",
        ),
    ),
    ResearchNotebookSpec(
        filename="06_factor_ranking.ipynb",
        slug="06-factor-ranking",
        title="Ranking a Universe by Price Factors",
        quantopian_sources=("Factor_Analysis", "Ranking_Universes_by_Factors", "Universe_Selection"),
        concept="จัดอันดับ universe ด้วย momentum, volatility และ volume จาก Webull bars",
        analysis_code=r"""
latest = close.index.max()
momentum_60 = close.pct_change(60).loc[latest]
vol_20 = returns.rolling(20).std().loc[latest]
avg_volume = (
    prices.pivot(index="date", columns="symbol", values="volume")
    .rolling(20)
    .mean()
    .loc[latest]
)

factor = pd.DataFrame(
    {
        "momentum_60d": momentum_60,
        "volatility_20d": vol_20,
        "avg_volume_20d": avg_volume,
    }
).dropna()
factor["momentum_rank"] = factor["momentum_60d"].rank(ascending=False)
factor["volatility_rank"] = factor["volatility_20d"].rank(ascending=True)
factor["liquidity_rank"] = factor["avg_volume_20d"].rank(ascending=False)
rank_columns = ["momentum_rank", "volatility_rank", "liquidity_rank"]
factor["composite_score"] = factor[rank_columns].mean(axis=1)
factor = factor.sort_values("composite_score")
factor.to_csv(OUTPUT_DIR / "factor_ranking.csv")

fig = go.Figure()
fig.add_trace(
    go.Bar(
        x=factor.index,
        y=factor["composite_score"],
        marker_color=THEME["primary"],
        name="Composite score",
    )
)
plot_path = save_plot(fig, "factor_ranking")
save_json(
    "factor_ranking_summary",
    {"as_of": str(latest.date()), "plot": str(plot_path), "top_symbol": factor.index[0]},
)
factor.round(4)
""",
        exercises=(
            "เพิ่ม factor ใหม่จาก drawdown 20 วัน",
            "เปลี่ยนน้ำหนัก factor แล้วดูอันดับเปลี่ยนอย่างไร",
            "เขียนข้อควรระวังเรื่อง multiple comparisons เมื่อลอง factor หลายตัว",
        ),
    ),
    ResearchNotebookSpec(
        filename="07_portfolio_var_cvar.ipynb",
        slug="07-portfolio-var-cvar",
        title="Portfolio Analysis, VaR, and CVaR",
        quantopian_sources=("Portfolio_Analysis", "VaR_and_CVaR", "Estimating_Covariance_Matrices"),
        concept="คำนวณ portfolio return, covariance, drawdown, VaR และ CVaR จาก Webull bars",
        analysis_code=r"""
weights = pd.Series({"AAPL": 0.30, "MSFT": 0.30, "SPY": 0.25, "TSLA": 0.15})
portfolio_returns = returns[weights.index].mul(weights, axis=1).sum(axis=1)
portfolio_equity = (1 + portfolio_returns).cumprod()
running_max = portfolio_equity.cummax()
drawdown = portfolio_equity / running_max - 1
var_95 = portfolio_returns.quantile(0.05)
cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
covariance = returns[weights.index].cov() * 252

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=portfolio_equity.index,
        y=portfolio_equity,
        name="Portfolio",
        line={"color": THEME["primary"]},
    )
)
plot_path = save_plot(fig, "portfolio_equity")
metrics = {
    "annualized_return_simple": float(portfolio_returns.mean() * 252),
    "annualized_volatility": float(portfolio_returns.std() * np.sqrt(252)),
    "max_drawdown": float(drawdown.min()),
    "var_95_daily": float(var_95),
    "cvar_95_daily": float(cvar_95),
    "plot": str(plot_path),
}
save_json("portfolio_risk_metrics", metrics)
covariance.to_csv(OUTPUT_DIR / "annualized_covariance.csv")
pd.Series(metrics).to_frame("value")
""",
        exercises=(
            "เปลี่ยนน้ำหนัก portfolio แล้วดู VaR/CVaR ใหม่",
            "เพิ่ม benchmark SPY-only แล้วเทียบ max drawdown",
            "อธิบายว่า VaR จาก historical sample มี blind spot อะไร",
        ),
    ),
    ResearchNotebookSpec(
        filename="08_liquidity_slippage.ipynb",
        slug="08-liquidity-slippage",
        title="Volume, Liquidity, and Slippage",
        quantopian_sources=("Introduction_to_Volume_Slippage_and_Liquidity", "Market_Impact_Model", "Leverage"),
        concept="ใช้ volume จาก Webull bars เพื่อทำ capacity และ slippage sanity check แบบง่าย",
        analysis_code=r"""
avg_volume_20 = prices.pivot(index="date", columns="symbol", values="volume").rolling(20).mean()
latest_volume = avg_volume_20.iloc[-1]
notional_order = pd.Series({"AAPL": 250_000, "MSFT": 250_000, "SPY": 500_000, "TSLA": 150_000})
latest_price = close.iloc[-1]
shares = notional_order / latest_price[notional_order.index]
participation = shares / latest_volume[notional_order.index]
slippage_bps = 2 + 50 * np.sqrt(participation.clip(lower=0))
liquidity = pd.DataFrame(
    {
        "latest_price": latest_price[notional_order.index],
        "order_notional": notional_order,
        "estimated_shares": shares,
        "avg_volume_20": latest_volume[notional_order.index],
        "participation_rate": participation,
        "toy_slippage_bps": slippage_bps,
    }
)
liquidity.to_csv(OUTPUT_DIR / "liquidity_slippage.csv")

fig = go.Figure()
fig.add_trace(
    go.Bar(
        x=liquidity.index,
        y=liquidity["toy_slippage_bps"],
        marker_color=THEME["primary"],
        name="Toy slippage bps",
    )
)
plot_path = save_plot(fig, "toy_slippage")
save_json(
    "liquidity_summary",
    {"plot": str(plot_path), "max_slippage_bps": float(liquidity["toy_slippage_bps"].max())},
)
liquidity.round(4)
""",
        exercises=(
            "เพิ่ม threshold ว่า participation rate เกิน 5% ต้อง warning",
            "ลอง notional order ใหญ่ขึ้น 10 เท่าแล้วดู slippage",
            "แยก liquidity risk ออกจาก alpha signal ก่อนสรุปกลยุทธ์",
        ),
    ),
    ResearchNotebookSpec(
        filename="09_overfitting_guardrails.ipynb",
        slug="09-overfitting-guardrails",
        title="Overfitting and Multiple Comparisons Guardrails",
        quantopian_sources=("The_Dangers_of_Overfitting", "p-Hacking_and_Multiple_Comparisons_Bias", "Model_Misspecification"),
        concept="จำลองการลอง parameter หลายตัว แล้วแยก in-sample/out-of-sample เพื่อเห็น overfitting",
        analysis_code=r"""
symbol = "AAPL"
symbol_returns = returns[symbol]
split = int(len(symbol_returns) * 0.6)
train = symbol_returns.iloc[:split]
test = symbol_returns.iloc[split:]

rows = []
for lookback in range(5, 81, 5):
    close_symbol = close[symbol]
    momentum = close_symbol.pct_change(lookback)
    signal = np.sign(momentum).shift(1).fillna(0)
    strategy = signal.loc[symbol_returns.index] * symbol_returns
    train_return = (1 + strategy.iloc[:split]).prod() - 1
    test_return = (1 + strategy.iloc[split:]).prod() - 1
    rows.append({"lookback": lookback, "train_return": train_return, "test_return": test_return})

grid = pd.DataFrame(rows)
best = grid.sort_values("train_return", ascending=False).iloc[0].to_dict()
grid.to_csv(OUTPUT_DIR / "parameter_grid.csv", index=False)

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=grid["lookback"],
        y=grid["train_return"],
        name="Train",
        line={"color": THEME["primary"]},
    )
)
fig.add_trace(
    go.Scatter(
        x=grid["lookback"],
        y=grid["test_return"],
        name="Test",
        line={"color": THEME["benchmark"]},
    )
)
plot_path = save_plot(fig, "overfitting_grid")
save_json("overfitting_summary", {"plot": str(plot_path), "best_by_train": best})
grid.round(4)
""",
        exercises=(
            "เปลี่ยน split เป็น 70/30 แล้วดู best parameter ใหม่",
            "เพิ่ม fee/slippage แล้วดู parameter ที่ดูดีหายไปไหม",
            "เขียน rule ว่าจะหยุดลอง parameter เมื่อไรเพื่อลด p-hacking",
        ),
    ),
)


def intro_markdown(spec: ResearchNotebookSpec) -> str:
    quantopian_items = "\n".join(f"- `{item}`" for item in spec.quantopian_sources)
    official_items = "\n".join(f"- {item}" for item in OFFICIAL_SOURCES)
    return f"""
    # {spec.title}

    Notebook นี้ replicate แนวทาง lecture/research notebook ของ QuantopianDoc ให้เข้ากับ Webull API โดยใช้ข้อมูล historical bars เป็น input หลัก.

    QuantopianDoc topics used as inspiration:
    {quantopian_items}

    Webull/OpenAPI sources:
    {official_items}

    Concept:
    - {spec.concept}
    - เริ่มจาก offline sample เพื่อ run ได้ทันที
    - เปิด live mode ได้เมื่อมี Webull credential และสิทธิ์ Market Data
    - ทุก output ถูกเขียนลง `outputs/quantopian-style/<slug>/`

    Safety:
    - ห้ามฝัง App Key, App Secret, token, account id จริงใน notebook
    - ใช้ Webull Market Data แบบ read-only เท่านั้น
    - ไม่ place, preview, replace, cancel order ใน notebook ชุดนี้
    - ผลวิจัยย้อนหลังไม่ใช่ forecast หรือคำสั่งซื้อขาย
    """


def build_notebook(spec: ResearchNotebookSpec) -> dict:
    exercises = "\n".join(f"{index}. {item}" for index, item in enumerate(spec.exercises, start=1))
    setup = COMMON_SETUP.replace("__NOTEBOOK_SLUG__", spec.slug)
    cells = [
        markdown_cell(intro_markdown(spec)),
        markdown_cell(
            """
            ## Setup and Webull-style Data Loader

            ### โค้ดช่องถัดไปทำอะไร

            - import pandas, numpy และ Plotly สำหรับ research notebook
            - สร้าง offline Webull-style OHLCV bars ที่ deterministic เพื่อให้ run ได้ทันที
            - เตรียม optional live mode ผ่าน `WEBULL_QUANTOPIAN_LIVE=1`
            - save output ลงโฟลเดอร์ประจำ notebook โดยไม่แตะ order/trading API
            """
        ),
        code_cell(setup),
        markdown_cell(
            """
            ## Data Quality Snapshot

            ### โค้ดช่องถัดไปทำอะไร

            - ตรวจช่วงวันที่และรายชื่อ symbol ที่โหลดมา
            - คำนวณ mean return และ daily volatility เบื้องต้น
            - save summary เป็น JSON เพื่อใช้เป็น artifact ตรวจซ้ำได้
            """
        ),
        code_cell(COMMON_INSPECT),
        markdown_cell(
            """
            ## Research Analysis

            ### โค้ดช่องถัดไปทำอะไร

            - ทำ analysis เฉพาะหัวข้อของ notebook นี้
            - export ตาราง/JSON/HTML chart ลง output folder
            - แสดงผลลัพธ์สุดท้ายเป็น DataFrame หรือ summary ที่อ่านง่าย
            """
        ),
        code_cell(spec.analysis_code),
        markdown_cell(
            f"""
            ## Exercises

            {exercises}

            ## Transfer to Real Webull Data

            1. ตั้งค่า `.env` ตาม README หลักของ repo
            2. ตั้ง `WEBULL_QUANTOPIAN_LIVE=1`
            3. ตรวจว่าบัญชี/แอปมี market data permission
            4. run notebook ใหม่ แล้วเทียบ offline sample กับ live Webull bars

            ## Common Mistakes

            - ใช้ parameter ที่ optimize จากทั้ง sample แล้วเรียกว่า out-of-sample
            - ลืม shift signal ก่อนคำนวณ return
            - มองข้าม fee, slippage, liquidity และ market data permission
            - สรุป historical backtest เป็น prediction
            """
        ),
    ]
    for index, cell in enumerate(cells):
        cell["id"] = f"{spec.slug}-{index:02d}"
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_readme() -> str:
    rows = "\n".join(f"{index}. [{spec.title}]({spec.filename})" for index, spec in enumerate(RESEARCH_NOTEBOOKS, start=1))
    mapping = "\n".join(
        f"- `{spec.filename}` — inspired by {', '.join(spec.quantopian_sources)}"
        for spec in RESEARCH_NOTEBOOKS
    )
    return (
        "# Webull Quantopian-Style Research Notebooks\n\n"
        "ชุดนี้ replicate รูปแบบการเรียนของ Quantopian lectures ให้ใช้กับ Webull API:\n"
        "เริ่มจาก data research notebook, ใช้ pandas/numpy/statistics, ทำกราฟและ artifact,\n"
        "แล้วค่อยต่อยอดไปสู่ risk/backtest guardrails.\n\n"
        "จุดต่างสำคัญ:\n\n"
        "- ไม่ copy เนื้อหา QuantopianDoc; ใช้เป็น curriculum inspiration เท่านั้น\n"
        "- ใช้ Webull historical bars เป็น data source เมื่อเปิด live mode\n"
        "- offline mode เป็น default จึง run ได้ใน CI และเครื่องใหม่โดยไม่ต้องมี credential\n"
        "- ไม่มี order placement หรือ trading automation\n\n"
        "## Learning Order\n\n"
        f"{rows}\n\n"
        "## Source Mapping\n\n"
        f"{mapping}\n\n"
        "## Live Mode\n\n"
        "```bash\n"
        "export WEBULL_QUANTOPIAN_LIVE=1\n"
        "export WEBULL_QUANTOPIAN_OUTPUT_DIR=outputs/quantopian-style\n"
        "```\n\n"
        "จากนั้นตั้ง `.env` ตาม README หลักของ repo แล้วเปิด notebook ที่ต้องการ.\n\n"
        "## Run Results Workflow\n\n"
        "Local offline run:\n\n"
        "```bash\n"
        "WEBULL_QUANTOPIAN_LIVE=0 python scripts/run_quantopian_style_workflow.py \\\n"
        "  --notebook-dir notebooks/quantopian_style \\\n"
        "  --output-dir site/quantopian-style/results\n\n"
        "python scripts/build_quantopian_style_dashboard.py \\\n"
        "  --results-dir site/quantopian-style/results \\\n"
        "  --site-dir site\n"
        "```\n\n"
        "Open `site/quantopian-style/index.html` to inspect the generated dashboard.\n\n"
        "GitHub run:\n\n"
        "1. Open Actions > Quantopian-Style Results.\n"
        "2. Click Run workflow.\n"
        "3. Wait for the deploy job to finish.\n"
        "4. Open `https://nutdnuy.github.io/webull-openapi-thai-lab/quantopian-style/`.\n\n"
        "The workflow forces `WEBULL_QUANTOPIAN_LIVE=0`, so it runs deterministic "
        "offline Webull-style data and does not use App Key, App Secret, token, "
        "account id, or order endpoints.\n\n"
        "## Official Sources\n\n"
        "- Webull Market Data Getting Started: "
        "https://developer.webull.com/apis/docs/market-data-api/getting-started\n"
        "- Webull Historical Bars: "
        "https://developer.webull.com/apis/docs/reference/broker-market-data-api/bars-using-get/\n"
        "- QuantopianDoc reference repo: https://github.com/nutdnuy/quantopiandoc/tree/main\n"
    )


def write_outputs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text(build_readme(), encoding="utf-8")
    for spec in RESEARCH_NOTEBOOKS:
        (out_dir / spec.filename).write_text(
            json.dumps(build_notebook(spec), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="notebooks/quantopian_style")
    args = parser.parse_args()
    write_outputs(Path(args.out_dir))


if __name__ == "__main__":
    main()
