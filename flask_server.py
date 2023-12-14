from flask import Flask, jsonify
import json
from serial import Serial
import threading
from flask_cors import CORS
import time
import random

MAX_DISTANCE = 260
CAN_WIDTH = 40

class CountAverage:
    def __init__(self):
        self.size = 0
        self.average = 0

    def add(self, val):
        self.average = (self.size * self.average + val) / (self.size + 1)
        self.size += 1

    def get_ave(self):
        return self.average
    
    def get_accum(self):
        return self.average * self.size
    
product_serial = Serial('/dev/ttyACM0', 9600, timeout=.5)
aisle_serial = Serial('/dev/ttyACM1', 9600, timeout=.5)
product_distance = 0
aisle_distance = 0
product_num = 0
last_buy_time = time.time()
sold_num = 0
average_stop_time = CountAverage()
average_purchase_time = CountAverage()
purchase_history = {f'{hour:02d}:{minute:02d}':random.randint(0, 3) for hour in range(0, 24) for minute in range(0, 60)}

app = Flask(__name__)
CORS(app)


    
def read_distance(serial):
    if not serial.inWaiting():
        return None
    
    try:
        s = serial.readline().decode('utf8')
    except UnicodeDecodeError:
        print('Not correct unicode')
        return None
    
    try: 
        distance = int(s)
    except ValueError:
        print('Cannot convert value')
        return None

    return distance

def read_product_serial():
    global product_distance, product_num, last_buy_time, sold_num, purchase_history
    product_num = 3
    min_error = 40
    prev_product_distance = None

    while True:
        dist = read_distance(product_serial)
        if dist is None:
            continue
        product_distance = dist
        # print("product ssensor distance:", product_distance)
        if product_distance > MAX_DISTANCE:
            continue

        if prev_product_distance is None:
            prev_product_distance = product_distance
            continue
        
        buy = product_distance > prev_product_distance + min_error
        refill = product_distance < prev_product_distance - min_error
        if buy:
            sold_num += (product_distance - prev_product_distance) // CAN_WIDTH
            prev_product_distance = product_distance
            last_buy_time = time.time()
            purchase_history[time.strftime('%H:%M')] += 1
            print('buy:', sold_num)
        elif refill:
            prev_product_distance = product_distance
            print('refill..')
        

def read_aisle_serial():
    global aisle_distance, last_buy_time, average_purchase_time, average_stop_time
    block_criteria = 1000 
    prev_aisle_distance = None
    min_error = 40
    block = False
    enter_time = 0
    leave_time = 0
    while True:
        dist = read_distance(aisle_serial) 
        if dist is None:
            continue
        aisle_distance = dist
        # print("aisle sensor distance:", aisle_distance)
        
        if prev_aisle_distance is None:
            prev_aisle_distance = aisle_distance
            continue
        
        enter = not block and aisle_distance < block_criteria and prev_aisle_distance > block_criteria
        leave = block and aisle_distance > block_criteria and prev_aisle_distance < block_criteria
        
        if enter:
            print('enter')
            block = True
            enter_time = time.time()
        elif leave:
            print('leave')
            block = False
            leave_time = time.time()
            stop_time = leave_time - enter_time
            average_stop_time.add(stop_time)
            print(f'time_diff:{stop_time:.2f}')

            if last_buy_time > enter_time:
                enter_to_buy_time = last_buy_time - enter_time
                print(f'enter to buy:{enter_to_buy_time:.2f}')
                average_purchase_time.add(enter_to_buy_time)

        prev_aisle_distance = aisle_distance
@app.route('/get_data', methods=['GET'])
def get_data():
    global product_distance, average_stop_time, average_purchase_time, sold_num
    storage = (1 - (product_distance / MAX_DISTANCE))*100
    storage = 0 if storage < 0 else storage
    storage = 100 if storage > 95 else storage 
    response = {
        "storage": storage,
        "average_stop_time": average_stop_time.get_ave(),
        "average_purchase_time": average_purchase_time.get_ave(),
        "accum_stop_time": average_stop_time.get_accum(),
        "sold_num": sold_num,
    }
    return jsonify(response)

@app.route('/get_history', methods=['GET'])
def get_history():
    global purchase_history
    response = {
        "purchase_history": purchase_history
    }
    return jsonify(response)


def start_app():
    app.run(debug=False, use_reloader=False, host="0.0.0.0", threaded=True)

if __name__ == '__main__':
    # start_app()
    app_thread = threading.Thread(target=start_app)
    product_serial_thread = threading.Thread(target=read_product_serial)
    aisle_serial_thread = threading.Thread(target=read_aisle_serial)
 
    app_thread.start()
    product_serial_thread.start()
    aisle_serial_thread.start()
 
    app_thread.join()
    product_serial_thread.join()
    aisle_serial_thread.join()
