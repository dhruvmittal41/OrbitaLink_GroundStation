#!/usr/bin/env python3
import json
import asyncio
from fastapi import FastAPI
from fastapi_socketio import SocketManager
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

ASSIGN_FILE = "data/assignments.json"

app = FastAPI()
sio = SocketManager(app=app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/fu_schedule/{fu_id}")
def get_schedule(fu_id: str):
    try:
        with open(ASSIGN_FILE) as f:
            assignments = json.load(f)
        return assignments.get(fu_id, [])
    except Exception as e:
        return {"error": str(e)}

@sio.on("connect")
async def connect(sid, environ):
    print(f"[SOCKET] FU connected: {sid}")

@sio.on("fu_log")
async def handle_fu_log(sid, data):
    print(f"[LOG] {data}")
    await sio.emit("log_update", data)

@sio.on("az_el")
async def handle_az_el(sid, data):
    print(f"[DATA] {data}")
    await sio.emit("az_el_update", data)

@sio.on("disconnect")
async def disconnect(sid):
    print(f"[SOCKET] FU disconnected: {sid}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
