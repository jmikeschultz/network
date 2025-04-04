#!/usr/bin/env python3
import sys
import RPi.GPIO as GPIO

PIN = 16  # BCM 16
STATE = {"0": GPIO.LOW, "1": GPIO.HIGH}

if len(sys.argv) != 2 or sys.argv[1] not in STATE:
    print("Usage: usbpower.py [1|0]")
    sys.exit(1)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT)
GPIO.output(PIN, STATE[sys.argv[1]])
