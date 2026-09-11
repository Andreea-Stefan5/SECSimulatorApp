from datetime import datetime
from services.logger import logger
from database import save_task, update_satellite_state, save_execution
import services.notifier as notifier

class Executor:
    def __init__(self, monitor):
        self.monitor = monitor

    # Event-Driven execution (no threads)
    def tick(self, current_time, satellites):
        for sat in satellites:
            # Process running tasks
            for task in sat.processing_tasks[:]: 
                if current_time >= task.end_time:
                    self._complete_task(task, sat)
            
            # Pick new tasks from queue if resources allow
            for task in sat.queue[:]:
                # Check if we have physical space (ignoring reservation since this task IS the reservation)
                if (sat.cpu_total - sat.cpu_used) >= task.cpu_req and \
                   (sat.mem_total - sat.mem_used) >= task.mem_req and \
                   sat.energy >= task.energy_req:
                    
                    sat.queue.remove(task)
                    self._start_task(task, sat, current_time)

    def _start_task(self, task, sat, current_time):
        sat.cpu_used += task.cpu_req
        sat.mem_used += task.mem_req
        sat.energy -= task.energy_req
        
        # Release reservation as it becomes active usage
        sat.cpu_reserved -= task.cpu_req
        sat.mem_reserved -= task.mem_req
        
        sat.processing_tasks.append(task)
        
        task.start_time = current_time
        task.end_time = current_time + task.duration
        task.status = "RUNNING"
        task.assigned_satellite = sat
        
        save_task(task)
        update_satellite_state(sat)
        logger.info(f"Started task {task.task_id} on {sat.sat_id}")
        notifier.notify(f"TASK {task.task_id} IS RUNNING ON SATELLITE {sat.sat_id}")

    def _complete_task(self, task, sat):
        sat.processing_tasks.remove(task)
        
        sat.cpu_used -= task.cpu_req
        sat.mem_used -= task.mem_req
        
        task.status = "DONE"
        save_task(task)
        update_satellite_state(sat)
        
        self.monitor.record({
            "task_id": task.task_id,
            "satellite": sat.sat_id,
            "start": datetime.fromtimestamp(task.start_time).isoformat() if task.start_time else "",
            "end": datetime.fromtimestamp(task.end_time).isoformat() if task.end_time else "",
            "status": task.status
        })
        save_execution({
            "task_id": task.task_id,
            "satellite": sat.sat_id,
            "start": datetime.fromtimestamp(task.start_time).isoformat(),
            "end": datetime.fromtimestamp(task.end_time).isoformat(),
            "status": "DONE"
        })
        logger.info(f"Completed task {task.task_id} on {sat.sat_id}")
        notifier.notify(f"TASK {task.task_id} IS DONE ON SATELLITE {sat.sat_id}")
