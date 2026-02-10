# OpenClaw Crypto Trading Strategies

Automated trading strategy scripts for Bitcoin (BTC) and Ethereum (ETH) designed to run within the OpenClaw environment. These scripts perform technical analysis on Binance public data and provide actionable signals based on a multi-indicator scoring system.

## 🚀 Overview

The project currently features two main strategy implementations:
- **BTC/USDT Strategy**: Optimized for the 2-hour (2H) timeframe.
- **ETH/USDT Strategy**: Optimized for the 1-hour (1H) timeframe.

Both strategies utilize a weighted scoring system to determine market bias and entry/exit signals.

## 🛠 Features

- **Technical Indicators**: 
  - RSI (Relative Strength Index)
  - EMA (50/200) for trend detection
  - MACD (Moving Average Convergence Divergence)
  - Bollinger Bands (Volatility)
  - Stochastic Oscillator (Momentum)
  - ATR (Average True Range) for dynamic stop-loss
- **State Management**: Persists position status, entry prices, and ATR in JSON state files.
- **Logging**: Automatically logs all signals, actions, and simulated P&L to CSV history files.
- **Dynamic Stop-Loss**: Implements a 2x ATR stop-loss logic to protect against volatility spikes.
- **OpenClaw Integration**: Designed to be triggered via OpenClaw cron jobs with reports delivered directly to Telegram.

## 📈 Strategy Logic

The scripts calculate a score from -5 to +5 based on indicator alignment:
- **Trend**: +1 for Bullish EMA, -1 for Bearish.
- **Momentum**: MACD cross and Stochastic position.
- **Volatility**: Price position relative to Bollinger Bands.
- **RSI**: OVERSOLD/OVERBOUGHT status.

**Signal Thresholds:**
- **LONG**: Score ≥ +3
- **SHORT**: Score ≤ -3
- **NEUTRAL/HOLD**: Score between -2 and +2

## 📋 Prerequisites

- Python 3.10+
- `ccxt`: For exchange data (Binance)
- `pandas`: For data manipulation
- `numpy`: For calculations

Install dependencies:
```bash
pip install ccxt pandas numpy
```

## 💻 Usage

### Running Manually
To check the current status of the BTC strategy:
```bash
python3 btc_strategy_full.py
```

### Automation via OpenClaw
These scripts are intended to run on a schedule. Example OpenClaw cron configuration:

```bash
# Hourly BTC check
0 * * * * | Run btc_strategy_full.py and report to Telegram.

# Hourly ETH check
2 * * * * | Run eth_strategy_full.py and report to Telegram.
```

## 📂 File Structure

- `btc_strategy_full.py`: Primary BTC strategy script.
- `eth_strategy_full.py`: Primary ETH strategy script.
- `*_history.csv`: Trading log files.
- `*_state.json`: Current position state persistence.
- `backtest_*.py`: Simulation scripts for historical performance analysis.

## 🛡 Disclaimer
This software is for educational and research purposes only. Trading cryptocurrency involves significant risk. Never trade more than you can afford to lose.
