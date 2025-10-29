echo " Starting Central Unit"

echo " Launching server.py...."

python3 -m uvicorn Server:asgi_app --host 0.0.0.0 --port 8080 &
SERVER_PID=$!
sleep 3


echo " Running Fetch_Sat_Name.py"
python3 Fetch_Sat_Name.py &
FETCH_PID=$!
sleep 1

echo "Running Scheduler.py..."
python3 Scheduler.py &
SCHED_PID=$!
sleep 1

echo "Running Assigner.py..."
python3 Assigner.py &
ASSIGN_PID=$!
sleep 1

echo "All Services started."
wait
