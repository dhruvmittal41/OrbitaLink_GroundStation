#!/bin/bash
# ===========================================
# Central Unit Startup Script  
# ===========================================

set -e  # Exit immediately on error
LOG_DIR="./logs"
mkdir -p "$LOG_DIR"

timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
echo "==========================================="
echo "🚀 Starting Central Unit - $timestamp"
echo "==========================================="

# --- 1. Launch Server (FastAPI + Socket.IO) ---
echo "🔹 Launching Server.py (FastAPI backend + Socket.IO)..."
nohup python3 Server.py\
  > "$LOG_DIR/server_$timestamp.log" 2>&1 &
SERVER_PID=$!
sleep 3

# --- 2. Launch FU Registry (UDP / Socket Registry) ---
echo "🔹 Launching Fu_Registry.py..."
nohup python3 Fu_Registry.py \
  > "$LOG_DIR/fu_registry_$timestamp.log" 2>&1 &
FU_REG_PID=$!
sleep 1

# --- 3. Launch Fetch_Sat_Name (Satellite Name Fetcher) ---
echo "🔹 Launching Fetch_Sat_Name.py..."
nohup python3 Fetch_Sat_Name.py \
  > "$LOG_DIR/fetch_sat_$timestamp.log" 2>&1 &
FETCH_PID=$!
sleep 1

# --- 4. Launch Scheduler (Computes Pass Predictions) ---
echo "🔹 Launching Scheduler.py..."
nohup python3 Scheduler.py \
  > "$LOG_DIR/scheduler_$timestamp.log" 2>&1 &
SCHED_PID=$!
sleep 1

# --- 5. Launch Assigner (Allocates FU Jobs) ---
echo "🔹 Launching Assigner.py..."
nohup python3 Assigner.py \
  > "$LOG_DIR/assigner_$timestamp.log" 2>&1 &
ASSIGN_PID=$!
sleep 1

echo ""
echo "✅ All Central Unit services started successfully."
echo "-------------------------------------------"
echo "🖥️  SERVER PID      : $SERVER_PID"
echo "📡 FU REGISTRY PID  : $FU_REG_PID"
echo "🛰️  FETCH PID       : $FETCH_PID"
echo "🗓️  SCHEDULER PID   : $SCHED_PID"
echo "🎯 ASSIGNER PID     : $ASSIGN_PID"
echo "-------------------------------------------"
echo "Logs saved under: $LOG_DIR/"
echo ""

# --- Graceful Shutdown Trap ---
cleanup() {
  echo ""
  echo "🛑 Shutting down Central Unit..."
  kill $ASSIGN_PID $SCHED_PID $FETCH_PID $FU_REG_PID $SERVER_PID 2>/dev/null || true
  echo "✅ All services stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM

# --- Keep script running ---
while true; do
  sleep 10
done
