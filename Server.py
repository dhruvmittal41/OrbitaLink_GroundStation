
import json
import os
import time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import socketio


sio = socketio.AsyncServer(
	async_mode = 'asgi',
	cors_allowed_origins = '*',
	ping_timeout = 20,
	ping_interval = 10
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

asgi_app = socketio.ASGIApp(sio, other_asgi_app = app)

DATA_PATH = "fu_data.json"
FU_REGISTRY = {}
SID_TO_FU = {}

if os.path.exists(DATA_PATH):
	with open(DATA_PATH, "r") as f:
		FU_REGISTRY.update(json.load(f))
	print(f"[BOOT] Restored {len(FU_REGISTRY)} Field Units.")

def save_fu_registry():
	with open(DATA_PATH, "w") as f:
		json.dump(FU_REGISTRY, f, indent=2)
	print("[SAVE] FU state saved")

@app.get("/")
async def index():
	return FileResponse("static/dashboard.html")


@sio.event
async def connect(sid, environ):
	print(f"[CONNECT] {sid} connected.")
	await sio.emit("log", f"[{datetime.now().strftime('%H:%M:%S')}] Socket Connected")
	await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

@sio.event
async def disconnect(sid):

	fu_id = SID_TO_FU.pop(sid, None)
	if fu_id:
		FU_REGISTRY.pop(fu_id, None)
		print(f"[DISCONNECT] {fu_id} disconnect (SID: {sid})")
		await sio.emit("log", f"[{datetime.now().strftime('%H:%M:%S')}] {fu_id} disconnected ")
		await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})
		save_fu_registry()

@sio.on("field_unit_data")

async def handle_field_unit_data(sid, data):

	fu_id = data.get("fu_id")
	sensor_data = data.get("sebsor_data", {})

	if not fu_id:
		print("[ERROR] No FU ID in data.")
		return

	FU_REGISTRY[fu_id] = {
		"fu_id" : fu_id,
		"sensor_data" : sensor_data,
		"timestamp": time.time()
	}
	SID_TO_FU[sid] = fu_id
	await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})
	print(f"[DATA] Recieved from {fu_id} : {sensor_data}")

@sio.on("az_el_result")
async def handle_az_el_result(sid, data):
	fu_id = data.get("fu_id")
	az = data.get("az")
	el = data.get("el")
	gps = data.get("gps", {})
	sat_name = data.get("satellite_name")

	if not all([fu_id, az is not None, el is not None]):
		print(f"[ERROR] Incomplete AZ/EL result: {data}")
		return

	FU_REGISTRY.setdefault(fu_id, {}).update({
		"az": az,
		"el" : el,
		"gps" : gps,
		"satellite" : sat_name,
		"last_updated" : datetime.utcnow().isoformat()
	})

	await sio.emit("client_data_update", {"clients" : list(FU_REGISTRY.values())})
	print(f"[AZ/EL] {fu_id}: AZ={az:.2f}, EL={el:.2f} for {sat_name}")
	save_fu_registry()

@sio.on("request_clients")
async def handle_request_clients(sid):
	await sio.emit("client_data_update", {"clients": list(FU_REGISTRY.values())})

@app.get("/api/clients")
async def get_clients():
	return FU_REGISTRY

@app.post("/api/fu")
async def recieve_http_data(request: Request):
	data = await request.json()
	await handle_field_unit_data(None, data)
	return {"status" : "ok"}


