import csv
import shift
import datetime
import pandas as pd
import time

running = False
ticker = "AAPL"
buffered_data = pd.DataFrame(columns=['datetime', 'best_bid', 'best_ask', 'bid_volume', 'ask_volume'])

def collector_loop(trader):
    global running
    buffer_count = 0
    while(running):
        
        best_price = trader.get_best_price(ticker)
        best_bid = best_price.get_bid_price()
        best_ask = best_price.get_ask_price()
        bid_volume = best_price.get_bid_size()
        ask_volume = best_price.get_ask_size()
        
        now = datetime.datetime.now()
        formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
        buffered_data.loc[len(buffered_data)] = [formatted_date, best_bid, best_ask, bid_volume, ask_volume]
        print(f"best bid: {best_bid:.2f}, best ask: {best_ask:.2f}")
        print(f"bid volume: {bid_volume}, ask volume: {ask_volume}")
        print()
        buffer_count += 1
        
        #saving every 5 mins
        if buffer_count >= 300:
            if save_data():
                buffer_count = 0
        time.sleep(1)
        
def save_data():
    global buffered_data
    print("saving...")
    try:
        existing_df = pd.read_csv('data.csv')
        updated_df = pd.concat([existing_df, buffered_data], ignore_index=True)

    except FileNotFoundError:
        print("file not found, creating new...")
        updated_df = buffered_data
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

    try:
        updated_df.to_csv('data.csv', float_format='%.2f', index=False)
        buffered_data = pd.DataFrame(columns=['datetime', 'best_bid', 'best_ask', 'bid_volume', 'ask_volume'])
        return True
    except Exception as e:
        print(f"couldn't save csv. {e}")
        return False
    

if __name__ == "__main__":
    username = "username goes here"
    password = "password goes here"
    with shift.Trader(username) as trader:
        trader.connect("initiator.cfg", password)
        if not trader.is_connected():
            raise RuntimeError("SHIFT connection failed")
        time.sleep(1)
        trader.sub_all_order_book()
        time.sleep(1)
        running = True
        collector_loop(trader)
