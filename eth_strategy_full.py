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

CSV_FILE = '/home/ironman/.openclaw/workspace/eth_strategy_history.csv'
STATE_FILE = '/home/ironman/.openclaw/workspace/eth_strategy_state.json'

# --- Indicator Functions ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    # Avoid division by zero
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
    # Avoid division by zero
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

def generate_price_chart(df, symbol="ETH/USDT"):
    """Generate and save a candlestick chart"""
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot candlestick chart
        ax.plot(df['timestamp'], df['close'], color='white', linewidth=1, label=f'{symbol} Price')
        
        # Plot moving averages
        ax.plot(df['timestamp'], df['EMA_50'], color='yellow', linewidth=2, label='EMA 50', alpha=0.8)
        ax.plot(df['timestamp'], df['EMA_200'], color='cyan', linewidth=2, label='EMA 200', alpha=0.8)
        
        # Plot Bollinger Bands
        ax.fill_between(df['timestamp'], df['BB_Upper'], df['BB_Lower'], 
                       color='gray', alpha=0.2, label='Bollinger Bands')
        
        # Highlight current price
        current_price = df['close'].iloc[-1]
        ax.scatter(df['timestamp'].iloc[-1], current_price, color='red', s=100, zorder=5, label='Current Price')
        
        ax.set_title(f'{symbol} - 1 Hour Chart', fontsize=16, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Price (USDT)', fontsize=12)
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = f'/tmp/crypto_chart_{symbol.replace("/", "")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        return chart_path
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None

# --- Strategy Logic ---
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
    
    # Validate indicators are ready (not NaN)
    required_indicators = ['RSI', 'EMA_50', 'EMA_200', 'MACD', 'MACD_Signal', 
                          'BB_Upper', 'BB_Lower', 'Stoch_K', 'Stoch_D', 'ATR']
    for ind in required_indicators:
        if pd.isna(last[ind]):
            return {
                "price": last['close'],
                "signal": "NEUTRAL",
                "confidence": "LOW",
                "score": 0,
                "reasons": ["Indicators warming up (insufficient data)"],
                "indicators": {k: 0.0 for k in ['RSI', 'MACD', 'ATR', 'BB_Upper', 'BB_Lower', 'EMA_50', 'EMA_200']},
                "valid": False
            }
    
    signal = "NEUTRAL"
    confidence = "LOW"
    reasons = []
    
    # Trend Analysis
    trend = "BULLISH" if last['EMA_50'] > last['EMA_200'] else "BEARISH"
    macd_bullish = last['MACD'] > last['MACD_Signal']
    macd_bearish = last['MACD'] < last['MACD_Signal']
    reasons.append(f"Trend: {trend}")

    # Momentum
    rsi_status = "NEUTRAL"
    if last['RSI'] > 70: rsi_status = "OVERBOUGHT"
    elif last['RSI'] < 30: rsi_status = "OVERSOLD"
    
    stoch_status = "NEUTRAL"
    if last['Stoch_K'] > 80: stoch_status = "OVERBOUGHT"
    elif last['Stoch_K'] < 20: stoch_status = "OVERSOLD"
    
    # Volatility
    bb_status = "INSIDE"
    if last['close'] > last['BB_Upper']: bb_status = "ABOVE_UPPER"
    elif last['close'] < last['BB_Lower']: bb_status = "BELOW_LOWER"
    
    # Scoring System
    score = 0
    if trend == "BULLISH": score += 1
    elif trend == "BEARISH": score -= 1
    if macd_bullish: score += 1
    elif macd_bearish: score -= 1
    if rsi_status == "OVERSOLD": score += 2
    elif rsi_status == "OVERBOUGHT": score -= 2
    if bb_status == "BELOW_LOWER": score += 1
    elif bb_status == "ABOVE_UPPER": score -= 1
    
    stoch_cross_up = prev['Stoch_K'] < prev['Stoch_D'] and last['Stoch_K'] > last['Stoch_D']
    stoch_cross_down = prev['Stoch_K'] > prev['Stoch_D'] and last['Stoch_K'] < last['Stoch_D']
    if stoch_cross_up and stoch_status == "OVERSOLD": score += 2
    if stoch_cross_down and stoch_status == "OVERBOUGHT": score -= 2

    if score >= 3:
        signal = "LONG"
        confidence = "HIGH" if score >= 4 else "MEDIUM"
    elif score <= -3:
        signal = "SHORT"
        confidence = "HIGH" if score <= -4 else "MEDIUM"
    else:
        signal = "NEUTRAL"
        if score > 0: reasons.append("Bias: Bullish")
        elif score < 0: reasons.append("Bias: Bearish")

    if rsi_status != "NEUTRAL": reasons.append(f"RSI {rsi_status}")
    if stoch_status != "NEUTRAL": reasons.append(f"Stoch {stoch_status}")
    if bb_status != "INSIDE": reasons.append(f"Price {bb_status} BB")
    if stoch_cross_up: reasons.append("Stoch Cross UP")
    if stoch_cross_down: reasons.append("Stoch Cross DOWN")

    return {
        "price": last['close'],
        "signal": signal,
        "confidence": confidence,
        "score": score,
        "reasons": reasons,
        "indicators": {
            "RSI": last['RSI'],
            "MACD": last['MACD'],
            "ATR": last['ATR'],
            "BB_Upper": last['BB_Upper'],
            "BB_Lower": last['BB_Lower'],
            "EMA_50": last['EMA_50'],
            "EMA_200": last['EMA_200']
        },
        "valid": True
    }

# --- State Management (JSON) ---
def load_state():
    import json
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "signal": "NEUTRAL",
        "entry_price": 0.0,
        "entry_atr": 0.0,
        "pending_signal": None
    }

def save_state(state):
    import json
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# --- Stop Loss Check ---
def check_stop_loss(current_price, state):
    if state["signal"] not in ["LONG", "SHORT"] or state["entry_price"] == 0:
        return False, "", 0.0
    
    atr_multiplier = 2.0
    entry_price = state["entry_price"]
    entry_atr = state["entry_atr"]
    
    if state["signal"] == "LONG":
        stop_price = entry_price - (atr_multiplier * entry_atr)
        if current_price <= stop_price:
            return True, f"STOP LOSS (Long): {current_price:.2f} <= {stop_price:.2f}", stop_price
    elif state["signal"] == "SHORT":
        stop_price = entry_price + (atr_multiplier * entry_atr)
        if current_price >= stop_price:
            return True, f"STOP LOSS (Short): {current_price:.2f} >= {stop_price:.2f}", stop_price
            
    return False, "", 0.0

# --- CSV Management ---
def log_to_csv(date, price, signal, action, entry_price, exit_price, profit, reasons, indicators):
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, 'a', newline='') as f:
        fieldnames = ['Date', 'ETH Price', 'Signal', 'Action', 'Entry Price', 
                     'Exit Price', 'Profit (USDT)', 'Stop Loss Level', 'Reasons', 
                     'RSI', 'MACD', 'ATR', 'BB_Lower', 'BB_Upper']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        # Calculate stop loss level for display
        stop_level = ""
        if action.startswith("ENTER"):
            atr_mult = 2.0
            if "LONG" in action:
                stop_level = f"{price - (atr_mult * indicators['ATR']):.2f}"
            elif "SHORT" in action:
                stop_level = f"{price + (atr_mult * indicators['ATR']):.2f}"
            
        writer.writerow({
            'Date': date,
            'ETH Price': f"{price:.2f}",
            'Signal': signal,
            'Action': action,
            'Entry Price': entry_price,
            'Exit Price': exit_price,
            'Profit (USDT)': profit,
            'Stop Loss Level': stop_level,
            'Reasons': "; ".join(reasons),
            'RSI': f"{indicators['RSI']:.2f}",
            'MACD': f"{indicators['MACD']:.2f}",
            'ATR': f"{indicators['ATR']:.2f}",
            'BB_Lower': f"{indicators['BB_Lower']:.2f}",
            'BB_Upper': f"{indicators['BB_Upper']:.2f}"
        })

def send_report_via_telegram(report_text, chart_path=None):
    """Send report via OpenClaw CLI message tool"""
    try:
        # Send the text report first
        cmd = [
            'openclaw', 'message', 'send',
            '--channel', 'telegram',
            '--target', '195050411',
            '--message', report_text
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Send chart if available
        if chart_path:
            cmd = [
                'openclaw', 'message', 'send',
                '--channel', 'telegram',
                '--target', '195050411',
                '--message', '📈 Price Chart Analysis',
                '--media', chart_path
            ]
            subprocess.run(cmd, capture_output=True, text=True)
        
        return True
    except Exception as e:
        print(f"Error sending report: {e}")
        return False

def main():
    try:
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv('ETH/USDT', timeframe='1h', limit=500)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        result = analyze_strategy(df)
        
        if not result.get('valid', True):
            print(f"ETH/USDT Strategy Report (1H)")
            print(f"Status: {result['reasons'][0]}")
            return
        
        state = load_state()
        current_price = result['price']
        current_signal = result['signal']
        
        # Check stop loss first
        stop_hit, stop_msg, stop_price = check_stop_loss(current_price, state)
        
        action = "HOLD"
        profit_usdt = ""
        changed = False
        
        if stop_hit:
            # Stop loss triggered - force exit
            old_signal = state["signal"]
            profit_pct = 0.0
            
            if old_signal == "LONG":
                profit_pct = (current_price - state["entry_price"]) / state["entry_price"]
            elif old_signal == "SHORT":
                profit_pct = (state["entry_price"] - current_price) / state["entry_price"]
            
            profit_usdt = f"{100 * profit_pct:.2f}"
            action = f"EXIT_{old_signal} (STOP)"
            result['reasons'].append(stop_msg)
            
            log_to_csv(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price,
                "NEUTRAL",
                action,
                f"{state['entry_price']:.2f}",
                f"{current_price:.2f}",
                profit_usdt,
                result['reasons'],
                result['indicators']
            )
            
            state = {"signal": "NEUTRAL", "entry_price": 0.0, "entry_atr": 0.0, "pending_signal": None}
            save_state(state)
            changed = True
            
        elif state.get("pending_signal"):
            # Confirm pending entry
            pending = state["pending_signal"]
            state = {
                "signal": pending,
                "entry_price": current_price,
                "entry_atr": result['indicators']['ATR'],
                "pending_signal": None
            }
            save_state(state)
            
            action = f"ENTER_{pending}"
            log_to_csv(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price,
                pending,
                action,
                f"{current_price:.2f}",
                "",
                "",
                result['reasons'],
                result['indicators']
            )
            changed = True
            
        elif current_signal != state["signal"]:
            # Signal changed
            old_signal = state["signal"]
            
            # Exit old position if exists
            if old_signal in ["LONG", "SHORT"]:
                profit_pct = 0.0
                if old_signal == "LONG":
                    profit_pct = (current_price - state["entry_price"]) / state["entry_price"]
                elif old_signal == "SHORT":
                    profit_pct = (state["entry_price"] - current_price) / state["entry_price"]
                
                profit_usdt = f"{100 * profit_pct:.2f}"
                action = f"EXIT_{old_signal}"
                
                log_to_csv(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    current_price,
                    current_signal,
                    action,
                    f"{state['entry_price']:.2f}",
                    f"{current_price:.2f}",
                    profit_usdt,
                    result['reasons'],
                    result['indicators']
                )
            
            # Set new signal as pending
            if current_signal in ["LONG", "SHORT"]:
                state = {
                    "signal": "NEUTRAL",
                    "entry_price": 0.0,
                    "entry_atr": 0.0,
                    "pending_signal": current_signal
                }
                action = f"SIGNAL_{current_signal} (PENDING)"
            else:
                state = {
                    "signal": "NEUTRAL",
                    "entry_price": 0.0,
                    "entry_atr": 0.0,
                    "pending_signal": None
                }
            
            save_state(state)
            changed = True
        
        # Generate enhanced technical analysis insights
        def generate_analysis_insights(result, df):
            insights = []
            
            # Trend insight
            trend = "BULLISH" if result['indicators']['EMA_50'] > result['indicators']['EMA_200'] else "BEARISH"
            insights.append(f"📊 {trend} trend established (EMA 50/200)")
            
            # RSI insight
            rsi = result['indicators']['RSI']
            if rsi > 70:
                insights.append(f"⚠️ RSI overbought at {rsi:.1f} - Potential reversal")
            elif rsi < 30:
                insights.append(f"📈 RSI oversold at {rsi:.1f} - Potential buying opportunity")
            else:
                insights.append(f"📊 RSI neutral at {rsi:.1f}")
            
            # MACD insight
            macd = result['indicators']['MACD']
            if macd > 0:
                insights.append(f"🟢 MACD bullish ({macd:.2f})")
            elif macd < 0:
                insights.append(f"🔴 MACD bearish ({macd:.2f})")
            else:
                insights.append(f"⚪ MACD neutral at {macd:.2f}")
            
            # Bollinger Band insight
            bb_position = "INSIDE"
            if result['price'] > result['indicators']['BB_Upper']:
                bb_position = "ABOVE_UPPER"
            elif result['price'] < result['indicators']['BB_Lower']:
                bb_position = "BELOW_LOWER"
            
            if bb_position == "ABOVE_UPPER":
                insights.append(f"🚀 Price above upper Bollinger Band - Strong momentum")
            elif bb_position == "BELOW_LOWER":
                insights.append(f"🔍 Price below lower Bollinger Band - Potential reversal")
            else:
                insights.append(f"📊 Price within Bollinger Bands range")
            
            # Volatility insight
            atr = result['indicators']['ATR']
            if atr > 50:
                volatility = "HIGH"
            elif atr < 20:
                volatility = "LOW"
            else:
                volatility = "MODERATE"
            insights.append(f"📈 Volatility: {volatility} (ATR: {atr:.2f})")
            
            # Risk Management insight
            atr_multiplier = 2.0
            if result['signal'] == "LONG":
                stop_level = result['price'] - (atr_multiplier * atr)
                risk_pct = (result['price'] - stop_level) / result['price'] * 100
                insights.append(f"💰 Recommended stop loss: ${stop_level:.2f} ({risk_pct:.1f}% risk)")
            elif result['signal'] == "SHORT":
                stop_level = result['price'] + (atr_multiplier * atr)
                risk_pct = (stop_level - result['price']) / result['price'] * 100
                insights.append(f"💰 Recommended stop loss: ${stop_level:.2f} ({risk_pct:.1f}% risk)")
            else:
                insights.append(f"⏳ No position - Risk management on hold")
            
            return insights

        # Generate chart
        chart_path = generate_price_chart(df, "ETH/USDT")
        
        # Print enhanced report (matching BTC format)
        print(f"ETH/USDT Strategy Report (1H)")
        print(f"Price: ${result['price']:.2f}")
        print(f"Signal: {result['signal']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Score: {result['score']}/5")
        
        # Print enhanced insights
        insights = generate_analysis_insights(result, df)
        print("\n🔍 Enhanced Analysis:")
        for insight in insights:
            print(f"  {insight}")
        
        if changed:
            print(f"ACTION: {action}")
            if profit_usdt:
                print(f"Profit: {profit_usdt} USDT")
        else:
            print(f"Action: HOLD")
            if state["signal"] in ["LONG", "SHORT"]:
                print(f"Active Position: {state['signal']} @ ${state['entry_price']:.2f}")
                # Show unrealized P&L
                if state["signal"] == "LONG":
                    unrealized = 100 * (current_price - state["entry_price"]) / state["entry_price"]
                else:
                    unrealized = 100 * (state["entry_price"] - current_price) / state["entry_price"]
                print(f"Unrealized P&L: {unrealized:.2f} USDT")
        
        print("Reasons:")
        for r in result['reasons']:
            print(f"- {r}")
        print("\n📊 Technical Indicators:")
        print(f"RSI: {result['indicators']['RSI']:.2f}")
        print(f"MACD: {result['indicators']['MACD']:.2f}")
        print(f"ATR: {result['indicators']['ATR']:.2f}")
        print(f"BB Lower: ${result['indicators']['BB_Lower']:.2f}")
        print(f"BB Upper: ${result['indicators']['BB_Upper']:.2f}")
        print(f"EMA 50: ${result['indicators']['EMA_50']:.2f}")
        print(f"EMA 200: ${result['indicators']['EMA_200']:.2f}")
        
        if chart_path:
            print(f"📈 Chart: {chart_path}")
            # Send report via Telegram
            report_text = f"""ETH/USDT Strategy Report (1H)
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
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
