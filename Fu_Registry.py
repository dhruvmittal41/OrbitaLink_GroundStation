import socket
import json
from pathlib import Path
from log_utils import log_event


PORT = 9999
BUFFER_SIZE = 1024
FU_REGISTRY_FILE = Path("data/fu_registry.json")


def load_fu_registry():

	if FU_REGISTRY_FILE.exists():
		with FU_REGISTRY_FILE.open("r") as f:
			return json.load(f)
	return{}


def save_fu_registry(registry):


	FU_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
	with FU_REGISTRY_FILE.open("w") as f:
		json.dump(registry, f, indent=4)
	log_event(f"[INFO] FU registry updated with {len(registry)} entries.")

def get_next_fu_id(registry):

	existing_ids = [int(k[2:]) for k in registry.keys() if k.startswith("FU")]
	next_id = max(existing_ids, default=0) + 1
	return f"FU{next_id}"

def handle_fu_registration(data, addr, registry):

	try:
		payload = json.loads(data.decode())
	except json.JSONDecodeError:
		log_event(f"[ERROR] Invalid JSON from {addr}: {data}")
		return registry

	ip = addr[0]
	fu_id = payload.get("fu_id")
	occupied  = payload.get("occupied_slots", [])

	if not fu_id:
		fu_id = get_next_fu(registry)
		log_event(f"[NEW FU] Assigned ID {fu_id} to {ip}")
	else:
		log_event(f"[FU ONLINE] {fu_id} ({ip})")

	registry[fu_id] = {
		"ip": ip,
		"occupied_slots": occupied
	}

	return registry


def start_fu_registry_server():

	registry = load_fu_registry()
	log_event(f"[START] FU Registry Server started in port {PORT}.")

	with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
		server.bind(("",PORT))
		while True:
			try:
				data,addr = server.recvfrom(BUFFER_SIZE)
				registry = handle_fu_registration(data, addr, registry)
				save_fu_registry(registry)

			except keyboardInterrupt:
				print("\n[SHUTDOWN] FU registry Server stopped. ")
				log_event("[STOP] FU registry server terminanted by user. ")
				break
			except Exception as e:
				log_event(f"[ERROR] Exception in registry loop: {e}")

if __name__ == "__main__":
	start_fu_registry_server()



