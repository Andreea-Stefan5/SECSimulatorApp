from services.logger import logger
from database import save_task, save_satellite, update_satellite_state, delete_task
from core.strategies import HeuristicStrategy
import services.notifier as notifier

class Scheduler:
    def __init__(self, executor, monitor, strategy=None):
        self.executor = executor
        self.monitor = monitor
        self.satellites = []
        self.ground_stations = []
        self.tasks = []
        self.time = 0
        self.strategy = strategy if strategy else HeuristicStrategy()

    def add_satellite(self, sat):
        self.satellites.append(sat)
        save_satellite(sat)

    def add_ground_station(self, gs):
        self.ground_stations.append(gs)

    def add_task(self, task):
        # Called directly by GS logic (upload) or by User (if bypassing GS)
        self.tasks.append(task)
        save_task(task)

    def remove_task(self, task_id):
        task = next((t for t in self.tasks if t.task_id == task_id), None)
        if not task:
            return False
            
        if task.status == "DONE":
            return False # Cannot delete completed tasks
            
        # Cancel if scheduled
        if task.assigned_satellite:
            task.assigned_satellite.cancel_task(task)
            
        self.tasks.remove(task)
        delete_task(task_id)
        logger.info(f"Task {task_id} removed by user")
        return True

    def update_task(self, task_id, cpu, mem, energy, duration):
        task = next((t for t in self.tasks if t.task_id == task_id), None)
        if not task:
            return False
            
        if task.status == "DONE":
            return False

        # Release old resources if scheduled/running
        if task.assigned_satellite:
            task.assigned_satellite.cancel_task(task)
            task.assigned_satellite = None

        task.cpu_req = cpu
        task.mem_req = mem
        task.energy_req = energy
        task.duration = duration
        task.status = "PENDING"
        task.retries = 3 # Reset retries
        
        save_task(task)
        logger.info(f"Task {task_id} updated by user")
        return True

    def set_strategy(self, strategy):
        self.strategy = strategy
        logger.info(f"Switched scheduling strategy to {strategy.__class__.__name__}")

    def tick(self):
        import time
        current_real_time = time.time()
        self.time += 1 # Keep tick counter for other logic if needed (e.g. orbit calc), but use real time for scheduling
        
        # 0. Update Ground Stations (Uplink)
        for gs in self.ground_stations:
            gs.update(self.satellites, self)

        # 1. Executor Tick (Event-Driven)
        # Executor uses 'current_time' for task start/end. Pass real time.
        self.executor.tick(current_real_time, self.satellites)

        # 2. Filter pending tasks
        pending_tasks = []
        for task in self.tasks:
            if task.status != "PENDING":
                continue

            # Deadline check needs to be real-time aware too!
            # If task.deadline is also timestamp-based (which it is in main.py: start + duration + 100)
            if current_real_time > task.deadline:
                if task.retries > 0:
                    task.retries -= 1
                    # Extend deadline and keep pending
                    task.deadline += 50
                    logger.warning(f"Task {task.task_id} missed deadline, retrying ({task.retries} left)")
                    save_task(task)
                else:
                    task.status = "FAILED"
                    logger.warning(f"Task {task.task_id} missed deadline, FAILED")
                    save_task(task)
                    notifier.notify(f"Task {task.task_id} FAILED (Deadline Missed)")
                continue
            
            if current_real_time >= task.earliest_start:
                pending_tasks.append(task)

        # 3. Update Satellites (Orbits)
        for sat in self.satellites:
            sat.update_orbit(self.time) # Orbits can stay simulated time for visual smoothness, or use real time? 
            # If we use real time, angles will jump huge amounts. Let's keep orbit on 'tick' basis for animation smoothness.

        # 4. Use Strategy to schedule
        if pending_tasks:
            assignments = self.strategy.schedule(pending_tasks, self.satellites, current_real_time)
            
            for task, sat in assignments:
                # Double check if still valid (race condition prevention)
                if sat.can_run(task):
                     self._assign(task, sat)

    def _assign(self, task, sat):
        # Reserve resources and add to local queue
        sat.reserve_resources(task)
        sat.queue.append(task)

        task.assigned_satellite = sat
        task.status = "SCHEDULED"

        logger.info(f"Task {task.task_id} assigned to {sat.sat_id} queue")
        save_task(task)
        notifier.notify(f"TASK {task.task_id} IS ASSIGNED TO SATELLITE {sat.sat_id}")
        # Executor will pick it up in its next tick
