from skyfield.api import EarthSatellite, load


ts = load.timescale()



#def clean_tle_line(line):
#	return ''.join(line.strip().split())[:69].ljust(69)


def load_tle(json_path):
	import json
	from pathlib import Path

	path = Path(json_path)
	if not path.exists():
		raise FileNotFoundError(f"TLE File not found: {json_path}")

	with path.open("r") as f:
		return json.load(f)

def create_satellite(line1, line2):
#	line1 = clean_tle_line(line1)
#	line2 = clean_tle_line(line2)
#	line1 = line1.strip().replace("\u00a0", " ").replace(" ", " ")
#	line2 = line2.strip().replace("\u00a0", " ").replace(" ", " ")
	print(f"[DEBUG] Line1 ({len(line1)}): {repr(line1)}")
	print(f"[DEBUG] Line2 ({len(line2)}): {repr(line2)}")
	return EarthSatellite(line1, line2, name="NOAA 15", ts=ts)




