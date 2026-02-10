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

CSV_FILE = '/home/ironman/.openclaw/workspace/sol_strategy_history.csv'
STATE_FILE = '/home/ironman/.openclaw/workspace/sol_strategy_state.json'
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

def calculate_sma(series, period):
    return series.rolling(window=period).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = calculate_ema(series, fast)
    exp2 = calculate_ema(series, slow)
    macd = exp1 - exp2
    signal_line = calculate_ema(macd, signal)
    return macd, signal_line

def calculate_bollinger_bands(series, period=20, std_dev=2):
    sma = calculate_sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_stochastic(df, period=14, k_period=3, d_period=3):
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    denominator = (high_max - low_min).replace(0, np.nan)
    k = 100 * ((df['close'] - low_min) / denominator)
    k_smooth = k.rolling(window=k_period).mean()
    d_smooth = k_smooth.rolling(window=d_period).mean()
    return k_smooth, d_smooth

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr

def generate_price_chart(df, symbol="SOL/USDT"):
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['timestamp'], df['close'], color='white', linewidth=1, label=f'{symbol} Price')
        ax.plot(df['timestamp'], df['EMA_50'], color='yellow', linewidth=2, label='EMA 50', alpha=0.8)
        ax.plot(df['timestamp'], df['EMA_200'], color='cyan', linewidth=2, label='EMA 200', alpha=0.8)
        ax.fill_between(df['timestamp'], df['BB_Upper'], df['BB_Lower'], color='gray', alpha=0.2, label='Bollinger Bands')
        current_price = df['close'].iloc[-1]
        ax.scatter(df['timestamp'].iloc[-1], current_price, color='red', s=100, zorder=5, label='Current Price')
        ax.set_title(f'{symbol} - 1 Hour Chart', fontsize=16, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Price (USDT)', fontsize=12)
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
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
        cmd = ['openclaw', 'message', 'send', '--channel', 'telegram', '--target', GROUP_ID, '--message', report_text]
        subprocess.run(cmd, capture_output=True, text=True)
        if chart_path:
            cmd = ['openclaw', 'message', 'send', '--channel', 'telegram', '--target', GROUP_ID, '--message', '📈 SOL Chart Analysis', '--media', chart_path]
            subprocess.run(cmd, capture_output=True, text=True)
        return True
    except Exception as e:
        print(f"Send error: {e}")
        return False

def analyze_strategy(df):
    df['RSI'] = calculate_rsi(df['close'])
    df['EMA_50'] = calculate_ema(df['close'], 50)
    df['EMA_200'] = calculate_ema(df['close'], 200)
    df['MACD'], df['MACD_Signal'] = calculate_macd(df['close'])
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = calculate_bollinger_bands(df['close'])
    df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(df)
    df['ATR'] = calculate_atr(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    score = 0
    trend = "BULLISH" if last['EMA_50'] > last['EMA_200'] else "BEARISH"
    if trend == "BULLISH": score += 1
    else: score -= 1
    if last['MACD'] > last['MACD_Signal']: score += 1
    else: score -= 1
    if last['RSI'] < 30: score += 2
    elif last['RSI'] > 70: score -= 2
    
    signal = "LONG" if score >= 3 else "SHORT" if score <= -3 else "NEUTRAL"
    confidence = "HIGH" if abs(score) >= 4 else "MEDIUM" if abs(score) >= 2 else "LOW"
    
    return {
        "price": last['close'], "signal": signal, "confidence": confidence, "score": score,
        "indicators": {
            "RSI": last['RSI'], "MACD": last['MACD'], "ATR": last['ATR'],
            "BB_Upper": last['BB_Upper'], "BB_Lower": last['BB_Lower'],
            "EMA_50": last['EMA_50'], "EMA_200": last['EMA_200']
        },
        "valid": True
    }

def main():
    try:
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv('SOL/USDT', timeframe='1h', limit=500)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        result = analyze_strategy(df)
        
        insights = [
            f"📊 {('BULLISH' if result['indicators']['EMA_50'] > result['indicators']['EMA_200'] else 'BEARISH')} trend established (EMA 50/200)",
            f"📊 RSI {'oversold' if result['indicators']['RSI'] < 30 else 'overbought' if result['indicators']['RSI'] > 70 else 'neutral'} at {result['indicators']['RSI']:.1f}",
            f"📈 SOL Volatility: {'HIGH' if result['indicators']['ATR'] > 2 else 'MODERATE'} (ATR: {result['indicators']['ATR']:.2f})"
        ]
        
        chart_path = generate_price_chart(df, "SOL/USDT")
        
        report_text = f"""SOL/USDT Strategy Report (1H)
Price: ${result['price']:.2f}
Signal: {result['signal']}
Confidence: {result['confidence']}
Score: {result['score']}/5

🔍 Enhanced Analysis:
  {'\n  '.join(insights)}

📊 Technical Indicators:
RSI: {result['indicators']['RSI']:.2f}
MACD: {result['indicators']['MACD']:.2f}
ATR: {result['indicators']['ATR']:.2f}
BB Lower: ${result['indicators']['BB_Lower']:.2f}
BB Upper: ${result['indicators']['BB_Upper']:.2f}
EMA 50: ${result['indicators']['EMA_50']:.2f}
EMA 200: ${result['indicators']['EMA_200']:.2f}"""
        
        send_report_via_telegram(report_text, chart_path)
        
        # Log to CSV
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['Date', 'SOL Price', 'Signal', 'Action'])
            if not file_exists: writer.writeheader()
            writer.writerow({'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'SOL Price': f"{result['price']:.2f}", 'Signal': result['signal'], 'Action': 'REPORT'})
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
