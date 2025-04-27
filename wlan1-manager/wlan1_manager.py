# simplified_wlan1_manager.py
import os
import time
import json
import logging
import yaml
import RPi.GPIO as GPIO
from geopy.distance import geodesic
import subprocess
import re

# === CONFIG ===
PIN = 16
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT)

GPS_PATH = "/home/mike/.cache/boat/current_position.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "wlan1_manager.yaml")

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("wlan1")

# === HELPERS ===
def get_wlan1_ssid():
    try:
        output = subprocess.check_output(["iw", "dev", "wlan1", "link"], text=True)
        match = re.search(r"SSID:\s*(.+)", output)
        if match:
            return match.group(1).strip()
        return None
    except subprocess.CalledProcessError:
        return None

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        log.error(f"Failed to load config from {CONFIG_PATH}: {e}")
        return {}

def get_gps():
    try:
        with open(GPS_PATH) as f:
            data = json.load(f)
            return (data["lat"], data["lon"])
    except Exception as e:
        log.warning(f"No GPS: {e}")
        return None

def near_hotspot(gps, config):
    max_miles = config.get("max_miles", 1.0)    
    for spot in config.get('hotspots', []):
        name = spot.get('name')
        ref = (spot.get("lat", 0), spot.get("lon", 0))
        if close_enough(gps, ref, max_miles):
            return name
    return None

def close_enough(current, target, max_miles):
    try:
        return geodesic(current, target).miles <= max_miles
    except:
        return False

def power_on():
    GPIO.output(PIN, GPIO.HIGH)
    log.info("wlan1 power ON")

def power_off():
    GPIO.output(PIN, GPIO.LOW)
    log.info("wlan1 power OFF")

# === MAIN LOOP ===
def run():
    log.info("Starting wlan1 manager")
    config = load_config()
    power_on()  # Always on at boot

    check_interval_secs = config.get("check_interval_secs", 3600)
    log.info(f"check_interval_secs:{check_interval_secs}")
    time.sleep(120) # stay on 2 minutes first time

    while True:
        config = load_config()
        gps = get_gps()

        if not gps:
            log.info("Missing GPS, keeping current state")
            time.sleep(check_interval_secs) 
            continue

        if not config.get("enable"):
            log.info("Manager disabled, keeping wlan1 power on")
            power_on()
        else:
            hotspot = near_hotspot(gps, config)
            if hotspot:
                connected_ssid = get_wlan1_ssid()
                if connected_ssid:
                    log.info(f'wlan1 is connected to:{connected_ssid}')
                else:
                    log.info(f"Boat is near:{hotspot}, turning on wlan1 power")
                    power_off() # power cycle
                    time.sleep(10)
                    power_on()
                    time.sleep(30) # give extra time to connect
            else:
                log.info("Boat is away from hotspots, turning off wlan1 power")
                power_off()

        time.sleep(check_interval_secs)                            

if __name__ == "__main__":
    run()
