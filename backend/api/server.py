from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)
scheduler_instance = None

# Lock to ensure thread-safe access to the scheduler instance
scheduler_lock = threading.Lock()

@app.route('/add_task', methods=['POST'])
def add_task():
    global scheduler_instance
    if not scheduler_instance:
        return jsonify({"error": "Scheduler not initialized"}), 500

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        from models.task import Task

        now = time.time()
        duration = data.get("duration", 5)
        earliest = data.get("earliest_start", now)
        deadline = data.get("deadline", earliest + duration + 100)
        
        # protect the critical section with a lock to ensure thread safety
        with scheduler_lock:
            task_id = f"API-T{len(scheduler_instance.tasks) + 1}"
             #create task object
            task = Task(
                task_id,
                data.get("cpu", 2),
                data.get("mem", 512),
                data.get("energy", 100),
                duration,
                earliest,
                deadline,
                data.get("user_id", "ExternalClient")
            )

            # add the task to the ground station's buffer
            if scheduler_instance.ground_stations:
                target_gs_id = data.get("gs_id") 
                target_gs = None

                if target_gs_id:
                    target_gs = next((gs for gs in scheduler_instance.ground_stations if gs.gs_id == target_gs_id), None)
                
                if not target_gs:
                    target_gs = scheduler_instance.ground_stations[0]

                target_gs.add_task(task)
                
                return jsonify({
                    "status": "queued_at_gs", 
                    "gs": target_gs.gs_id, 
                    "task_id": task_id
                }), 200

            else:
                scheduler_instance.add_task(task)
                return jsonify({"status": "queued_direct", "task_id": task_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/monitor', methods=['GET'])
def monitor():
    global scheduler_instance
    if not scheduler_instance:
        return jsonify({"error": "Scheduler not initialized"}), 500
        
    stats = {
        "time": scheduler_instance.time,
        "satellites": [
            {
                "id": s.sat_id,
                "energy": s.energy,
                "cpu_used": s.cpu_used,
                "queue_size": len(s.queue)
            } for s in scheduler_instance.satellites
        ],
        "tasks_done": sum(1 for t in scheduler_instance.tasks if t.status == "DONE")
    }
    return jsonify(stats), 200

def start_api(scheduler):
    global scheduler_instance
    scheduler_instance = scheduler
    
    # Run Flask in a separate thread
    thread = threading.Thread(target=lambda: app.run(host="0.0.0.0",port=5000, debug=False, use_reloader=False))
    thread.daemon = True
    thread.start()