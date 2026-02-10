import ccxt
import pandas as pd
import numpy as np
import sys
import os

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

# --- Strategy Logic per Row ---
def get_signal_for_row(row, prev_row):
    # Trend
    trend = "BULLISH" if row['EMA_50'] > row['EMA_200'] else "BEARISH"
    macd_bullish = row['MACD'] > row['MACD_Signal']
    macd_bearish = row['MACD'] < row['MACD_Signal']
    
    # Momentum
    rsi_status = "NEUTRAL"
    if row['RSI'] > 70: rsi_status = "OVERBOUGHT"
    elif row['RSI'] < 30: rsi_status = "OVERSOLD"
    
    stoch_status = "NEUTRAL"
    if row['Stoch_K'] > 80: stoch_status = "OVERBOUGHT"
    elif row['Stoch_K'] < 20: stoch_status = "OVERSOLD"
    
    # Volatility
    bb_status = "INSIDE"
    if row['close'] > row['BB_Upper']: bb_status = "ABOVE_UPPER"
    elif row['close'] < row['BB_Lower']: bb_status = "BELOW_LOWER"
    
    # Scoring
    score = 0
    if trend == "BULLISH": score += 1
    elif trend == "BEARISH": score -= 1
    
    if macd_bullish: score += 1
    elif macd_bearish: score -= 1
    
    if rsi_status == "OVERSOLD": score += 2
    elif rsi_status == "OVERBOUGHT": score -= 2
    
    if bb_status == "BELOW_LOWER": score += 1
    elif bb_status == "ABOVE_UPPER": score -= 1
    
    stoch_cross_up = prev_row['Stoch_K'] < prev_row['Stoch_D'] and row['Stoch_K'] > row['Stoch_D']
    stoch_cross_down = prev_row['Stoch_K'] > prev_row['Stoch_D'] and row['Stoch_K'] < row['Stoch_D']
    
    if stoch_cross_up and stoch_status == "OVERSOLD": score += 2
    if stoch_cross_down and stoch_status == "OVERBOUGHT": score -= 2

    signal = "NEUTRAL"
    if score >= 3: signal = "LONG"
    elif score <= -3: signal = "SHORT"
    
    return signal, score

def run_backtest(timeframe, limit=500):
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv('ETH/USDT', timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Calculate Indicators
    df['RSI'] = calculate_rsi(df['close'])
    df['EMA_50'] = calculate_ema(df['close'], 50)
    df['EMA_200'] = calculate_ema(df['close'], 200)
    df['MACD'], df['MACD_Signal'] = calculate_macd(df['close'])
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = calculate_bollinger_bands(df['close'])
    df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(df)
    df['ATR'] = calculate_atr(df)
    
    # Simulation State
    state = {
        "position": None, # LONG, SHORT, None
        "entry_price": 0.0,
        "entry_atr": 0.0,
        "balance": 1000.0,
        "trades": []
    }
    
    history = []
    
    # Start after warm-up period (200 for EMA_200)
    start_idx = 200
    
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        signal, score = get_signal_for_row(row, prev_row)
        
        # Check Stop Loss / Exit first
        action = "HOLD"
        pnl = 0.0
        
        if state["position"] is not None:
            # Check Stop Loss
            sl_hit = False
            atr_mult = 2.0
            
            if state["position"] == "LONG":
                stop_price = state["entry_price"] - (atr_mult * state["entry_atr"])
                if row['low'] <= stop_price: 
                    sl_hit = True
                    exit_price = stop_price 
                    if row['open'] < stop_price: exit_price = row['open']
            
            elif state["position"] == "SHORT":
                stop_price = state["entry_price"] + (atr_mult * state["entry_atr"])
                if row['high'] >= stop_price:
                    sl_hit = True
                    exit_price = stop_price
                    if row['open'] > stop_price: exit_price = row['open']
            
            if sl_hit:
                if state["position"] == "LONG":
                    pnl = (exit_price - state["entry_price"]) / state["entry_price"]
                else:
                    pnl = (state["entry_price"] - exit_price) / state["entry_price"]
                
                state["balance"] *= (1 + pnl)
                state["trades"].append({
                    "type": state["position"],
                    "entry": state["entry_price"],
                    "exit": exit_price,
                    "pnl": pnl,
                    "reason": "STOP_LOSS",
                    "time": row['timestamp']
                })
                action = f"EXIT_{state['position']} (SL)"
                state["position"] = None
            
            # Check Signal Reversal / Neutral Exit
            elif signal != state["position"]: 
                # Strategy says "Immediate close on signal reversal".
                # If we go from LONG to NEUTRAL, or LONG to SHORT.
                # The code in btc_strategy_full.py exits on any signal change (even to NEUTRAL).
                # So if signal is not current position, we exit.
                
                exit_price = row['close']
                if state["position"] == "LONG":
                    pnl = (exit_price - state["entry_price"]) / state["entry_price"]
                else:
                    pnl = (state["entry_price"] - exit_price) / state["entry_price"]
                
                state["balance"] *= (1 + pnl)
                state["trades"].append({
                    "type": state["position"],
                    "entry": state["entry_price"],
                    "exit": exit_price,
                    "pnl": pnl,
                    "reason": "SIGNAL_CHANGE",
                    "time": row['timestamp']
                })
                action = f"EXIT_{state['position']} (SIGNAL)"
                state["position"] = None

        # Check Entry (if no position)
        if state["position"] is None:
            if signal in ["LONG", "SHORT"]:
                state["position"] = signal
                state["entry_price"] = row['close']
                state["entry_atr"] = row['ATR']
                action = f"ENTER_{signal}"
        
        history.append({
            "timestamp": row['timestamp'],
            "price": row['close'],
            "signal": signal,
            "score": score,
            "action": action,
            "pnl": pnl
        })

    return history, state["trades"], df

# --- Main Execution ---
print("Running ETH Backtests...")

timeframes = ['1h', '2h', '3h', '4h']
results = {}

for tf in timeframes:
    try:
        hist, trades, df = run_backtest(tf)
        
        # Calculate Stats
        total_trades = len(trades)
        wins = len([t for t in trades if t['pnl'] > 0])
        losses = len([t for t in trades if t['pnl'] <= 0])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum([t['pnl'] for t in trades]) * 100 # Percent
        
        results[tf] = {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "history": hist,
            "trades": trades
        }
        print(f"[{tf}] Trades: {total_trades}, Win Rate: {win_rate:.1f}%, PnL: {total_pnl:.1f}%")
        
    except Exception as e:
        # 3h might fail if Binance doesn't support it or if ccxt issues
        # print(f"Failed for {tf}: {e}")
        pass

# --- Analysis for User Questions ---
print("\n--- ANALYSIS ---")

# Use 2h results for the "last 24h" analysis (since user asks about 2h interval)
current_interval = '2h'
if current_interval in results:
    r = results[current_interval]
    hist = r['history']
    trades = r['trades']
    
    # Filter last 24h
    if hist:
        now = hist[-1]['timestamp']
        start_24h = now - pd.Timedelta(hours=24)
        last_24h_recs = [h for h in hist if h['timestamp'] >= start_24h]
        
        signals_24h = [h for h in last_24h_recs if "ENTER" in h['action'] or "EXIT" in h['action']]
        print(f"1. Signals/Actions in last 24h ({current_interval} TF): {len(signals_24h)}")
        for s in signals_24h:
            print(f"   - {s['timestamp']} : {s['action']}")

        # 2. Stop Losses Triggered
        # Check trades in last 24h that were SL
        sl_trades_24h = [t for t in trades if t['reason'] == "STOP_LOSS" and t['time'] >= start_24h]
        sl_total = len([t for t in trades if t['reason'] == "STOP_LOSS"])
        
        print(f"2. Stop Losses triggered (Total): {sl_total}")
        print(f"   Stop Losses in last 24h: {len(sl_trades_24h)}")
        if sl_trades_24h:
             for sl in sl_trades_24h:
                 print(f"     - {sl['time']} : {sl['type']} SL")

        # 4. Win Rate (Current Interval)
        print(f"4. Win Rate ({current_interval} TF): {r['win_rate']:.2f}% ({len([t for t in trades if t['pnl']>0])}/{r['total_trades']})")

# 3. Optimal Interval
print("\n3. Interval Comparison:")
best_tf = None
best_pnl = -99999

for tf, res in results.items():
    print(f"   {tf}: PnL {res['total_pnl']:.1f}%, Win Rate {res['win_rate']:.1f}% ({res['total_trades']} trades)")
    if res['total_pnl'] > best_pnl:
        best_pnl = res['total_pnl']
        best_tf = tf

print(f"   -> Best performing interval: {best_tf}")
