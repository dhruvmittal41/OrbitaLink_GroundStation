import time
import requests
import geocoder
import serial
import socketio
import uuid
import threading
import json
import os
from skyfield.api import load, wgs84, EarthSatellite

# === Configuration ===
SERVER_URL = "http://192.168.159.92:8080"
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600
ALTITUDE = 216  # meters

# === Unique FU ID ===


def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))


FU_ID = get_mac_address()

# === Geo IP Location ===
g = geocoder.ip('me')
LATITUDE = g.latlng[0] if g.latlng else 28.6139
LONGITUDE = g.latlng[1] if g.latlng else 77.2090

# === Socket.IO Client ===
sio = socketio.Client()

# === Load TLE Cache from local JSON file ===
TLE_CACHE = {}
TLE_FILE = "all_tle_data.json"
if os.path.exists(TLE_FILE):
    with open(TLE_FILE, "r") as f:
        TLE_CACHE = json.load(f)
        print(f"📄 Loaded {len(TLE_CACHE)} TLEs from {TLE_FILE}")
else:
    print(f"❌ TLE file '{TLE_FILE}' not found. AZ/EL computation will fail.")

ts = load.timescale()

# === Global Mode and Timeout State ===
MODE = "A"
last_sent_az = None
last_sent_el = None
unchanged_duration = 0
SEND_TIMEOUT = 15  # in seconds

# === Serial Setup ===
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"✅ Connected to Arduino on {SERIAL_PORT}")
except Exception as e:
    print(f"❌ Failed to open serial port {SERIAL_PORT}: {e}")
    ser = None

# === TLE Fetching from local cache ===


def get_tle_by_name(sat_name):
    tle = TLE_CACHE.get(sat_name)
    if tle:
        return tle["line1"], tle["line2"]
    else:
        print(f"❌ Satellite '{sat_name}' not found in local TLE cache.")
        return None, None

# === AZ/EL Computation ===


def compute_az_el_by_name(sat_name, lat, lon, alt=0):
    try:
        tle1, tle2 = get_tle_by_name(sat_name)
        if not tle1 or not tle2:
            raise Exception("No valid TLE lines received.")
        satellite = EarthSatellite(tle1, tle2, sat_name, ts)
        observer = wgs84.latlon(latitude_degrees=lat,
                                longitude_degrees=lon, elevation_m=alt)
        t = ts.now()
        difference = satellite - observer
        topocentric = difference.at(t)
        alt, az, _ = topocentric.altaz()
        return round(az.degrees, 2), round(alt.degrees, 2)
    except Exception as e:
        print(f"⚠️ Error computing AZ/EL: {e}")
        return None, None

# === Senders ===


def send_initial_data():
    data = {
        "fu_id": FU_ID,
        "sensor_data": {}  # Removed sensor reading
    }
    print("📤 Sending initial sensor data", data)
    sio.emit("field_unit_data", data)


def send_sensor_data():
    while True:
        if MODE == "A":
            data = {
                "fu_id": FU_ID,
                "sensor_data": {}  # Clean logs by avoiding serial reads
            }
            sio.emit("field_unit_data", data)
        time.sleep(5)


def poll_az_el_loop():
    while True:
        if MODE == "A":
            sio.emit("poll_az_el", {"fu_id": FU_ID})
        time.sleep(5)


def send_az_el_to_arduino(az_angle, el_angle, port='/dev/ttyACM0'):
    try:
        arduino = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)
        message = f"AZ: {az_angle:.2f}, EL: {el_angle:.2f}\n"
        arduino.write(message.encode('utf-8'))
        print("✅ AZ/EL sent to Arduino successfully:", message.strip())
        arduino.close()
    except serial.SerialException as e:
        print("❌ Serial error:", e)
    except Exception as e:
        print("❌ General error:", e)

# === ACTIVATE Listener ===


def wait_for_activate_input(timeout=3):
    if not ser or not ser.is_open:
        print("⚠️ Serial not available for ACTIVATE input.")
        return

    print(f"⏳ Waiting for 'ACTIVATE' input from Arduino ({timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line == "ACTIVATE":
                print("🚀 'ACTIVATE' command received!")
                handle_activate()
                return
        except Exception as e:
            print(f"⚠️ Serial read error during activate wait: {e}")
    print("⌛ Timeout reached. Continuing startup...")


def handle_activate():
    print("🟢 Activation logic triggered by 'ACTIVATE' input from Arduino!")

# === Manual Input Mode ===


def manual_mode_loop():
    while True:
        try:
            az = float(input("📝 Enter AZ angle: "))
            el = float(input("📝 Enter EL angle: "))
            send_az_el_to_arduino(az, el)
        except ValueError:
            print("⚠️ Invalid input. Please enter numeric values.")
        except KeyboardInterrupt:
            print("\n🛑 Manual mode exited.")
            break

# === Mode Controller ===


def mode_controller():
    global MODE
    while True:
        mode = input("\n🔁 Enter mode (A=Auto, M=Manual): ").strip().upper()
        if mode == "A":
            MODE = "A"
            print("⚙️ Switched to AUTOMATIC mode.")
        elif mode == "M":
            MODE = "M"
            print("⚙️ Switched to MANUAL mode. Enter angles below.")
            manual_mode_loop()
        else:
            print("⚠️ Invalid input. Please enter A or M.")

# === AZ/EL Update Event ===


@sio.on("az_el_update")
def on_az_el_update(data):
    global MODE, last_sent_az, last_sent_el, unchanged_duration

    if data.get("fu_id") != FU_ID or MODE != "A":
        return

    sat_name = data.get("satellite_name")
    if not sat_name or sat_name == "undefined":
        print("⚠️ Invalid satellite name")
        return

    az, el = compute_az_el_by_name(sat_name, LATITUDE, LONGITUDE, ALTITUDE)
    if az is None or el is None:
        print(f"⚠️ AZ/EL computation failed for {sat_name}")
        return

    # Change detection logic
    should_send = False
    if last_sent_az is None or last_sent_el is None:
        should_send = True
    elif abs(az - last_sent_az) > 1.0 or abs(el - last_sent_el) > 1.0:
        should_send = True

    if should_send:
        unchanged_duration = 0
        send_az_el_to_arduino(az, el)
        last_sent_az = az
        last_sent_el = el
    else:
        unchanged_duration += 5  # assuming this is called every 5 sec
        print(
            f"⏱️ No significant change in AZ/EL. Unchanged for {unchanged_duration}s")
        if unchanged_duration >= SEND_TIMEOUT:
            print("❌ AZ/EL unchanged for 15s. Pausing Arduino updates.")

    # Always emit result to dashboard
    sio.emit("az_el_result", {
        "fu_id": FU_ID,
        "az": az,
        "el": el,
        "satellite_name": sat_name,
        "gps": {
            "lat": LATITUDE,
            "lon": LONGITUDE,
            "alt": ALTITUDE
        }
    })

    print(f"📡 Computed AZ: {az:.2f}°, EL: {el:.2f}°")

# === Socket.IO Connect Event ===


@sio.event
def connect():
    print("✅ Connected to server")
    send_initial_data()
    sio.start_background_task(send_sensor_data)
    sio.start_background_task(poll_az_el_loop)


# === Main Runner ===
if __name__ == "__main__":
    wait_for_activate_input(timeout=3)
    threading.Thread(target=mode_controller, daemon=True).start()
    while True:
        try:
            sio.connect(SERVER_URL)
            sio.wait()
        except Exception as e:
            print(f"❌ Connection failed: {e}. Retrying in 3s...")
            time.sleep(3)
