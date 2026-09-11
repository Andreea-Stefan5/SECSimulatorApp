import math

class GroundStation:
    def __init__(self, gs_id, lat, lon):
        self.gs_id = gs_id
        self.lat = lat
        self.lon = lon
        self.buffer = [] # Tasks waiting to be uploaded
        
        # Convert Lat/Lon to 3D coords (Earth Radius ~6371 km)
        r = 6371
        rad_lat = math.radians(lat)
        rad_lon = math.radians(lon)
        
        self.x = r * math.cos(rad_lat) * math.cos(rad_lon)
        self.y = r * math.cos(rad_lat) * math.sin(rad_lon)
        self.z = r * math.sin(rad_lat)
        
    def add_task(self, task):
        self.buffer.append(task)
        
    def update(self, satellites, scheduler):
        """
        Check if any satellite is visible and upload tasks.
        """
        if not self.buffer:
            return

        # Simple visibility check: Distance < 5000km
        upload_range = 5000 # km
        
        
        can_upload = False
        for sat in satellites:
             dist = math.sqrt((self.x - sat.x)**2 + (self.y - sat.y)**2 + (self.z - sat.z)**2)
             if dist < upload_range:
                 can_upload = True
                 print(f"[{self.gs_id}] Link established with {sat.sat_id}, checking assignments...")
                 break
        
        if can_upload:
            import time
            current_real_time = time.time()
            
            # Filter tasks that are ready to go
            to_upload = []
            for task in self.buffer[:]: 
                if task.earliest_start <= current_real_time:
                    to_upload.append(task)
            
            if to_upload:
                print(f"[{self.gs_id}] Uploading {len(to_upload)} valid tasks to scheduler.")
                for task in to_upload:
                    scheduler.add_task(task)
                    self.buffer.remove(task)
