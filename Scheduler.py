#!/usr/bin/env python3
import json
from datetime import datetime, timedelta, timezone
from skyfield.api import EarthSatellite, load

# ==============================
# CONFIGURATION
# ==============================
SATELLITES_FILE = "data/satellites.json"
SCHEDULE_FILE = "data/schedule.json"

# Future: dynamically selected via UI or file input
SELECTED_SATELLITES = [
    "NOAA 15",
    "NOAA 19"
]

# Ground station (CU location)
LAT, LON, ALT = 28.6139, 77.2090, 0.216  # Example: Delhi


def generate_schedule(selected_satellites):
    """Generate a 24-hour visibility schedule for selected satellites."""
    ts = load.timescale()
    eph = load('de421.bsp')
    location = eph['earth'].topos(
        latitude_degrees=LAT,
        longitude_degrees=LON,
        elevation_m=ALT
    )

    # Load full TLE dataset
    with open(SATELLITES_FILE, "r") as f:
        satellites_data = json.load(f)

    now = datetime.now(timezone.utc)
    schedule = []

    for satname in selected_satellites:
        if satname not in satellites_data:
            print(f"[WARNING] {satname} not found in {SATELLITES_FILE}, skipping...")
            continue

        tle = satellites_data[satname]
        satellite = EarthSatellite(tle["line1"], tle["line2"], satname, ts)

        print(f"[INFO] Generating schedule for {satname}...")

        for minutes_ahead in range(0, 24 * 60, 15):  # every 15 minutes for next 24 hours
            t = ts.utc(now + timedelta(minutes=minutes_ahead))
            difference = satellite - location
            alt, az, _ = difference.at(t).altaz()

            if alt.degrees > 10:  # above horizon threshold
                entry = {
                    "satellite": satname,
                    "start_time": (now + timedelta(minutes=minutes_ahead)).isoformat(),
                    "duration": 600  # 10 min placeholder
                }
                schedule.append(entry)

        print(f"[SCHEDULE] {satname}: {len([s for s in schedule if s['satellite'] == satname])} entries")

    # Save to file
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=4)

    print(f"\n✅ Generated {len(schedule)} total schedule entries for {len(selected_satellites)} satellites.")
    print(f"📁 Output saved to: {SCHEDULE_FILE}")


if __name__ == "__main__":
    generate_schedule(SELECTED_SATELLITES)
