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

Currency / Commodity Pairs

Examples:

https://www.investing.com/currencies/eur-usd
https://www.investing.com/currencies/usd-jpy
https://www.investing.com/currencies/xau-usd
