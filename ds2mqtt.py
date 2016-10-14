#!/usr/bin/env python3
"""
Python3 utility to broadcast data received from a one wire DS18B20 to MQTT
Based on sample code from
https://learn.adafruit.com/adafruits-raspberry-pi-lesson-11-ds18b20-temperature-sensing/software
"""
__author__ = "Daniel Casner <www.danielcasner.org>"


import os
import glob
import time
import argparse
 
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
 
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
 
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_c, temp_f



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pin", type=int, help="The GPIO pin connected to the sensor's data pin")
    parser.add_argument("topic", type=str, help="The topic stem, data will be broadcast as topic/temperature and topic/humidity")
    parser.add_argument('-i', "--interval", type=int, default=30, help="Number of seconds between sensor samples")
    parser.add_argument('-r', "--power", type=int, help="Optional GPIO pin controlling sensor power, useful for resetting the sensor")
    parser.add_argument('-l', "--LED", type=int, help="Optional GPIO pin to blink an LED every time the sensor is sampled")
    parser.add_argument("-c", "--clientID", type=str, default="", help="MQTT client ID for the counter node")
    parser.add_argument("-b", "--brokerHost", type=str, default="localhost", help="MQTT Broker hostname or IP address")
    parser.add_argument('-p', "--brokerPort", type=int, help="MQTT Broker port")
    parser.add_argument('-k', "--brokerKeepAlive", type=int, help="MQTT keep alive seconds")
    parser.add_argument('-n', "--bind", type=str, help="Local interface to bind to for connection to broker")
    parser.add_argument('-v', "--verbose", action="count", help="Increase debugging verbosity")
    args = parser.parse_args()

    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)
    
    c = mqtt.Client(args.clientID, not args.clientID)
    
    c.loop_start()
    
    c.connect(*brokerConnect)
    
    runService(s, c, args.topic, args.interval)
    
    c.loop_stop()
