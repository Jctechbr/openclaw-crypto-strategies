import ccxt
import pandas as pd
import pandas_ta as ta
import time

def fetch_data(symbol='BTC/USDT', timeframe='1h', limit=500):
    try:
        # Use Binance (no API key needed for public data)
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_indicators(df):
    # Calculate RSI
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # Calculate MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    
    # Calculate EMA
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    
    return df

def analyze_strategy(df):
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    signal = "NEUTRAL"
    confidence = "LOW"
    reason = []

    # Strategy Logic
    
    # 1. Trend Filter (EMA 50 vs 200)
    if last_row['EMA_50'] > last_row['EMA_200']:
        trend = "BULLISH"
        reason.append("EMA 50 > EMA 200 (Uptrend)")
    else:
        trend = "BEARISH"
        reason.append("EMA 50 < EMA 200 (Downtrend)")

    # 2. RSI Conditions
    if last_row['RSI'] < 30:
        rsi_signal = "OVERSOLD"
        reason.append(f"RSI is {last_row['RSI']:.2f} (Oversold)")
    elif last_row['RSI'] > 70:
        rsi_signal = "OVERBOUGHT"
        reason.append(f"RSI is {last_row['RSI']:.2f} (Overbought)")
    else:
        rsi_signal = "NEUTRAL"

    # 3. MACD Crossover
    macd_bullish = last_row['MACD_12_26_9'] > last_row['MACDs_12_26_9'] and prev_row['MACD_12_26_9'] <= prev_row['MACDs_12_26_9']
    macd_bearish = last_row['MACD_12_26_9'] < last_row['MACDs_12_26_9'] and prev_row['MACD_12_26_9'] >= prev_row['MACDs_12_26_9']

    if macd_bullish:
        reason.append("MACD Bullish Crossover")
    if macd_bearish:
        reason.append("MACD Bearish Crossover")

    # Final Decision
    if trend == "BULLISH":
        if rsi_signal == "OVERSOLD" or macd_bullish:
            signal = "LONG"
            confidence = "HIGH" if (rsi_signal == "OVERSOLD" and macd_bullish) else "MEDIUM"
        elif rsi_signal == "OVERBOUGHT":
            signal = "EXIT_LONG" # Take profit
    elif trend == "BEARISH":
        if rsi_signal == "OVERBOUGHT" or macd_bearish:
            signal = "SHORT"
            confidence = "HIGH" if (rsi_signal == "OVERBOUGHT" and macd_bearish) else "MEDIUM"
        elif rsi_signal == "OVERSOLD":
            signal = "EXIT_SHORT" # Take profit

    return {
        "price": last_row['close'],
        "signal": signal,
        "confidence": confidence,
        "trend": trend,
        "reasons": reason,
        "indicators": {
            "RSI": last_row['RSI'],
            "MACD": last_row['MACD_12_26_9'],
            "EMA_50": last_row['EMA_50'],
            "EMA_200": last_row['EMA_200']
        }
    }

def main():
    print("Fetching BTC/USDT data...")
    df = fetch_data()
    if df is not None:
        df = calculate_indicators(df)
        result = analyze_strategy(df)
        
        print("\n--- BITCOIN STRATEGY REPORT ---")
        print(f"Price: ${result['price']:.2f}")
        print(f"Trend: {result['trend']}")
        print(f"Signal: {result['signal']} ({result['confidence']} Confidence)")
        print("\nReasoning:")
        for r in result['reasons']:
            print(f"- {r}")
        
        print("\nIndicators:")
        print(f"RSI: {result['indicators']['RSI']:.2f}")
        print(f"MACD: {result['indicators']['MACD']:.4f}")
        
if __name__ == "__main__":
    main()
