````md
# Market AI Bot

Market AI Bot is a Python-based technical analysis tool that parses Investing.com URLs, resolves the instrument type, fetches daily OHLCV data from supported providers, and calculates multiple market indicators for analysis.

This project is built for educational, research, and technical analysis practice purposes only. It does **not** provide investment advice.

---

## Overview

The script accepts an Investing.com URL from the user, identifies whether the asset is an equity or a currency/commodity pair, attempts to resolve the proper symbol, downloads daily market data, calculates multiple technical indicators, generates a rule-based signal summary, and prepares structured JSON output and an AI-ready prompt for further interpretation.

---

## Features

- Investing.com URL parsing
- Equity support
- Currency pair support
- Best-effort symbol resolution
- Data fetching from:
  - Stooq
  - Yahoo Finance
- OHLCV data cleaning and normalization
- Multi-indicator analysis
- Rule-based signal summary
- Market regime classification
- AI-ready JSON payload generation
- AI-ready technical analysis prompt generation

---

## Supported Asset Types

### Equities
Example:

```text
https://www.investing.com/equities/cloudflare-inc
````

### Currency / Commodity Pairs

Examples:

```text
https://www.investing.com/currencies/eur-usd
https://www.investing.com/currencies/usd-jpy
https://www.investing.com/currencies/xau-usd
```

---

## Calculated Indicators

The script currently calculates the following indicators:

* RSI (Wilder)
* EMA 20
* EMA 50
* EMA 200
* MACD
* Bollinger Bands
* ATR
* ADX
* +DI / -DI
* OBV
* StochRSI
* MFI
* SuperTrend

---

## How It Works

When the script runs, it asks the user to paste an Investing.com URL.

Then it performs the following steps:

1. Normalizes the URL
2. Detects the asset type from the URL
3. Builds possible provider symbols
4. Fetches daily OHLCV market data
5. Cleans and standardizes the dataset
6. Calculates technical indicators
7. Builds the latest market snapshot
8. Detects market regime and trend direction
9. Produces rule-based technical signals
10. Prints a recent indicator table
11. Generates structured JSON output
12. Generates an AI-ready prompt

---

## Requirements

* Python 3.10 or newer
* pip

Python packages:

* pandas
* requests
* yfinance

---

## Installation

Clone the repository:

```bash
git clone https://github.com/RedDawn610/rsi-multi-indicator-bot.git
cd rsi-multi-indicator-bot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the script with:

```bash
python market_ai_bot.py
```

After launching, the script will ask for an Investing.com URL.

Example input flow:

```text
Investing linki yapıştır (/equities/ veya /currencies/):
> https://www.investing.com/currencies/xau-usd

RSI periyodu? (varsayılan 14):
> 14
```

The script then outputs:

* latest close price
* RSI and trend indicators
* volatility indicators
* regime analysis
* rule-based signal summary
* recent indicator table
* AI-ready JSON payload
* AI-ready prompt text

---

## Example Output Content

The output includes information such as:

* instrument name
* data source used
* latest date
* close price
* RSI value
* EMA20 / EMA50 / EMA200
* MACD line / signal / histogram
* Bollinger band levels
* ATR
* ADX / +DI / -DI
* OBV
* StochRSI
* MFI
* SuperTrend
* regime classification
* trend direction
* signal summary

---

## Project Structure

```text
rsi-multi-indicator-bot/
├── market_ai_bot.py
├── README.md
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## Data Sources

This project attempts to fetch data from the following providers on a best-effort basis:

* Stooq
* Yahoo Finance

Investing.com is used for URL parsing and instrument identification only.

Because different data providers may use different:

* session definitions
* close prices
* volume conventions
* update timings

small discrepancies may appear across platforms.

---

## Important Notes

* This tool is built for technical analysis and experimentation.
* This tool is **not** a broker integration.
* This tool does **not** execute trades.
* This tool does **not** provide financial advice.
* Volume data may be missing or not meaningful for some FX or spot instruments.
* Indicators that depend on volume, such as MFI and OBV, may be less informative when volume quality is limited.

---

## Disclaimer

This repository and the software inside it are provided strictly for:

* education
* research
* technical analysis practice
* software development purposes

Nothing in this project should be interpreted as:

* investment advice
* financial advice
* trading advice
* portfolio management advice
* buy/sell recommendation
* risk management guidance

Financial markets involve substantial risk. Any trading or investment decision made using this software, its outputs, its indicators, or its generated interpretations is entirely the responsibility of the user.

The developer assumes **no liability** for:

* financial losses
* trading losses
* missed opportunities
* indirect damages
* decisions made based on the outputs of this tool

Always verify market data independently and use proper risk management.

---

## Limitations

Some limitations of the current implementation:

* Daily timeframe only
* Limited provider coverage
* Best-effort ticker extraction for equities
* No chart visualization yet
* No backtesting engine yet
* No portfolio tracking yet
* No real-time streaming yet

---

## Possible Future Improvements

Potential future enhancements may include:

* chart generation
* backtesting support
* multi-timeframe analysis
* CLI argument support
* CSV / Excel export
* web interface
* Streamlit dashboard
* alert system
* additional market data providers
* pattern detection
* strategy testing modules

---

## Contribution

You can fork the repository and adapt it for your own learning or development workflow.

If you want to improve the project, feel free to open an issue or submit a pull request.

---

## License

This project is distributed under the MIT License.

See the `LICENSE` file for details.

---

## Final Warning

Do not rely on this repository alone for real financial decisions.

Always combine technical analysis with:

* independent verification
* broader market context
* sound judgment
* proper risk management

```
```

