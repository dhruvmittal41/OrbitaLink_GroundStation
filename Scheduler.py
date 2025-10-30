#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from skyfield.api import EarthSatellite, load

TLE_FILE = "data/tle.txt"
SCHEDULE_FILE = "data/schedule.json"

# Ground station location (CU or FU reference)
LAT, LON, ALT = 28.6139, 77.2090, 0.216  # Delhi example

def generate_schedule():
    ts = load.timescale()
    with open(TLE_FILE) as f:
        lines = f.readlines()
    satname, line1, line2 = lines[0].strip(), lines[1].strip(), lines[2].strip()
    satellite = EarthSatellite(line1, line2, satname, ts)
    location = load('de421.bsp')['earth'].topos(latitude_degrees=LAT, longitude_degrees=LON, elevation_m=ALT)

    now = datetime.now(timezone.utc)
    schedule = []

    for minutes_ahead in range(0, 24*60, 15):  # check every 15 min
        t = ts.utc(now + timedelta(minutes=minutes_ahead))
        diff = satellite - location
        alt, az, _ = diff.at(t).altaz()
        if alt.degrees > 10:  # simple visibility check
            entry = {
                "satellite": satname,
                "start_time": (now + timedelta(minutes=minutes_ahead)).isoformat(),
                "duration": 600  # 10 minutes dummy duration
            }
            schedule.append(entry)

    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=4)
    print(f"[SCHEDULE] Generated {len(schedule)} passes for {satname}")

if __name__ == "__main__":
    generate_schedule()
