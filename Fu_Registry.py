#!/usr/bin/env python3
import socket
import json
import time
from datetime import datetime, timedelta, timezone
import threading
import os

REGISTRY_FILE = "data/active_fus.json"
UDP_IP = "0.0.0.0"
UDP_PORT = 8080

fus = {}


def load_registry():
    global fus
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                content = f.read().strip()
                if content:  # File exists and not empty
                    fus = json.loads(content)
                else:
                    fus = {}  # Empty file -> initialize empty dict
        except json.JSONDecodeError:
            print(f"[WARNING] {REGISTRY_FILE} is malformed. Resetting.")
            fus = {}
    else:
        fus = {}

def save_registry():
    with open(REGISTRY_FILE, "w") as f:
        json.dump(fus, f, indent=4)

def remove_inactive():
    while True:
        now = datetime.now(timezone.utc)
        to_remove = []
        for fid, data in fus.items():
            last_seen = datetime.fromisoformat(data["last_seen"])
            if (now - last_seen) > timedelta(minutes=5):
                print(f"[TIMEOUT] Removing inactive FU {fid}")
                to_remove.append(fid)
        for fid in to_remove:
            del fus[fid]
        save_registry()
        time.sleep(60)

def start_registry():
    load_registry()
    threading.Thread(target=remove_inactive, daemon=True).start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[LISTENING] FU Registry running on UDP {UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)
        try:
            msg = json.loads(data.decode())
            fid = msg.get("fu_id")
            if fid:
                fus[fid] = {
                    "ip": addr[0],
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "occupied_slots": msg.get("occupied_slots", [])
                }
                save_registry()
                print(f"[UPDATE] FU {fid} active @ {addr[0]}")
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    start_registry()
