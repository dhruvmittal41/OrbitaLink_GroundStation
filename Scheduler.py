import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tle_utils import load_tle, create_satellite, ts
from log_utils import log_event
from skyfield.api import wgs84



SAT_NAME_FILE = Path("data/satellite_name.json")
SCHEDULE_FILE = Path("data/schedule.json")
LOCATION = {"lat":28.6139, "lon": 77.2090, "elev_m":0}

def load_satellite_name():

	if not SAT_NAME_FILE.exists():
		log_event("[ERROR] satellite_name.json not found.")
		return None

	with open(SAT_NAME_FILE, "r") as f:
		data = json.load(f)
		return data.get("satellite_name")

def generate_pass_schedule(sat_name, observer_lat, observer_lon, observer_elev):

	satellites = load_tle("data/satellites.json")
	if sat_name not in satellites:
		log_event(f"[ERROR] Satellite '{sat_name}' not found in TLE data.")
		return []

	sat = create_satellite(satellites[sat_name]["line1"],satellites[sat_name]["line2"])
	observer = wgs84.latlon(observer_lat, observer_lon, observer_elev)

	now = datetime.now(timezone.utc)
	end_dt = now + timedelta(hours=24)
	start_time = ts.from_datetime(now)
	end_time = ts.from_datetime(end_dt)
	times, events = sat.find_events(observer, start_time, end_time, altitude_degrees = 10.0)

	schedule = []
	for ti, event in zip(times, events):

		if event ==0:
			entry = {
				"satellite": sat_name,
				"start_time": ti.utc_iso(),
				"timestamp": ti.utc_datetime().timestamp()
				}
			schedule.append(entry)

	return schedule

def save_schedule(schedule):


	SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok = True)
	with open(SCHEDULE_FILE, "w") as f:
		json.dump(schedule, f, indent=4)

	log_event(f"Generated and saved {len(schedule)} pass entries to {SCHEDULE_FILE}")


if __name__ == "__main__":
	from skyfield.api import wgs84

	observer = wgs84.latlon(LOCATION["lat"], LOCATION["lon"], LOCATION["elev_m"])
	sat_name = load_satellite_name()

	if not sat_name:
		print("[ERROR] No satellite name available. Run Fetch_Sat_Nsme.py first.")
		exit(1)

	print(f"[INFO] Generating schedule for: {sat_name}")
	schedule = generate_pass_schedule(
		sat_name,
		LOCATION["lat"],
		LOCATION["lon"],
		LOCATION["elev_m"]
	)

	if schedule:
		save_schedule(schedule)
		print(f"[DONE] Schedule saved for {sat_name}.")
	else:
		print(f"[WARNING] No visible passes found for {sat_name} in next 24 hrs.") 

