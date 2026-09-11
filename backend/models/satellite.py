import threading

class Satellite:
    def __init__(self, sat_id, cpu, mem, battery):
        self.sat_id = sat_id
        self.cpu_total = cpu
        self.mem_total = mem
        self.battery_capacity = battery

        self.cpu_used = 0
        self.mem_used = 0
        
        self.cpu_reserved = 0
        self.mem_reserved = 0
        
        self.energy = battery

        self.lock = threading.Lock()
        self.connected = True
        self.in_sunlight = True
        
        # Local Queue for Edge Computing
        self.queue = [] 
        self.processing_tasks = []
        
        # Position
        self.x = 0
        self.y = 0
        self.z = 0
        # Orbital Parameters
        import random
        import math
        self.angle = random.uniform(0, 2 * math.pi) # Mean Anomaly / current position
        self.orbit_radius = 7000 
        self.inclination = random.uniform(math.radians(30), math.radians(98)) # 30 to 98 degrees (Polar)
        self.raan = random.uniform(0, 2 * math.pi) # Longitude of Ascending Node
        
        # Initial position calculation
        self.update_orbit(0)

    def can_run(self, task):
        # Emergency Low Power Mode
        if self.energy < 0.1 * self.battery_capacity:
            return False
            
        return (self.cpu_total - self.cpu_used - self.cpu_reserved) >= task.cpu_req and \
               (self.mem_total - self.mem_used - self.mem_reserved) >= task.mem_req and \
               self.energy >= task.energy_req

    def reserve_resources(self, task):
        self.cpu_reserved += task.cpu_req
        self.mem_reserved += task.mem_req

    def release_resources(self, task):
        pass

    def cancel_task(self, task):
        # Check queue
        if task in self.queue:
            self.queue.remove(task)
            self.cpu_reserved -= task.cpu_req
            self.mem_reserved -= task.mem_req
        
        if task in self.processing_tasks:
            self.processing_tasks.remove(task)
            self.cpu_used -= task.cpu_req
            self.mem_used -= task.mem_req

    def update_orbit(self, current_time):
        # day/night cycle (60s cycle: 36s sun, 24s eclipse)
        self.in_sunlight = (current_time % 60) < 36
        self.connected = (current_time % 15) != 0

        import math
        # Simulate motion
        speed = 0.05 # rad per tick
        self.angle += speed
        
        # 3D Orbital Position (Simplified Keplerian)
        # x = r * (cos(Ω)cos(θ) - sin(Ω)sin(θ)cos(i))
        # y = r * (sin(Ω)cos(θ) + cos(Ω)sin(θ)cos(i))
        # z = r * (sin(θ)sin(i))
        
        cos_node = math.cos(self.raan)
        sin_node = math.sin(self.raan)
        cos_ang = math.cos(self.angle)
        sin_ang = math.sin(self.angle)
        cos_inc = math.cos(self.inclination)
        sin_inc = math.sin(self.inclination)
        
        self.x = self.orbit_radius * (cos_node * cos_ang - sin_node * sin_ang * cos_inc)
        self.y = self.orbit_radius * (sin_node * cos_ang + cos_node * sin_ang * cos_inc)
        self.z = self.orbit_radius * (sin_ang * sin_inc)

        if self.in_sunlight:
            charge_rate = 0.5 # 0.5% per tick
            self.energy = min(self.battery_capacity, self.energy + charge_rate)
        else:
            # Eclipse: No charge
            pass
            
        self.energy = max(0, self.energy - 0.01)

    def distance_to(self, other):
        import math
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)

    def check_isl_connectivity(self, other):
        return self.distance_to(other) < 3000
