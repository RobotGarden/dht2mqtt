#!/usr/bin/env python3
"""
Python3 utility to broadcast data received from a DHT22 to AM2302 sensor over MQTT.
The sensor driver is based on example code from the pigpio project upon which this utility relies.
Depends on pigpio daemon running and on paho-mqtt 
"""
__author__ = "Daniel Casner <www.danielcasner.org>"


import argparse
import time
import pigpio
import json
import paho.mqtt.client as mqtt

class DHTSensor:
    """
    A class to read relative humidity and temperature from the
    DHT22 sensor.  The sensor is also known as the AM2302.

    The sensor can be powered from the Pi 3V3 or the Pi 5V rail.

    Powering from the 3V3 rail is simpler and safer.  You may need
    to power from 5V if the sensor is connected via a long cable.

    For 3V3 operation connect pin 1 to 3V3 and pin 4 to ground.

    Connect pin 2 to a gpio.

    For 5V operation connect pin 1 to 5V and pin 4 to ground.

    The following pin 2 connection works for me.  Use at YOUR OWN RISK.

    5V--5K_resistor--+--10K_resistor--Ground
                    |
    DHT22 pin 2 -----+
                    |
    gpio ------------+
    """

    MAX_NO_RESPONSE = 2

    def __init__(self, pi, gpio, LED=None, power=None):
        """
        Instantiate with the Pi and gpio to which the DHT22 output
        pin is connected.

        Optionally a LED may be specified.  This will be blinked for
        each successful reading.

        Optionally a gpio used to power the sensor may be specified.
        This gpio will be set high to power the sensor.  If the sensor
        locks it will be power cycled to restart the readings.

        Taking readings more often than about once every two seconds will
        eventually cause the DHT22 to hang.  A 3 second interval seems OK.
        """

        self.pi = pi
        self.gpio = gpio
        self.LED = LED
        self.power = power

        if power is not None:
            pi.write(power, 1)  # Switch sensor on.
            time.sleep(2)

        self.powered = True

        self.cb = None

        self.bad_CS = 0  # Bad checksum count.
        self.bad_SM = 0  # Short message count.
        self.bad_MM = 0  # Missing message count.
        self.bad_SR = 0  # Sensor reset count.

        # Power cycle if timeout > MAX_TIMEOUTS.
        self.no_response = 0

        self.rhum = None
        self.temp = None

        self.tov = None

        self.high_tick = 0
        self.bit = 40

        pi.set_pull_up_down(gpio, pigpio.PUD_OFF)

        pi.set_watchdog(gpio, 0)  # Kill any watchdogs.

        self.cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._cb)

    def __del__(self):
        self.cancel()

    def _cb(self, gpio, level, tick):
        """
        Accumulate the 40 data bits.  Format into 5 bytes, humidity high,
        humidity low, temperature high, temperature low, checksum.
        """
        diff = pigpio.tickDiff(self.high_tick, tick)

        if level == 0:
        
            # Edge length determines if bit is 1 or 0.
            if diff >= 50:
                val = 1
                if diff >= 200:   # Bad bit?
                    self.CS = 256  # Force bad checksum.
            else:
                val = 0

            if self.bit >= 40:  # Message complete.
                self.bit = 40

            elif self.bit >= 32:  # In checksum byte.
                self.CS  = (self.CS << 1)  + val

                if self.bit == 39:
                    # 40th bit received.
                    self.pi.set_watchdog(self.gpio, 0)
                    self.no_response = 0
                    total = self.hH + self.hL + self.tH + self.tL
                    if (total & 255) == self.CS:  # Is checksum ok?
                        self.rhum = ((self.hH << 8) + self.hL) * 0.1
                        if self.tH & 128:  # Negative temperature.
                            mult = -0.1
                            self.tH = self.tH & 127
                        else:
                            mult = 0.1
                        self.temp = ((self.tH << 8) + self.tL) * mult
                        self.tov = time.time()
                        if self.LED is not None:
                            self.pi.write(self.LED, 0)
                    else:
                        self.bad_CS += 1

            elif self.bit >= 24:  # in temp low byte
                self.tL = (self.tL << 1) + val

            elif self.bit >= 16:  # in temp high byte
                self.tH = (self.tH << 1) + val

            elif self.bit >= 8:  # in humidity low byte
                self.hL = (self.hL << 1) + val

            elif self.bit >= 0:  # in humidity high byte
                self.hH = (self.hH << 1) + val

            else:               # header bits
                pass

            self.bit += 1

        elif level == 1:
            self.high_tick = tick
            if diff > 250000:
                self.bit = -2
                self.hH = 0
                self.hL = 0
                self.tH = 0
                self.tL = 0
                self.CS = 0

        else:  # level == pigpio.TIMEOUT:
            self.pi.set_watchdog(self.gpio, 0)
            if self.bit < 8:       # Too few data bits received.
                self.bad_MM += 1    # Bump missing message count.
                self.no_response += 1
                if self.no_response > self.MAX_NO_RESPONSE:
                    self.no_response = 0
                    self.bad_SR += 1  # Bump sensor reset count.
                    if self.power is not None:
                        self.powered = False
                        self.pi.write(self.power, 0)
                        time.sleep(2)
                        self.pi.write(self.power, 1)
                        time.sleep(2)
                        self.powered = True
            elif self.bit < 39:    # Short message receieved.
                self.bad_SM += 1    # Bump short message count.
                self.no_response = 0

            else:                  # Full message received.
                self.no_response = 0

    @property
    def temperature(self):
       """Return current temperature."""
       return self.temp

    @property
    def humidity(self):
        """Return current relative humidity."""
        return self.rhum

    @property
    def staleness(self):
       """Return time since measurement made."""
       if self.tov is not None:
           return time.time() - self.tov
       else:
           return float('Inf')

    @property
    def bad_checksum(self):
        """Return count of messages received with bad checksums."""
        return self.bad_CS

    @property
    def short_message(self):
        """Return count of short messages."""
        return self.bad_SM

    @property
    def missing_message(self):
        """Return count of missing messages."""
        return self.bad_MM

    @property
    def sensor_resets(self):
        """Return count of power cycles because of sensor hangs."""
        return self.bad_SR

    def trigger(self):
        """Trigger a new relative humidity and temperature reading."""
        if self.powered:
            if self.LED is not None:
                self.pi.write(self.LED, 1)

            self.pi.write(self.gpio, pigpio.LOW)
            time.sleep(0.017)  # 17 ms
            self.pi.set_mode(self.gpio, pigpio.INPUT)
            self.pi.set_watchdog(self.gpio, 200)

    def cancel(self):
        """Cancel the DHT22 sensor."""
        self.pi.set_watchdog(self.gpio, 0)
        if self.cb is not None:
            self.cb.cancel()
            self.cb = None

def runService(sensor, client, topic_stem, interval):
    "Runs the DHT2MQTT service, broadcasting data at the requested interval"
    tempTopic = topic_stem + '/temperature'
    humTopic  = topic_stem + '/humidity'
    while True:
        ts = time.time()
        sensor.trigger()
        time.sleep(2)
        if (sensor.staleness < interval): # Actually have a new sensor reading to publish
            client.publish(tempTopic, json.dumps(sensor.temperature), qos=0, retain=True)
            client.publish(humTopic,  json.dumps(sensor.humidity),    qos=0, retain=True)
        time.sleep(interval - (time.time()-ts))

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
    
    pi = pigpio.pi()

    s = DHTSensor(pi, args.pin, LED=args.LED, power=args.power)
    
    c = mqtt.Client(args.clientID, not args.clientID)
    
    c.loop_start()
    
    c.connect(*brokerConnect)
    
    runService(s, c, args.topic, args.interval)
    
    c.loop_stop()
    pi.stop()
