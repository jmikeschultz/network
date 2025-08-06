import os
import time
import json
import logging
import yaml
import RPi.GPIO as GPIO
import subprocess
import re
from geopy.distance import geodesic

# === CONFIGURATION ===
PIN = 16
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT, initial=GPIO.LOW)

GPS_PATH = "/home/mike/.cache/boat/current_position.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "wlan1_manager.yaml")

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("wlan1")

# === UTILITIES ===

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.error(f"Failed to load config: {e}")
        return {}

def get_gps():
    try:
        with open(GPS_PATH) as f:
            pos = json.load(f)
            return (pos["lat"], pos["lon"])
    except Exception as e:
        log.warning(f"No GPS: {e}")
        return None

def close_enough(current, target, max_miles):
    try:
        return geodesic(current, target).miles <= max_miles
    except:
        return False

def near_hotspot(gps, hotspots, max_miles):
    for spot in hotspots:
        ref = (spot.get("lat", 0), spot.get("lon", 0))
        if close_enough(gps, ref, max_miles):
            return spot.get("name")
    return None

def get_wlan1_ssid():
    try:
        out = subprocess.check_output(["iw", "dev", "wlan1", "link"], text=True)
        match = re.search(r"SSID:\s*(.+)", out)
        return match.group(1).strip() if match else None
    except subprocess.CalledProcessError:
        return None

def has_upstream(iface="wlan1", target="8.8.8.8"):
    try:
        return subprocess.run(
            ["ping", "-I", iface, "-c", "2", "-W", "2", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).returncode == 0
    except:
        return False

def bounce_interface():
    log.info("Bouncing wlan1")
    subprocess.call(["ip", "link", "set", "wlan1", "down"])
    time.sleep(3)
    subprocess.call(["ip", "link", "set", "wlan1", "up"])
    time.sleep(15)

def power_on(cfg):
    if cfg.get("power_switch_present", True):
        GPIO.output(PIN, GPIO.HIGH)
        log.info("wlan1 power ON")
    else:
        log.info("wlan1 power ON (noop)")

def power_off(cfg):
    if cfg.get("power_switch_present", True):
        GPIO.output(PIN, GPIO.LOW)
        log.info("wlan1 power OFF")
    else:
        log.info("wlan1 power OFF (noop)")

# === MAIN LOOP ===

def run():
    log.info("Starting wlan1 manager")
    time.sleep(2)  # initial grace period

    while True:
        cfg = load_config()
        gps = get_gps()
        gps_mode = cfg.get("gps_position_control", False)
        check_secs = cfg.get("check_interval_secs", 3600)
        max_miles = cfg.get("max_miles", 1.0)
        hotspots = cfg.get("hotspots", [])

        # === POWER CONTROL ===
        if gps_mode and gps:
            hotspot = near_hotspot(gps, hotspots, max_miles)
            if hotspot:
                log.info(f"GPS near hotspot '{hotspot}' — powering ON")
                power_on(cfg)
            else:
                log.info("Not near any hotspot — powering OFF")
                power_off(cfg)
        else:
            log.info("GPS-based control disabled or no GPS — powering ON")
            power_on(cfg)

        # === WIFI + UPSTREAM WATCHDOG ===
        ssid = get_wlan1_ssid()
        upstream = has_upstream() if ssid else False

        if not ssid:
            log.info("Not connected to any SSID")
        elif not upstream:
            log.info(f"Connected to '{ssid}' but no upstream")
        else:
            log.info(f"Connected to '{ssid}', upstream OK")
            time.sleep(check_secs)
            continue

        # Bounce and recheck
        bounce_interface()
        new_ssid = get_wlan1_ssid()
        if new_ssid:
            log.info(f"After bounce, connected to: {new_ssid}")
        else:
            log.warning("After bounce, still not connected")

        time.sleep(check_secs)

if __name__ == "__main__":
    run()
