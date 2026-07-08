# Webull Quantopian-Style Research Notebooks

ชุดนี้ replicate รูปแบบการเรียนของ Quantopian lectures ให้ใช้กับ Webull API:
เริ่มจาก data research notebook, ใช้ pandas/numpy/statistics, ทำกราฟและ artifact,
แล้วค่อยต่อยอดไปสู่ risk/backtest guardrails.

จุดต่างสำคัญ:

- ไม่ copy เนื้อหา QuantopianDoc; ใช้เป็น curriculum inspiration เท่านั้น
- ใช้ Webull historical bars เป็น data source เมื่อเปิด live mode
- offline mode เป็น default จึง run ได้ใน CI และเครื่องใหม่โดยไม่ต้องมี credential
- ไม่มี order placement หรือ trading automation

## Learning Order

1. [Webull Research Environment](01_research_environment.ipynb)
2. [Plotting Prices and Returns](02_plotting_returns.ipynb)
3. [Autocorrelation and Simple AR Signals](03_autocorrelation_ar.ipynb)
4. [Regression Beta and CAPM Intuition](04_regression_beta.ipynb)
5. [Pairs Trading with Webull Bars](05_pairs_trading.ipynb)
6. [Ranking a Universe by Price Factors](06_factor_ranking.ipynb)
7. [Portfolio Analysis, VaR, and CVaR](07_portfolio_var_cvar.ipynb)
8. [Volume, Liquidity, and Slippage](08_liquidity_slippage.ipynb)
9. [Overfitting and Multiple Comparisons Guardrails](09_overfitting_guardrails.ipynb)

## Source Mapping

- `01_research_environment.ipynb` — inspired by Introduction_to_Research, Introduction_to_Pandas, Introduction_to_NumPy
- `02_plotting_returns.ipynb` — inspired by Plotting_Data, Means, Variance, Statistical_Moments
- `03_autocorrelation_ar.ipynb` — inspired by Autocorrelation_and_AR_Models, Instability_of_Estimates
- `04_regression_beta.ipynb` — inspired by Linear_Regression, CAPM_and_Arbitrage_Pricing_Theory, Beta_Hedging
- `05_pairs_trading.ipynb` — inspired by Introduction_to_Pairs_Trading, Integration_Cointegration_and_Stationarity
- `06_factor_ranking.ipynb` — inspired by Factor_Analysis, Ranking_Universes_by_Factors, Universe_Selection
- `07_portfolio_var_cvar.ipynb` — inspired by Portfolio_Analysis, VaR_and_CVaR, Estimating_Covariance_Matrices
- `08_liquidity_slippage.ipynb` — inspired by Introduction_to_Volume_Slippage_and_Liquidity, Market_Impact_Model, Leverage
- `09_overfitting_guardrails.ipynb` — inspired by The_Dangers_of_Overfitting, p-Hacking_and_Multiple_Comparisons_Bias, Model_Misspecification

## Live Mode

```bash
export WEBULL_QUANTOPIAN_LIVE=1
export WEBULL_QUANTOPIAN_OUTPUT_DIR=outputs/quantopian-style
```

จากนั้นตั้ง `.env` ตาม README หลักของ repo แล้วเปิด notebook ที่ต้องการ.

## Run Results Workflow

Local offline run:

```bash
WEBULL_QUANTOPIAN_LIVE=0 python scripts/run_quantopian_style_workflow.py \
  --notebook-dir notebooks/quantopian_style \
  --output-dir site/quantopian-style/results

python scripts/build_quantopian_style_dashboard.py \
  --results-dir site/quantopian-style/results \
  --site-dir site
```

Open `site/quantopian-style/index.html` to inspect the generated dashboard.

The workflow stores test output in two places:

- `site/quantopian-style/results/notebook-test-results.json` summarizes every notebook.
- `site/quantopian-style/results/<notebook-slug>/test_result.json` stores the per-notebook execution result, artifact list, and checks.

GitHub run:

1. Open Actions > Quantopian-Style Results.
2. Click Run workflow.
3. Wait for the deploy job to finish.
4. Open `https://nutdnuy.github.io/webull-openapi-thai-lab/quantopian-style/`.

The workflow forces `WEBULL_QUANTOPIAN_LIVE=0`, so it runs deterministic offline Webull-style data and does not use App Key, App Secret, token, account id, or order endpoints.

## Official Sources

- Webull Market Data Getting Started: https://developer.webull.com/apis/docs/market-data-api/getting-started
- Webull Historical Bars: https://developer.webull.com/apis/docs/reference/broker-market-data-api/bars-using-get/
- QuantopianDoc reference repo: https://github.com/nutdnuy/quantopiandoc/tree/main
