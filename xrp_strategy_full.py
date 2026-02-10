#!/usr/bin/env python3
import ccxt
import pandas as pd
import numpy as np
import sys
import os
import csv
from datetime import datetime
import json
import subprocess
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib
matplotlib.use('Agg')

CSV_FILE = '/home/ironman/.openclaw/workspace/xrp_strategy_history.csv'
STATE_FILE = '/home/ironman/.openclaw/workspace/xrp_strategy_state.json'
GROUP_ID = '-1003787617512'

# --- Indicator Functions ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = calculate_ema(series, fast)
    exp2 = calculate_ema(series, slow)
    macd = exp1 - exp2
    signal_line = calculate_ema(macd, signal)
    return macd, signal_line

def calculate_bollinger_bands(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr

def generate_price_chart(df, symbol="XRP/USDT"):
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['timestamp'], df['close'], color='white', linewidth=1, label=f'{symbol} Price')
        ax.plot(df['timestamp'], calculate_ema(df['close'], 50), color='yellow', linewidth=2, label='EMA 50', alpha=0.8)
        ax.plot(df['timestamp'], calculate_ema(df['close'], 200), color='cyan', linewidth=2, label='EMA 200', alpha=0.8)
        upper, _, lower = calculate_bollinger_bands(df['close'])
        ax.fill_between(df['timestamp'], upper, lower, color='gray', alpha=0.2, label='Bollinger Bands')
        ax.set_title(f'{symbol} - 1 Hour Chart', fontsize=16, fontweight='bold')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        chart_path = f'/tmp/crypto_chart_{symbol.replace("/", "")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        return chart_path
    except Exception as e:
        print(f"Chart error: {e}")
        return None

def send_report_via_telegram(report_text, chart_path=None):
    try:
        subprocess.run(['openclaw', 'message', 'send', '--channel', 'telegram', '--target', GROUP_ID, '--message', report_text], capture_output=True)
        if chart_path:
            subprocess.run(['openclaw', 'message', 'send', '--channel', 'telegram', '--target', GROUP_ID, '--message', '📈 XRP Chart Analysis', '--media', chart_path], capture_output=True)
        return True
    except Exception as e:
        print(f"Send error: {e}")
        return False

def main():
    try:
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv('XRP/USDT', timeframe='1h', limit=500)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        rsi = calculate_rsi(df['close'])
        ema50 = calculate_ema(df['close'], 50)
        ema200 = calculate_ema(df['close'], 200)
        macd, macd_sig = calculate_macd(df['close'])
        upper, _, lower = calculate_bollinger_bands(df['close'])
        atr = calculate_atr(df)
        
        last_rsi = rsi.iloc[-1]
        last_ema50 = ema50.iloc[-1]
        last_ema200 = ema200.iloc[-1]
        last_price = df['close'].iloc[-1]
        
        score = 0
        if last_ema50 > last_ema200: score += 1
        else: score -= 1
        if last_rsi < 30: score += 2
        elif last_rsi > 70: score -= 2
        
        insights = [
            f"📊 {('BULLISH' if last_ema50 > last_ema200 else 'BEARISH')} trend established (EMA 50/200)",
            f"📊 RSI status: {'Oversold' if last_rsi < 30 else 'Overbought' if last_rsi > 70 else 'Neutral'} ({last_rsi:.1f})",
            f"📈 XRP Volatility (ATR): {atr.iloc[-1]:.4f}"
        ]
        
        chart_path = generate_price_chart(df, "XRP/USDT")
        
        report_text = f"""XRP/USDT Strategy Report (1H)
Price: ${last_price:.4f}
Signal: {'LONG' if score >= 2 else 'SHORT' if score <= -2 else 'NEUTRAL'}
Confidence: {'HIGH' if abs(score) >= 3 else 'MEDIUM'}
Score: {score}/5

🔍 Enhanced Analysis:
  {'\n  '.join(insights)}

📊 Technical Indicators:
RSI: {last_rsi:.2f}
MACD: {macd.iloc[-1]:.4f}
ATR: {atr.iloc[-1]:.4f}
BB Lower: ${lower.iloc[-1]:.4f}
BB Upper: ${upper.iloc[-1]:.4f}
EMA 50: ${last_ema50:.4f}
EMA 200: ${last_ema200:.4f}"""
        
        send_report_via_telegram(report_text, chart_path)
        
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['Date', 'XRP Price', 'Signal', 'Action'])
            if not file_exists: writer.writeheader()
            writer.writerow({'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'XRP Price': f"{last_price:.4f}", 'Signal': 'NEUTRAL', 'Action': 'REPORT'})
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
