# Healthcare stock tickers and company stats

Generated: 2026-06-13 (UTC)

This file captures the current source locations and schema for a broad U.S.-listed healthcare ticker universe with related company statistics.

## Primary dataset

- **Dataset:** `by_industry/health_care.csv` from `Ate329/top-us-stock-tickers`
- **Raw CSV:** https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/by_industry/health_care.csv
- **Repository:** https://github.com/Ate329/top-us-stock-tickers
- **Columns:** `symbol`, `name`, `price`, `marketCap`, `volume`, `industry`
- **Coverage note:** This dataset is an automatically updated list of U.S.-listed stocks grouped by industry. The healthcare CSV includes common stocks, ADRs, preferred shares, warrants, units, and acquisition-company securities tagged to Health Care.

## Cross-check source

- **StockAnalysis sector page:** https://stockanalysis.com/stocks/sector/healthcare/
- **Reported healthcare-sector count at lookup time:** 1,056 stocks
- **Reported aggregate market cap:** $8.52 trillion
- **Reported aggregate revenue:** $4.59 trillion
- **Reported aggregate profits:** $201.34 billion
- **Reported weighted average PE ratio:** 42.31
- **Reported profit margin:** 4.39%
- **Reported dividend yield:** 0.43%

## Top healthcare tickers by market capitalization snapshot

| Rank | Symbol | Company | Market Cap | Revenue |
|---:|---|---|---:|---:|
| 1 | LLY | Eli Lilly and Company | $1.01T | $72.25B |
| 2 | JNJ | Johnson & Johnson | $579.83B | $96.36B |
| 3 | ABBV | AbbVie Inc. | $402.35B | $62.82B |
| 4 | UNH | UnitedHealth Group Incorporated | $371.00B | $449.71B |
| 5 | MRK | Merck & Co., Inc. | $294.03B | $65.77B |
| 6 | NVS | Novartis AG | $280.78B | $56.58B |
| 7 | AZN | AstraZeneca PLC | $280.26B | $60.44B |
| 8 | NVO | Novo Nordisk A/S | $197.32B | $50.57B |
| 9 | AMGN | Amgen Inc. | $191.70B | $37.22B |
| 10 | TMO | Thermo Fisher Scientific Inc. | $174.42B | $45.20B |
| 11 | GILD | Gilead Sciences, Inc. | $155.93B | $29.74B |
| 12 | ABT | Abbott Laboratories | $153.59B | $45.13B |
| 13 | PFE | Pfizer Inc. | $149.38B | $63.32B |
| 14 | ISRG | Intuitive Surgical, Inc. | $145.58B | $10.58B |
| 15 | CVS | CVS Health Corporation | $130.09B | $405.62B |
| 16 | DHR | Danaher Corporation | $127.47B | $24.78B |
| 17 | SYK | Stryker Corporation | $119.69B | $25.27B |
| 18 | BMY | Bristol-Myers Squibb Company | $116.66B | $48.48B |
| 19 | VRTX | Vertex Pharmaceuticals Incorporated | $112.92B | $12.22B |
| 20 | SNY | Sanofi | $106.43B | $54.60B |
| 21 | GSK | GSK plc | $106.31B | $43.29B |
| 22 | MDT | Medtronic plc | $102.97B | $36.36B |
| 23 | MCK | McKesson Corporation | $91.79B | $403.43B |
| 24 | ELV | Elevance Health, Inc. | $87.75B | $200.42B |
| 25 | HCA | HCA Healthcare, Inc. | $85.89B | $76.39B |

## Refresh instructions

Because security classifications, prices, volumes, and market capitalizations change daily, refresh the dataset directly from the raw CSV URL above before using it for analysis or trading. For auditability, store the downloaded CSV next to this file as `data/healthcare_stocks.csv` and keep the generated date in commit history.

Example refresh command:

```bash
python - <<'PY'
from urllib.request import Request, urlopen
url = 'https://raw.githubusercontent.com/Ate329/top-us-stock-tickers/main/by_industry/health_care.csv'
req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urlopen(req, timeout=30) as response:
    data = response.read()
open('data/healthcare_stocks.csv', 'wb').write(data)
print(f'wrote {len(data):,} bytes')
PY
```
