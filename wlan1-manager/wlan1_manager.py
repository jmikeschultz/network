# simplified_wlan1_manager.py
import os
import time
import json
import logging
import yaml
import RPi.GPIO as GPIO
from geopy.distance import geodesic

# === CONFIG ===
PIN = 16
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT)

GPS_PATH = "/home/mike/.cache/boat/current_position.json"
CONFIG_PATH = "/home/mike/networking/wlan1-manager/wlan1_manager.yaml"

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("wlan1")

# === HELPERS ===
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
    log.info("USB power ON")

def power_off():
    GPIO.output(PIN, GPIO.LOW)
    log.info("USB power OFF")

# === MAIN LOOP ===
def run():
    log.info("Starting wlan1 manager")
    config = load_config()
    power_on()  # Always on at boot

    check_interval_secs = config.get("check_interval_secs", 3600)
    log.info(f"check_interval_secs:{check_interval_secs}")
    time.sleep(check_interval_secs)

    while True:
        config = load_config()
        gps = get_gps()

        if not gps:
            log.info("Missing GPS, keeping current state")
            time.sleep(check_interval_secs) 
            continue

        if not config.get("enable"):
            log.info("Manager disabled, keeping USB power ON")
            power_on()
        else:
            hotspot = near_hotspot(gps, config)
            if hotspot:
                log.info(f"Boat is near:{hotspot}")
                power_on()
            else:
                log.info("Boat is away")
                power_off()

        time.sleep(check_interval_secs)                            

if __name__ == "__main__":
    run()
