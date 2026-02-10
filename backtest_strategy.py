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
    bars = exchange.fetch_ohlcv('BTC/USDT', timeframe=timeframe, limit=limit)
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
                if row['low'] <= stop_price: # Assuming hit if low touches it
                    sl_hit = True
                    exit_price = stop_price # Execute at SL
                    # In real life slippage exists, but strictly:
                    if row['open'] < stop_price: exit_price = row['open'] # Gap down
            
            elif state["position"] == "SHORT":
                stop_price = state["entry_price"] + (atr_mult * state["entry_atr"])
                if row['high'] >= stop_price:
                    sl_hit = True
                    exit_price = stop_price
                    if row['open'] > stop_price: exit_price = row['open'] # Gap up
            
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
            
            # Check Signal Reversal Exit
            elif (state["position"] == "LONG" and signal == "SHORT") or \
                 (state["position"] == "SHORT" and signal == "LONG") or \
                 (state["position"] == "LONG" and score < 0) or \
                 (state["position"] == "SHORT" and score > 0): # Strict exit on sentiment flip? No, strategy says "signal reversal"
                 
                # The strategy description says "Exit: Immediate close on signal reversal"
                # Does that mean reversal of SCORE sign or reversal of SIGNAL (Long->Short)?
                # "Entry Long: +3, Short: -3. Neutral -2 to +2"
                # If I am Long, and score drops to -3 (Short signal), I flip.
                # If I am Long, and score drops to 0 (Neutral), do I exit?
                # MEMORY.md says: "Exit: Immediate close on signal reversal". usually means Long -> Short.
                # But let's check the code in btc_strategy_full.py:
                # `if current_signal != state["signal"]:` -> This implies exiting even if it goes to NEUTRAL.
                
                if signal != state["position"] and signal != "NEUTRAL":
                     # Reversal to opposite strong signal
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
                        "reason": "SIGNAL_FLIP",
                        "time": row['timestamp']
                     })
                     action = f"EXIT_{state['position']} (FLIP)"
                     state["position"] = None
                
                # Check simple exit on Neutral if the original code did that?
                # Original code: `if current_signal != state["signal"]:`
                # If signal becomes NEUTRAL (score < 3 and > -3), it exits.
                # Let's mimic that.
                elif signal == "NEUTRAL":
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
                        "reason": "NEUTRAL",
                        "time": row['timestamp']
                     })
                     action = f"EXIT_{state['position']} (NEUTRAL)"
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
print("Running Backtests...")

timeframes = ['1h', '2h', '4h']
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
        
        # Save CSV for 4h (requested by user logic)
        if tf == '4h':
            # Generate the CSV content expected by user
            csv_path = '/home/ironman/.openclaw/workspace/btc_strategy_history.csv'
            with open(csv_path, 'w') as f:
                f.write("Date,BTC Price,Signal,Action,Profit (USDT)\n")
                for h in hist:
                    profit_str = f"{h['pnl']*100:.2f}" if h['pnl'] != 0 else ""
                    f.write(f"{h['timestamp']},{h['price']:.2f},{h['signal']},{h['action']},{profit_str}\n")
                    
    except Exception as e:
        print(f"Failed for {tf}: {e}")

# --- Analysis for User Questions ---
print("\n--- ANALYSIS ---")

# 1. Signals in last 24h (from 4h timeframe)
r4h = results.get('4h')
if r4h:
    hist = r4h['history']
    # Filter last 24h
    now = hist[-1]['timestamp']
    start_24h = now - pd.Timedelta(hours=24)
    last_24h_recs = [h for h in hist if h['timestamp'] >= start_24h]
    
    signals_24h = [h for h in last_24h_recs if "ENTER" in h['action'] or "EXIT" in h['action']]
    print(f"1. Signals/Actions in last 24h (4h TF): {len(signals_24h)}")
    for s in signals_24h:
        print(f"   - {s['timestamp']} : {s['action']}")

    # 2. Stop Losses Triggered (Total in history)
    sl_trades = [t for t in r4h['trades'] if t['reason'] == "STOP_LOSS"]
    sl_last_24h = [t for t in sl_trades if t['time'] >= start_24h]
    print(f"2. Stop Losses triggered (Total): {len(sl_trades)}")
    print(f"   Stop Losses in last 24h: {len(sl_last_24h)}")

    # 4. Win Rate
    print(f"4. Win Rate (4h TF): {r4h['win_rate']:.2f}% ({len([t for t in r4h['trades'] if t['pnl']>0])}/{r4h['total_trades']})")

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
