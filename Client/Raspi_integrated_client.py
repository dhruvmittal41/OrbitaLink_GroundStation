import time
import uuid
import math
import socketio
import threading
import geocoder
import Adafruit_DHT
import smbus2
import board
import busio
import RPi.GPIO as GPIO
import json
import os
from adafruit_as5600 import AS5600
from skyfield.api import load, wgs84, EarthSatellite

# === CONFIGURATION ===
SERVER_URL = "http://192.168.159.92:8080"
FU_ID = ':'.join(
    f"{(uuid.getnode() >> ele) & 0xff:02x}" for ele in range(40, -1, -8))

# === LOCATION ===
g = geocoder.ip('me')
LATITUDE = g.latlng[0] if g.latlng else 28.6139
LONGITUDE = g.latlng[1] if g.latlng else 77.2090
ALTITUDE = 216

# === HARDWARE CONFIG ===
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 4
DHT_INTERVAL = 2

MUX_ADDR = 0x70
ENC_CH1 = 0

RPWM1 = 9
LPWM1 = 10
M1_EN = 7

# === GLOBAL STATE ===
sio = socketio.Client()
MODE = "A"
TLE_CACHE_FILE = "all_tle_data.json"
TLE_CACHE = {}
ts = load.timescale()
last_dht_read = 0
speed_value = 200
azimuthang = 0.0

# === I2C + Encoder Setup ===
i2c = busio.I2C(board.SCL, board.SDA)
bus = smbus2.SMBus(1)


def select_i2c_channel(bus, addr, channel):
    bus.write_byte(addr, 1 << channel)


select_i2c_channel(bus, MUX_ADDR, ENC_CH1)
encoder = AS5600(i2c)

# === GPIO + PWM Setup ===
GPIO.setmode(GPIO.BCM)
GPIO.setup([RPWM1, LPWM1, M1_EN], GPIO.OUT)
GPIO.output(M1_EN, GPIO.HIGH)
pwm_r = GPIO.PWM(RPWM1, 1000)
pwm_l = GPIO.PWM(LPWM1, 1000)
pwm_r.start(0)
pwm_l.start(0)

# === TLE PERSISTENCE ===


def load_tle_cache():
    global TLE_CACHE
    if os.path.exists(TLE_CACHE_FILE):
        try:
            with open(TLE_CACHE_FILE, 'r') as f:
                raw = json.load(f)
                TLE_CACHE = {k: (v["line1"], v["line2"])
                             for k, v in raw.items()}
                print(
                    f"[TLE] Loaded {len(TLE_CACHE)} TLEs from {TLE_CACHE_FILE}")
        except Exception as e:
            print(f"[TLE] Failed to load local cache: {e}")
    else:
        print(f"[TLE] File {TLE_CACHE_FILE} not found")

# === UTILS ===


def wrap360(angle):
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def get_error(target, current):
    e = target - current
    if e > 180:
        e -= 360
    if e < -180:
        e += 360
    return e


def should_rotate(target, current, threshold=1.0):
    return abs(get_error(target, current)) >= threshold


def get_angle():
    return (encoder.raw_angle * 360.0) / 4096.0


def rotate_motor(d_angle, speed=speed_value):
    kp, ki, kd = 2.0, 0.0, 0.0
    I, prev_e = 0, 0
    start_ang = get_angle()
    target_ang = wrap360(start_ang + d_angle)
    t_end = time.time() + 5
    print(f"[ROTATE] {start_ang:.2f} -> {target_ang:.2f}")

    while time.time() < t_end:
        cur_ang = get_angle()
        e = get_error(target_ang, cur_ang)
        if abs(e) < 1:
            break
        dt = 0.01
        I += e * dt
        D = (e - prev_e) / dt
        prev_e = e
        u = kp * e + ki * I + kd * D
        pwm = min(abs(u), speed)
        if u >= 0:
            pwm_r.ChangeDutyCycle(pwm)
            pwm_l.ChangeDutyCycle(0)
        else:
            pwm_r.ChangeDutyCycle(0)
            pwm_l.ChangeDutyCycle(pwm)
        time.sleep(dt)

    pwm_r.ChangeDutyCycle(0)
    pwm_l.ChangeDutyCycle(0)

# === SENSOR + AZ/EL ===


def read_dht():
    h, t = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    if h is not None and t is not None:
        return {"temperature": t, "humidity": h, "Latitude": LATITUDE, "Longitude": LONGITUDE}
    return {}


def get_tle_by_name(sat_name):
    if sat_name in TLE_CACHE:
        return TLE_CACHE[sat_name]
    print(f"[TLE] Satellite '{sat_name}' not found in local cache")
    return None, None


def compute_az_el(sat_name):
    try:
        tle1, tle2 = get_tle_by_name(sat_name)
        if not tle1 or not tle2:
            raise Exception("Missing TLE")
        sat = EarthSatellite(tle1, tle2, sat_name, ts)
        observer = wgs84.latlon(LATITUDE, LONGITUDE, ALTITUDE)
        topocentric = (sat - observer).at(ts.now())
        alt, az, _ = topocentric.altaz()
        return round(az.degrees, 2), round(alt.degrees, 2)
    except Exception as e:
        print(f"[AZ/EL] Error: {e}")
        return None, None

# === SOCKET.IO ===


@sio.event
def connect():
    print("[SOCKET] Connected")
    send_initial_data()
    sio.start_background_task(send_sensor_loop)
    sio.start_background_task(poll_az_el_loop)


@sio.on("az_el_update")
def on_az_el_update(data):
    if data.get("fu_id") != FU_ID or MODE != "A":
        return
    sat = data.get("satellite_name")
    print(f"[AUTO] Received satellite: {sat}")
    az, el = compute_az_el(sat)
    if az is not None:
        rotate_motor(az * 2.5)
        sio.emit("az_el_result", {
            "fu_id": FU_ID,
            "az": az,
            "el": el,
            "satellite_name": sat,
            "gps": {"lat": LATITUDE, "lon": LONGITUDE, "alt": ALTITUDE}
        })

# === TASKS ===


def send_initial_data():
    sio.emit("field_unit_data", {"fu_id": FU_ID, "sensor_data": read_dht()})


def send_sensor_loop():
    while True:
        if MODE == "A":
            sio.emit("field_unit_data", {
                     "fu_id": FU_ID, "sensor_data": read_dht()})
        time.sleep(5)


def poll_az_el_loop():
    while True:
        if MODE == "A":
            sio.emit("poll_az_el", {"fu_id": FU_ID})
        time.sleep(5)


def manual_mode_loop():
    global speed_value, azimuthang
    while True:
        try:
            speed_value = int(input("Speed (0–255): "))
            angles = input("Enter azimuth,elevation: ").split(',')
            azimuthang = float(angles[0])
            rotate_motor(azimuthang)
        except:
            print("[MANUAL] Invalid input.")


def mode_controller():
    global MODE
    while True:
        mode = input("\nEnter mode (A=Auto, M=Manual): ").strip().upper()
        if mode == "A":
            MODE = "A"
            print("[MODE] Switched to AUTO")
        elif mode == "M":
            MODE = "M"
            print("[MODE] Switched to MANUAL")
            manual_mode_loop()
        else:
            print("[MODE] Invalid mode")


# === MAIN ===
if __name__ == "__main__":
    load_tle_cache()
    try:
        threading.Thread(target=mode_controller, daemon=True).start()
        while True:
            try:
                sio.connect(SERVER_URL)
                sio.wait()
            except Exception as e:
                print(f"[SOCKET] Retry in 3s: {e}")
                time.sleep(3)
    finally:
        pwm_r.stop()
        pwm_l.stop()
        GPIO.cleanup()
