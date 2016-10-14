#!/usr/bin/env python3
"""
Python3 utility to broadcast data received from a one wire DS18B20 to MQTT
Based on sample code from
https://learn.adafruit.com/adafruits-raspberry-pi-lesson-11-ds18b20-temperature-sensing/software
"""
__author__ = "Daniel Casner <www.danielcasner.org>"

import sys
import os
import time
import json
import argparse

class Sensor(object):
    "Class wrapper around 1 wire temperature sensor"

    def __init__(self, device):
        self.device_file = device

    def read_temp_raw(self):
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def read_temp(self):
        lines = self.read_temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            temp_k = temp_c + 273.150
            return temp_c, temp_f, temp_k

def runService(sensor, client, topic, unit, interval):
    "Runs the sensor MQTT broadcast service"
    while True:
        sample = sensor.read_temp()
        client.publish(topic, json.dumps(sample[uint]), qos=0, retain=True)
        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("device", type=str, help="1 wire device to read")
    parser.add_argument("topic", type=str, help="The topic to publish temperature data on")
    parser.add_argument('-u', "--unit", choices="CFK", default='C', help="Unit to publish temperature in")
    parser.add_argument('-d', "--driver", action="store_true", help="Load 1 wire kernel drivers. Requires the script to be run as root.")
    parser.add_argument('-i', "--interval", type=int, default=30, help="Number of seconds between sensor samples")
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

    if args.driver:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

    s = Sensor(args.device)

    c = mqtt.Client(args.clientID, not args.clientID)

    c.loop_start()

    c.connect(*brokerConnect)

    if args.unit == 'C':
        unit_index = 0
    elif args.unit == 'F':
        unit_index = 1
    elif args.unit == 'K':
        unit_index = 2
    else:
        sys.exit("Unsupported unit selection: {}".format(args.unit))

    runService(s, c, args.topic, unit_index, args.interval)

    c.loop_stop()
