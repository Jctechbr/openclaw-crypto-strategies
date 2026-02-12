# Crypto Trading Strategy (BTC, ETH, SOL, XRP)

## Overview
Automated swing trading strategy running on varying timeframes via Binance public data.

## Assets & Emojis
- 💰 Bitcoin (BTC/USDT) - 4-hour timeframe
- 💎 Ethereum (ETH/USDT) - 1-hour timeframe
- ☀️ Solana (SOL/USDT) - 4-hour timeframe  
- 💧 XRP (XRP/USDT) - Needs data structure improvements

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

## Job Execution Protocol

### Individual Agent Execution
- **ETH (💎)**: Every 30 minutes at :00 and :30
- **BTC (💰)**: Every 4 hours at :00 (0, 4, 8, 12, 16, 20)
- **SOL (☀️)**: Every 4 hours at :00 (0, 4, 8, 12, 16, 20) - Staggered 5 min after BTC
- **XRP (💧)**: Every 4 hours at :00 (0, 4, 8, 12, 16, 20) - Staggered 10 min after BTC

### Master Agent Validation
- **Master Agent**: `/home/ironman/scripts/crypto_trading_check.py`
- **Validation Checks**: 
  - Verify all individual agents ran successfully
  - Check for missing execution records
  - Re-run failed jobs automatically
  - Generate consolidated report with status summary

### Execution Staggering
- **ETH**: No staggering needed (30-min intervals)
- **BTC**: Base time (0:00, 4:00, 8:00, 12:00, 16:00, 20:00)
- **SOL**: BTC time + 5 minutes
- **XRP**: BTC time + 10 minutes
- **Combined Report**: BTC time + 15 minutes

### Model Optimization
- **ETH**: Use `google-antigravity/gemini-3-flash` (for momentum capture)
- **BTC**: Use `google-antigravity/gemini-3-pro-high` (for trend analysis)
- **SOL**: Use `google-antigravity/claude-opus-4-5-thinking` (for volatility analysis)
- **XRP**: Use `google-antigravity/gemini-3-flash` (for stable patterns)
- **Combined**: Use `google-antigravity/gemini-3-pro-high` (for comprehensive analysis)

### Failure Recovery
- Auto-retry failed jobs up to 3 times
- Log all execution attempts and outcomes
- Send alerts for persistent failures
- Maintain execution history for performance analysis
