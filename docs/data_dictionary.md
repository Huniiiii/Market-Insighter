# Data Dictionary

| Internal name | Description | Live source | Vendor symbol | Unit | Daily transformation |
|---|---|---|---|---|---|
| SPY | S&P 500 ETF | Yahoo Finance | SPY | Adjusted price | Percent return |
| XLF | US financial-sector ETF | Yahoo Finance | XLF | Adjusted price | Percent return |
| XLE | US energy-sector ETF | Yahoo Finance | XLE | Adjusted price | Percent return |
| WTI | Front-month WTI crude future | Yahoo Finance | CL=F | USD/barrel | Percent return |
| USDCAD | US dollar / Canadian dollar | Yahoo Finance | CAD=X | CAD per USD | Percent return |
| USDKRW | US dollar / Korean won | Yahoo Finance | KRW=X | KRW per USD | Percent return |
| US10Y | 10-year US Treasury yield | FRED | DGS10 | Percent | Basis-point change |
| FEDFUNDS | Effective federal funds rate | FRED | DFF | Percent | Basis-point change |
| CPI | US CPI for all urban consumers | FRED | CPIAUCSL | Index | 12-observation percent change |

## Event calendar schema

| Column | Required | Meaning |
|---|---|---|
| date | Yes | Announcement or event date |
| event | Yes | Human-readable label |
| category | No | CPI, central bank, oil, geopolitical, or other grouping |
| actual | No | Released value |
| consensus | No | Pre-event market expectation |
| surprise | No | Actual minus consensus in the same unit |

The sample CSVs are deterministic synthetic data. They demonstrate the code path and must not be interpreted as historical records.

