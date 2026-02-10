# Crypto Trading Strategy (BTC & ETH)

## Overview
Automated swing trading strategy running on 4-hour candles via Binance public data.

## Assets
- Bitcoin (BTC/USDT)
- Ethereum (ETH/USDT)

## Core Rules
- **Entry Long:** Score ≥ +3 (Strong Bullish)
- **Entry Short:** Score ≤ -3 (Strong Bearish)
- **Neutral/Hold:** Score between -2 and +2
- **Stop Loss:** Dynamic 2x ATR from entry price (Protects against volatility spikes)
- **Exit:** Immediate close on signal reversal

## Position Management
- **Simulated Capital:** 100 USDT per trade (for tracking P&L)

## Monitoring Schedule
- **Frequency:** Every 1 hour (Top of the hour)
- **Reporting:** Full detailed report sent to Telegram user `195050411` every hour, regardless of status.
- **Daily Review:** 09:00 AM (Performance check & interval optimization)

## Technical Indicators
- **Trend:** EMA 50 vs EMA 200
- **Momentum:** RSI (14), MACD (12, 26, 9), Stochastic (14, 3, 3)
- **Volatility:** Bollinger Bands (20, 2), ATR (14)
