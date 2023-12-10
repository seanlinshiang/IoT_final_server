from flask import Flask, jsonify
import json
from serial import Serial
import threading
from flask_cors import CORS
import time

MAX_HISTORY_LEN = 10

product_serial = Serial('/dev/ttyACM0', 9600, timeout=.5)
aisle_serial = Serial('/dev/ttyACM1', 9600, timeout=.5)
product_distance = 0
aisle_distance = 0
product_num = 0



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
    global product_distance, product_num
    product_num = 3
    min_error = 40
    prev_product_distance = None

    while True:
        dist = read_distance(product_serial)
        if dist is None:
            continue
        product_distance = dist
        print("product sensor distance:", product_distance)

        if prev_product_distance is None:
            prev_product_distance = product_distance
            continue
        
        taken = product_distance > prev_product_distance + min_error
        refill = product_distance < prev_product_distance - min_error
        if taken:
            product_num -= 1
            prev_product_distance = product_distance
            print('taken:', product_num)
        elif refill:
            product_num += 1
            prev_product_distance = product_distance
            print('refill:', product_num)
        

def read_aisle_serial():
    global aisle_distance
    prev_aisle_distance = None
    min_error = 100
    block = False
    enter_time = 0
    leave_time = 0
    while True:
        dist = read_distance(aisle_serial) 
        if dist is None:
            continue
        aisle_distance = dist
        print("aisle sensor distance:", aisle_distance)
        
        if prev_aisle_distance is None:
            prev_aisle_distance = aisle_distance
            continue
        
        enter = not block and aisle_distance < prev_aisle_distance - min_error
        leave = block and aisle_distance > prev_aisle_distance + min_error
        
        if enter:
            block = True
            enter_time = time.time()
            print('enter')
            prev_aisle_distance = aisle_distance
        elif leave:
            block = False
            leave_time = time.time()
            time_diff = leave_time - enter_time
            print(f'time_dif:{time_diff:.2f}')
            print('leave')
            prev_aisle_distance = aisle_distance

@app.route('/storage', methods=['GET'])
def storage():
    global product_distance
    return jsonify(message=product_distance)


def start_app():
    app.run(debug=True, use_reloader=False, host="0.0.0.0", threaded=True)

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