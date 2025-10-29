import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from log_utils import log_event


SCHEDULE_FILE = Path("data/schedule.json")
FU_REGISTRY_FILE = Path("FU_Registry.json")
ASSIGNMENTS_FILE = Path("data/assignments.json")

BUFFER = 300

def load_schedule():
	if not SCHEDULE_FILE.exists():
		log_event(f"[ERROR] schedule.json not found.")
		return []
	return json.load(SCHEDULE_FILE.open())


def load_fu_registry():
	if not FU_REGISTRY_FILE.exists():
		log_event("[ERROR] fu_registry.json not found.")
		return {}
	return json.load(FU_REGISTRY_FILE.open())

def is_slot_available(existing_slots, new_ts):

	new_start = datetime.fromisoformat(new_ts["start_time"].replace("Z", "+00:00"))
	new_end = datetime.fromisoformat(new_ts["end_time"].replace("Z", "+00:00"))

	if not existing_slots:
		return True

	for slot in existing_slots:
		existing_start = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
		existing_end = datetime.fromisoformat(slot["end_time"].replace("Z", "")).replace(tzinfo=timezone.utc)

		if new_start < existing_end and new_end > existing_start:
			return False

	return True

def assign_passes_to_fus(schedule, fus):
	assignments = []
	updated_registry = fus.copy()

	DEFAULT_PASS_DURATION = timedelta(minutes=10)

	for entry in schedule:

		start_dt = datetime.fromisoformat(entry["start_time"].replace("Z",""))
		end_dt = start_dt + DEFAULT_PASS_DURATION
		end_dt = end_dt.replace(microsecond=0)
		print(entry)
		slot = {
			"start_time": entry["start_time"],
			"end_time": end_dt.isoformat() + "Z"
		}
		assigned = False
		print(fus.items())

		for fu_id, details in fus.items():
			existing = details.get("occupied_slots", [])
			print(existing)
			print(is_slot_available(existing, slot))
			if is_slot_available(existing, slot):

				assignments.append({
					"satellite": entry["satellite"],
					"timestamp": entry["timestamp"],
					"start_time": entry["start_time"],
					"assigned_fu": fu_id,
					"fu_ip": details["ip"]
				})
				updated_registry[fu_id]["occupied_slots"].append(slot)
				assigned = True
				log_event(f"[ASSIGNMENT] {entry['satellite']} at {entry['start_time']} --> {fu_id}")
				break
		if not assigned:
			log_event(f"[WARNING] Could not assign pass at {entry['start_time']} (all FUs busy)")
		return assignments, updated_registry

def save_assignments(assignments):
	ASSIGNMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
	with open(ASSIGNMENTS_FILE, "w") as f:
		json.dump(assignments, f, indent=4)
	log_event(f"[INFO] {len(assignments)} passes assigned and saved to assignments.json")

def save_updated_fu_registry(fus):
	with open(FU_REGISTRY_FILE, "w") as f:
		json.dump(fus, f, indent=4)
	log_event(f"[INFO] FU registry updated with new occupied slots.")

if __name__ == "__main__":

	schedule = load_schedule()
	fus = load_fu_registry()
	print(schedule)
	print(fus)
	if not schedule or not fus:
		print("[ERROR] Cannot proceed with assignment - missing data")
		exit(1)

	assignments, updated_fus = assign_passes_to_fus(schedule, fus)
	save_assignments(assignments)
	save_updated_fu_registry(updated_fus)

	print(f"[DONE] {len(assignments)} pass assignments saved.") 
