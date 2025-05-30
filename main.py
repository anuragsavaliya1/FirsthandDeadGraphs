import ccxt
import time
import telegram
from telegram import Bot
from datetime import datetime
import os
import pandas as pd
import pandas_ta as ta

# Verify python-telegram-bot version
if telegram.__version__.split('.')[0] != '13':
    raise ImportError(
        f"Unsupported python-telegram-bot version: {telegram.__version__}. Please install version 13.15 with: pip install python-telegram-bot==13.15"
    )

# Binance public client (no API keys needed)
binance = ccxt.binance()

# Telegram setup
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN',
                           '7954315913:AAEwHLzBAWSe_2KJWi5TzbMWTKME34YcziA')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '675393949')
bot = Bot(token=TELEGRAM_TOKEN)

# Test Telegram connection
try:
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Crypto Scalping Assistant with RSI started successfully!")
    print("Telegram bot initialized successfully.")
except Exception as e:
    print(f"Error initializing Telegram bot: {e}")
    exit(1)

# Configuration
PERCENTAGE_THRESHOLD = 2.0
MIN_VOLUME_USDT = 100000
CHECK_INTERVAL = 60
RISK_REWARD_RATIO = 1.5
STOP_LOSS_PERCENT = 0.5
MAX_HOLDING_TIME = 300
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70


def get_usdt_pairs():
    """Fetch all USDT trading pairs."""
    try:
        markets = binance.load_markets()
        usdt_pairs = [symbol for symbol in markets if symbol.endswith('/USDT')]
        return usdt_pairs
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []


def get_price_change_and_rsi(symbol):
    """Calculate price change and RSI for the last 1-minute candle."""
    try:
        # Fetch 1-minute candles (limit=15 for RSI calculation)
        candles = binance.fetch_ohlcv(symbol,
                                      timeframe='1m',
                                      limit=RSI_PERIOD + 1)
        if len(candles) < RSI_PERIOD + 1:
            return None, None, None
        # Extract close prices
        df = pd.DataFrame(
            candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
        rsi = df['rsi'].iloc[-1]
        # Calculate price change
        prev_candle = candles[-2]
        curr_candle = candles[-1]
        prev_close = prev_candle[4]
        curr_close = curr_candle[4]
        volume = curr_candle[5] * curr_close
        percent_change = ((curr_close - prev_close) / prev_close) * 100
        return percent_change, volume, rsi
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None, None, None


def get_volume(symbol):
    """Fetch 24h volume in USDT."""
    try:
        ticker = binance.fetch_ticker(symbol)
        return ticker['quoteVolume']
    except Exception as e:
        print(f"Error fetching volume for {symbol}: {e}")
        return 0


def send_telegram_alert(message):
    """Send alert to Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print(f"Alert sent: {message}")
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")


def suggest_entry(symbol, percent_change, curr_price, rsi):
    """Suggest entry points with RSI filter."""
    entry_price = curr_price
    if percent_change >= PERCENTAGE_THRESHOLD and rsi < RSI_OVERBOUGHT:
        # Sudden hike: Follow momentum (buy) if not overbought
        stop_loss = entry_price * (1 - STOP_LOSS_PERCENT / 100)
        take_profit = entry_price * (
            1 + (STOP_LOSS_PERCENT * RISK_REWARD_RATIO) / 100)
        signal = "BUY (Momentum)"
    elif percent_change <= -PERCENTAGE_THRESHOLD and rsi > RSI_OVERSOLD:
        # Sudden drop: Expect bounce (buy) if not oversold
        stop_loss = entry_price * (1 - STOP_LOSS_PERCENT / 100)
        take_profit = entry_price * (
            1 + (STOP_LOSS_PERCENT * RISK_REWARD_RATIO) / 100)
        signal = "BUY (Bounce)"
    else:
        return None
    return {
        'signal': signal,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'max_holding_time': MAX_HOLDING_TIME,
        'rsi': rsi
    }


def main():
    """Main function to scan pairs and generate alerts."""
    print("Starting Binance Scalping Alerts with RSI...")
    usdt_pairs = get_usdt_pairs()
    print(f"Monitoring {len(usdt_pairs)} USDT pairs...")

    while True:
        for symbol in usdt_pairs:
            try:
                percent_change, volume, rsi = get_price_change_and_rsi(symbol)
                if percent_change is None or volume is None or rsi is None:
                    continue
                if volume < MIN_VOLUME_USDT:
                    continue
                if abs(percent_change) >= PERCENTAGE_THRESHOLD:
                    ticker = binance.fetch_ticker(symbol)
                    curr_price = ticker['last']
                    signal_data = suggest_entry(symbol, percent_change,
                                                curr_price, rsi)
                    if signal_data:
                        timestamp = datetime.now().strftime("%Y-%m-d %H:%M:%S")
                        message = (
                            f"🚨 {symbol} Alert\n"
                            f"Time: {timestamp}\n"
                            f"Price Change: {percent_change:.2f}%\n"
                            f"Current Price: ${curr_price:.2f}\n"
                            f"RSI: {rsi:.2f}\n"
                            f"Signal: {signal_data['signal']}\n"
                            f"Entry: ${signal_data['entry_price']:.2f}\n"
                            f"Stop-Loss: ${signal_data['stop_loss']:.2f}\n"
                            f"Take-Profit: ${signal_data['take_profit']:.2f}\n"
                            f"Max Hold: {signal_data['max_holding_time']}s")
                        print(message)
                        send_telegram_alert(message)
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
