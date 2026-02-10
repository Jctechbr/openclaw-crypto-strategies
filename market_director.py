#!/usr/bin/env python3
import pandas as pd
import subprocess
import os
from datetime import datetime

# Paths to the individual strategy logs
LOGS = {
    'BTC': '/home/ironman/.openclaw/workspace/btc_strategy_history.csv',
    'ETH': '/home/ironman/.openclaw/workspace/eth_strategy_history.csv',
    'SOL': '/home/ironman/.openclaw/workspace/sol_strategy_history.csv',
    'XRP': '/home/ironman/.openclaw/workspace/xrp_strategy_history.csv'
}
GROUP_ID = '-1003787617512'

def get_last_result(csv_path):
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return None
        return df.iloc[-1].to_dict()
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return None

def determine_market_sentiment(results):
    signals = [r['Signal'] for r in results.values() if r]
    if not signals:
        return "⚠️ No Data", "Waiting for orchestra members to report."
    
    longs = signals.count('LONG')
    shorts = signals.count('SHORT')
    neutrals = signals.count('NEUTRAL')
    total = len(signals)

    if longs >= 3:
        return "🚀 STRONG BULLISH", f"{longs}/{total} assets are signaling LONG. Strong market momentum."
    elif shorts >= 3:
        return "📉 STRONG BEARISH", f"{shorts}/{total} assets are signaling SHORT. High selling pressure."
    elif longs > shorts:
        return "⚖️ BULLISH BIAS", "Market leaning bullish. Correlation is building."
    elif shorts > longs:
        return "⚖️ BEARISH BIAS", "Market leaning bearish. Correlation is building."
    else:
        return "💤 NEUTRAL", "Market is sideways or contradictory. Waiting for clear trend."

def main():
    results = {asset: get_last_result(path) for asset, path in LOGS.items()}
    sentiment, insight = determine_market_sentiment(results)
    
    signal_summary = ""
    for asset, data in results.items():
        emoji = "🟡" if asset == "BTC" else "🔵" if asset == "ETH" else "🟣" if asset == "SOL" else "🟢"
        price_key = f"{asset} Price"
        price = data.get(price_key, 'N/A') if data else 'N/A'
        signal = data.get('Signal', 'N/A') if data else 'N/A'
        signal_summary += f"{emoji} {asset}: {signal} (Price: ${price})\n"

    report = f"""🤵 **Market Director's Executive Summary**
Time: {datetime.now().strftime('%H:%M')}

**Global Sentiment:** {sentiment}
**Insight:** {insight}

---
**Current Signals:**
{signal_summary}
---
*Next Step: Confident correlation is required before automated execution is enabled.*
"""
    
    subprocess.run([
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--target', GROUP_ID,
        '--message', report
    ], capture_output=True, text=True)

if __name__ == "__main__":
    main()
