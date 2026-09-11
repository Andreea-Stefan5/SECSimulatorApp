class Task:
    def __init__(self, task_id, cpu, mem, energy, duration, earliest_start, deadline, user_id="User1"):
        self.task_id = task_id
        self.user_id = user_id
        self.cpu_req = cpu
        self.mem_req = mem
        self.energy_req = energy
        self.duration = duration
        self.earliest_start = earliest_start
        self.deadline = deadline

        self.status = "PENDING"
        self.assigned_satellite = None
        self.start_time = None
        self.end_time = None
        self.retries = 3

    def __repr__(self):
        return f"Task(id={self.task_id}, status={self.status})"
