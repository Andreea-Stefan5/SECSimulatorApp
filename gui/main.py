import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import threading
import time
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend.core.scheduler import Scheduler
from backend.models.satellite import Satellite
from backend.models.task import Task
from backend.models.ground_station import GroundStation
from backend.services.executor import Executor
from backend.services.monitor import Monitor
from backend.core.strategies import HeuristicStrategy, GeneticStrategy, RLStrategy
from backend.database import init_db, get_all_satellites_data, save_satellite, delete_satellite
from backend.api.server import start_api
import backend.services.notifier as notifier

class SECSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SEC Simulator & Scheduler")
        self.root.geometry("1400x800")
        
        # backend Setup
        init_db()
        self.monitor = Monitor()
        self.executor = Executor(self.monitor)
        self.scheduler = Scheduler(self.executor, self.monitor)
        
        # start API Server in background
        try:
            start_api(self.scheduler)
            print("API Server started on port 5000")
        except Exception as e:
            print(f"Failed to start API: {e}")

        self.init_simulation_data()
        
        self.setup_ui()
        
        # simulation Loop
        self.running = False
        self.simulation_speed = 1000 # ms per tick

        self.sim_start_time = 0
        self.sim_end_time = 0
        self.tasks_at_start = 0

        self.tick_loop()

    def init_simulation_data(self):
        db_sats = get_all_satellites_data()
        
        if not db_sats:
            import random
            print("Database empty. Seeding satellites...")
            for i in range(1, 13): 
                cpu = random.choice([2, 4, 8, 16])
                mem = random.choice([1024, 2048, 4096, 8192])
                battery = 100 
                sat = Satellite(f"SAT-{i:02d}", cpu, mem, battery)
                save_satellite(sat)
                self.scheduler.add_satellite(sat)
        else:
            print(f"Loading {len(db_sats)} satellites from DB...")
            for s in db_sats:
                sat = Satellite(s["sat_id"], s["cpu"], s["mem"], s["battery"])
                if s["inclination"] is not None: sat.inclination = s["inclination"]
                if s["raan"] is not None: sat.raan = s["raan"]
                if s["angle"] is not None: sat.angle = s["angle"]
                
                self.scheduler.add_satellite(sat)
            
        self.scheduler.add_ground_station(GroundStation("GS-Bucharest", 44.42, 26.10))
        self.scheduler.add_ground_station(GroundStation("GS-London", 51.50, -0.12))
        self.scheduler.add_ground_station(GroundStation("GS-NewYork", 40.71, -74.00))

    def setup_ui(self):
        # left panel
        left_panel = tk.Frame(self.root, width=300, bg="#f0f0f0", padx=10, pady=10)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(left_panel, text="Controls", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
        
        # user selection
        tk.Label(left_panel, text="Active User:", bg="#f0f0f0").pack(anchor="w")
        self.user_var = tk.StringVar(value="User 1")
        user_combo = ttk.Combobox(left_panel, textvariable=self.user_var, values=["User 1", "User 2", "User 3"])
        user_combo.pack(fill=tk.X, pady=5)
        
        # strategy
        tk.Label(left_panel, text="Scheduling Strategy:", bg="#f0f0f0").pack(anchor="w")
        self.strategy_var = tk.StringVar(value="Heuristic")
        strategy_combo = ttk.Combobox(left_panel, textvariable=self.strategy_var, values=["Heuristic", "Genetic", "RL"])
        strategy_combo.pack(fill=tk.X, pady=5)
        strategy_combo.bind("<<ComboboxSelected>>", self.change_strategy)
        
        # sim Controls
        btn_frame = tk.Frame(left_panel, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, pady=10)
        self.btn_start = tk.Button(btn_frame, text="Start", command=self.start_sim, bg="#4caf50", fg="white")
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_stop = tk.Button(btn_frame, text="Stop", command=self.stop_sim, bg="#f44336", fg="white")
        self.btn_stop.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # speed control
        tk.Label(left_panel, text="Sim Speed (ms):", bg="#f0f0f0").pack(anchor="w", pady=(10,0))
        self.speed_scale = tk.Scale(left_panel, from_=100, to=2000, orient=tk.HORIZONTAL, bg="#f0f0f0")
        self.speed_scale.set(1000)
        self.speed_scale.pack(fill=tk.X)
        
        # manage satellites button
        tk.Button(left_panel, text="Manage Satellites", command=self.open_satellite_manager, bg="#9c27b0", fg="white").pack(fill=tk.X, pady=5)

        # stats button
        tk.Button(left_panel, text="Show Metrics", command=self.show_metrics, bg="#ff9800", fg="white").pack(fill=tk.X, pady=5)
        
        # add task form
        tk.Label(left_panel, text="Add New Task", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=(20, 10))
        
        tk.Label(left_panel, text="CPU Req:", bg="#f0f0f0").pack(anchor="w")
        self.entry_cpu = tk.Entry(left_panel)
        self.entry_cpu.insert(0, "2")
        self.entry_cpu.pack(fill=tk.X)
        
        tk.Label(left_panel, text="Mem Req:", bg="#f0f0f0").pack(anchor="w")
        self.entry_mem = tk.Entry(left_panel)
        self.entry_mem.insert(0, "512")
        self.entry_mem.pack(fill=tk.X)
        
        tk.Label(left_panel, text="Energy Req:", bg="#f0f0f0").pack(anchor="w")
        self.entry_energy = tk.Entry(left_panel)
        self.entry_energy.insert(0, "15.00")
        self.entry_energy.pack(fill=tk.X)

        tk.Label(left_panel, text="Duration:", bg="#f0f0f0").pack(anchor="w")
        self.entry_dur = tk.Entry(left_panel)
        self.entry_dur.insert(0, "5")
        self.entry_dur.pack(fill=tk.X)

        tk.Label(left_panel, text="Schedule Time (YYYY-MM-DD HH:MM:SS):", bg="#f0f0f0").pack(anchor="w")
        self.entry_time = tk.Entry(left_panel)
        from datetime import datetime
        self.entry_time.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.entry_time.pack(fill=tk.X)

        tk.Label(left_panel, text="Ground Station:", bg="#f0f0f0").pack(anchor="w")
        self.gs_ids = [gs.gs_id for gs in self.scheduler.ground_stations]
        self.gs_var = tk.StringVar(value=self.gs_ids[0] if self.gs_ids else "")
        self.gs_combo = ttk.Combobox(left_panel, textvariable=self.gs_var, values=self.gs_ids)
        self.gs_combo.pack(fill=tk.X, pady=5)

        tk.Button(left_panel, text="Add Task (to GS)", command=self.add_task_ui, bg="#2196f3", fg="white").pack(fill=tk.X, pady=10)
        
        # right panel: visualization
        right_panel = tk.Frame(self.root, bg="white")
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # canvas
        self.canvas = tk.Canvas(right_panel, bg="#1a1a2e", height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # GS calendar button
        cal_btn = tk.Button(right_panel, text="GS Calendar (Waiting Tasks)", command=self.open_gs_calendar, bg="#9c27b0", fg="white")
        cal_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # history Button
        hist_btn = tk.Button(right_panel, text="Execution History", command=self.open_history_window, bg="#607d8b", fg="white")
        hist_btn.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # alerts panel
        bottom_split = tk.Frame(right_panel, height=200, bg="white")
        bottom_split.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # task list container
        log_container = tk.Frame(bottom_split, bg="white", bd=1, relief=tk.SOLID)
        log_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        
        tk.Label(log_container, text="Active Tasks", bg="#eeeeee", font=("Arial", 9, "bold")).pack(fill=tk.X)
        
        self.tasks_canvas = tk.Canvas(log_container, bg="white")
        self.tasks_scrollbar = tk.Scrollbar(log_container, orient="vertical", command=self.tasks_canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.tasks_canvas, bg="white")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.tasks_canvas.configure(
                scrollregion=self.tasks_canvas.bbox("all")
            )
        )

        self.tasks_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.tasks_canvas.configure(yscrollcommand=self.tasks_scrollbar.set)

        self.tasks_canvas.pack(side="left", fill="both", expand=True)
        self.tasks_scrollbar.pack(side="right", fill="y")
        
        # alerts panel
        alert_frame = tk.Frame(bottom_split, bg="white", width=300, bd=1, relief=tk.SOLID)
        alert_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))
        
        tk.Label(alert_frame, text="System Alerts", bg="#eeeeee", font=("Arial", 9, "bold")).pack(fill=tk.X)
        
        from tkinter import scrolledtext
        self.alerts_text = scrolledtext.ScrolledText(alert_frame, height=8, font=("Consolas", 9), state='disabled', width=40)
        self.alerts_text.pack(fill=tk.BOTH, expand=True)
        
        # Override backend notifier
        # We need to patch both potential module paths due to sys.path manipulation
        import backend.services.notifier as notifier_backend
        import services.notifier as notifier_services
        
        original_notify = notifier_backend.notify
        
        def gui_notify(message):
            original_notify(message)
            try:
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                self.alerts_text.configure(state='normal')
                self.alerts_text.insert(tk.END, f"[{ts}] {message}\n")
                self.alerts_text.see(tk.END)
                self.alerts_text.configure(state='disabled')
            except:
                pass
            
        notifier_backend.notify = gui_notify
        notifier_services.notify = gui_notify
        
    def open_satellite_manager(self):
        win = tk.Toplevel(self.root)
        win.title("Satellite Management")
        win.geometry("800x500")

        # list of satellites 
        left_frame = tk.Frame(win, width=500, bg="white", padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left_frame, text="Available Satellites (DB)", font=("Arial", 11, "bold")).pack(pady=5)
        tk.Label(left_frame, text="Hold Ctrl or Shift to select multiple satellites.", font=("Arial", 9, "italic"), fg="gray").pack(pady=(0, 5))
        
        columns = ("ID", "CPU", "Mem", "Battery")
        tree = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="extended")
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=80 if col != "ID" else 150)
            
        tree.pack(fill=tk.BOTH, expand=True)

        right_frame = tk.Frame(win, width=250, bg="#f0f0f0", padx=10, pady=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(right_frame, text="Add New Satellite", font=("Arial", 11, "bold"), bg="#f0f0f0").pack(pady=5)
        
        tk.Label(right_frame, text="Sat ID:", bg="#f0f0f0").pack(anchor="w")
        e_id = tk.Entry(right_frame)
        e_id.pack(fill=tk.X)
        
        tk.Label(right_frame, text="CPU Total:", bg="#f0f0f0").pack(anchor="w")
        e_cpu = tk.Entry(right_frame)
        e_cpu.insert(0, "4")
        e_cpu.pack(fill=tk.X)
        
        tk.Label(right_frame, text="Mem Total:", bg="#f0f0f0").pack(anchor="w")
        e_mem = tk.Entry(right_frame)
        e_mem.insert(0, "2048")
        e_mem.pack(fill=tk.X)
        
        tk.Label(right_frame, text="Battery Cap:", bg="#f0f0f0").pack(anchor="w")
        e_bat = tk.Entry(right_frame)
        e_bat.insert(0, "100")
        e_bat.pack(fill=tk.X)

        active_sats = {s.sat_id for s in self.scheduler.satellites}

        def refresh_list():
            for item in tree.get_children():
                tree.delete(item)
            
            db_sats = get_all_satellites_data()
            items_to_select = []
            
            for sat in db_sats:
                tag = "active" if sat["sat_id"] in active_sats else "inactive"
                item_id = tree.insert("", "end", values=(sat["sat_id"], sat["cpu"], sat["mem"], sat["battery"]), tags=(tag,))
                
                if sat["sat_id"] in active_sats:
                    items_to_select.append(item_id)
            
            tree.tag_configure("active", foreground="green", font=("Arial", 9, "bold"))
            tree.tag_configure("inactive", foreground="gray")
            
            if items_to_select:
                tree.selection_set(items_to_select)

        refresh_list()

        def add_sat():
            try:
                sid = e_id.get()
                cpu = int(e_cpu.get())
                mem = int(e_mem.get())
                bat = float(e_bat.get())
                
                if not sid:
                    messagebox.showerror("Error", "ID is required", parent=win)
                    return

                new_sat = Satellite(sid, cpu, mem, bat)
                save_satellite(new_sat) # Saves with random orbit
                messagebox.showinfo("Success", f"Satellite {sid} added to DB", parent=win)
                refresh_list()
            except ValueError:
                messagebox.showerror("Error", "Invalid inputs", parent=win)

        tk.Button(right_frame, text="Add Satellite", command=add_sat, bg="#4caf50", fg="white").pack(fill=tk.X, pady=10)

        action_frame = tk.Frame(left_frame, bg="white")
        action_frame.pack(fill=tk.X, pady=10)

        def delete_selected():
            selected = tree.selection()
            if not selected: return
            
            if messagebox.askyesno("Confirm", "Delete selected satellites locally and from DB?"):
                for item in selected:
                    vals = tree.item(item)["values"]
                    sid = vals[0]
                    # Delete from DB
                    delete_satellite(sid)
                
                refresh_list()

        def use_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Select satellites to use in simulation.")
                return
            
            selected_ids = [tree.item(item)["values"][0] for item in selected]
            
            current_map = {s.sat_id: s for s in self.scheduler.satellites}
            new_list = []
            
            db_sats = get_all_satellites_data() # reload to get full data
            
            for s_data in db_sats:
                if s_data["sat_id"] in selected_ids:
                    if s_data["sat_id"] in current_map:
                         new_list.append(current_map[s_data["sat_id"]])
                    else:
                         sat = Satellite(s_data["sat_id"], s_data["cpu"], s_data["mem"], s_data["battery"])
                         if s_data["inclination"] is not None: sat.inclination = s_data["inclination"]
                         if s_data["raan"] is not None: sat.raan = s_data["raan"]
                         if s_data["angle"] is not None: sat.angle = s_data["angle"]
                         new_list.append(sat)
            
            self.scheduler.satellites = new_list
            
            active_sats.clear()
            active_sats.update(s.sat_id for s in new_list)
            
            refresh_list()
            messagebox.showinfo("Success", f"Active satellites updated. Count: {len(new_list)}", parent=win)

        tk.Button(action_frame, text="Update Active Satellites", command=use_selected, bg="#2196f3", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="Delete Selected", command=delete_selected, bg="#f44336", fg="white").pack(side=tk.RIGHT, padx=5)
        
        tk.Label(left_frame, text="Note: Green = Currently Active in Sim", font=("Arial", 8, "italic"), fg="gray").pack(anchor="w")


    def change_strategy(self, event=None):
        selection = self.strategy_var.get()
        if selection == "Heuristic":
            self.scheduler.set_strategy(HeuristicStrategy())
        elif selection == "Genetic":
            self.scheduler.set_strategy(GeneticStrategy())
        elif selection == "RL":
            self.scheduler.set_strategy(RLStrategy())

    def start_sim(self):
        import time
        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        self.sim_start_time = time.time()
        self.sim_end_time = None
        self.tasks_at_start = len(self.scheduler.tasks)

    def stop_sim(self):
        import time
        self.running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

        self.sim_end_time = time.time()

    def show_metrics(self):
        import time 
        if self.sim_start_time == 0:
            messagebox.showinfo("Metrics", "Simularea nu a fost pornita inca.")
            return
            
        if self.running:
            sim_duration = time.time() - self.sim_start_time
        else:
            sim_duration = self.sim_end_time - self.sim_start_time
            
        current_session_tasks = self.scheduler.tasks[self.tasks_at_start:]
        
        total = len(current_session_tasks)
        done = sum(1 for t in current_session_tasks if t.status == "DONE")
        failed = sum(1 for t in current_session_tasks if t.status == "FAILED")
        
        success_rate = (done / total * 100) if total > 0 else 0
        
        durations = [t.duration for t in current_session_tasks if t.status == "DONE"]
        avg_dur = sum(durations) / len(durations) if durations else 0
        
        msg = f"""Simulation Metrics (Current Session):
------------------
Total Tasks: {total}
Completed: {done}
Failed: {failed}
Success Rate: {success_rate:.1f}%

Sim Elapsed Time: {sim_duration:.1f} sec
Avg Task Duration: {avg_dur:.1f} sec
"""
        messagebox.showinfo("Metrics", msg)

    def add_task_ui(self):
        try:
            cpu = int(self.entry_cpu.get())
            mem = int(self.entry_mem.get())
            duration = int(self.entry_dur.get())
            
            # user formula: Energy = f(Resources, Duration)
            # new formula for 100-scale:
            # base drain: 0.1/sec, CPU: 0.1/sec, Mem: 0.0005/sec
            power_draw = 0.1 + (cpu * 0.1) + (mem * 0.0005)
            energy = power_draw * duration
            
            # update the Energy Entry to show the calculated value (for visibility)
            self.entry_energy.delete(0, tk.END)
            self.entry_energy.insert(0, f"{energy:.2f}")
            
            try:
                import time
                from datetime import datetime
                sch_str = self.entry_time.get()
                dt = datetime.strptime(sch_str, "%Y-%m-%d %H:%M:%S")
                start = dt.timestamp()
                
                # Validation: Cannot schedule in the past
                if start < time.time() - 1: # Tolerance of 1s
                    messagebox.showerror("Error", "Cannot schedule task in the past!")
                    return

            except ValueError:
                import time
                start = time.time()
                print("Invalid Date Format, defaulting to NOW")
            
            user_id = self.user_var.get()
            
            task_id = f"T{len(self.scheduler.tasks) + 1}-{user_id}"
            
            deadline = start + duration + 100
            
            task = Task(task_id, cpu, mem, energy, duration, start, deadline, user_id)
            
            selected_gs_id = self.gs_var.get()
            gs = next((g for g in self.scheduler.ground_stations if g.gs_id == selected_gs_id), None)
            
            if gs:
                gs.add_task(task)
                import time
                if start > time.time():
                     notifier.notify(f"TASK {task.task_id} IS SCHEDULED ON GS {gs.gs_id}")
                     messagebox.showinfo("Success", f"Task buffered at {gs.gs_id}, scheduled for {sch_str}")
                else:
                     notifier.notify(f"TASK {task.task_id} IS SCHEDULED ON GS {gs.gs_id}")
                     messagebox.showinfo("Success", f"Task queued at {gs.gs_id} (Immediate)")
            else:
                messagebox.showerror("Error", "Selected Ground Station not found!")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid input values")

    def tick_loop(self):
        if self.running:
            self.scheduler.tick()
            self.update_canvas()
            self.update_task_list()
        
        speed = self.speed_scale.get()
        self.root.after(speed, self.tick_loop)

    def update_canvas(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w/2, h/2
        
        earth_radius = 60 
        
        self.canvas.create_oval(cx - earth_radius, cy - earth_radius, 
                                cx + earth_radius, cy + earth_radius, 
                                fill="#4b86b4", outline="white", width=2)
        self.canvas.create_text(cx, cy, text="EARTH", fill="white", font=("Arial", 10, "bold"))
        
        scale = 0.05
        
        for gs in self.scheduler.ground_stations:
             angle_rad = math.radians(gs.lon - 90)
             
             gx = cx + earth_radius * math.cos(angle_rad)
             gy = cy + earth_radius * math.sin(angle_rad)
             
             self.canvas.create_rectangle(gx-6, gy-6, gx+6, gy+6, fill="#ffd700", outline="black")
             
             text_radius = earth_radius + 25
             tx = cx + text_radius * math.cos(angle_rad)
             ty = cy + text_radius * math.sin(angle_rad)
             
             self.canvas.create_text(tx, ty, text=gs.gs_id, fill="yellow", font=("Arial", 8, "bold"))
             
             if len(gs.buffer) > 0:
                 self.canvas.create_text(tx, ty+12, text=f"Buff: {len(gs.buffer)}", fill="cyan", font=("Arial", 7))

        sats = self.scheduler.satellites
        
        for i, sat1 in enumerate(sats):
            for sat2 in sats[i+1:]:
                if sat1.check_isl_connectivity(sat2):
                     x1, y1 = cx + sat1.x * scale, cy + sat1.y * scale
                     x2, y2 = cx + sat2.x * scale, cy + sat2.y * scale
                     self.canvas.create_line(x1, y1, x2, y2, fill="gray", dash=(2, 4))
        
        # satellites
        for sat in sats:
            rx = cx + sat.x * scale
            ry = cy + sat.y * scale
            
            # color logic based on status
            color = "green" if sat.connected else "red"
            if sat.energy < 0.1 * sat.battery_capacity:
                color = "orange" 
            
            self.canvas.create_oval(rx-10, ry-10, rx+10, ry+10, fill=color, outline="white")
            pct = (sat.energy / sat.battery_capacity) * 100 if sat.battery_capacity > 0 else 0
            self.canvas.create_text(rx, ry-20, text=f"{sat.sat_id}\n{pct:.0f}%", fill="white", font=("Arial", 8))
            
            if len(sat.queue) > 0:
                self.canvas.create_text(rx, ry+15, text=f"Q:{len(sat.queue)}", fill="white", font=("Arial", 7))
        import time
        current_sec = int(time.time()) % 60
        is_day = current_sec < 36
        
        if is_day:
            phase_time_left = 36 - current_sec
        else:
            phase_time_left = 60 - current_sec
        
        margin_x = w - 70
        margin_y = 50
        
        if is_day:
            self.canvas.create_oval(margin_x - 18, margin_y - 18, margin_x + 18, margin_y + 18, fill="#ffeb3b", outline="#fbc02d", width=2)
            self.canvas.create_line(margin_x, margin_y - 25, margin_x, margin_y + 25, fill="#ffeb3b", width=2)
            self.canvas.create_line(margin_x - 25, margin_y, margin_x + 25, margin_y, fill="#ffeb3b", width=2)
            phase_text = "DAY"
            text_color = "#ffeb3b"
        else:
            self.canvas.create_oval(margin_x - 18, margin_y - 18, margin_x + 18, margin_y + 18, fill="#e0e0e0", outline="#bdbdbd")
            self.canvas.create_oval(margin_x - 8, margin_y - 18, margin_x + 24, margin_y + 12, fill="#1a1a2e", outline="#1a1a2e")
            phase_text = "NIGHT"
            text_color = "#e0e0e0"
            
        self.canvas.create_text(margin_x, margin_y + 35, text=f"{phase_text}: {phase_time_left}s", fill=text_color, font=("Arial", 11, "bold"))

    def update_task_list(self):
        for widget in self.scrollable_frame.winfo_children():
            if widget.winfo_y() > 30: 
                widget.destroy()

        for widget in self.scrollable_frame.winfo_children():
             widget.destroy()
             
        header_frame = tk.Frame(self.scrollable_frame, bg="#e0e0e0")
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="ID", width=10, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header_frame, text="User", width=8, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header_frame, text="Status", width=12, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header_frame, text="Sat", width=10, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header_frame, text="Info", width=15, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(header_frame, text="Actions", width=20, bg="#e0e0e0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)

        recent_tasks = self.scheduler.tasks[-50:]
        
        from functools import partial
        
        for task in reversed(recent_tasks):
            row_frame = tk.Frame(self.scrollable_frame, bg="white", pady=2)
            row_frame.pack(fill=tk.X)
            
            sat_id = task.assigned_satellite.sat_id if task.assigned_satellite else "-"
            uid = getattr(task, 'user_id', 'Unknown')
            info = f"CPU:{task.cpu_req} T:{task.duration}"
            
            tk.Label(row_frame, text=task.task_id, width=10, bg="white").pack(side=tk.LEFT)
            tk.Label(row_frame, text=uid, width=8, bg="white").pack(side=tk.LEFT)
            
            status_color = "black"
            if task.status == "DONE": status_color = "green"
            elif task.status == "FAILED": status_color = "red"
            elif task.status == "RUNNING": status_color = "blue"
            
            tk.Label(row_frame, text=task.status, width=12, bg="white", fg=status_color).pack(side=tk.LEFT)
            tk.Label(row_frame, text=sat_id, width=10, bg="white").pack(side=tk.LEFT)
            tk.Label(row_frame, text=info, width=15, bg="white", font=("Arial", 8)).pack(side=tk.LEFT)
            
            # Actions
            action_frame = tk.Frame(row_frame, bg="white", width=20)
            action_frame.pack(side=tk.LEFT)
            
            if task.status != "DONE":
                tk.Button(action_frame, text="Edit", command=partial(self.edit_task_prompt, task), 
                         bg="#ff9800", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)
                tk.Button(action_frame, text="Del", command=partial(self.handle_delete_task, task.task_id), 
                         bg="#f44336", fg="white", font=("Arial", 8), width=5).pack(side=tk.LEFT, padx=2)

    def handle_delete_task(self, task_id):
        if self.scheduler.remove_task(task_id):
            messagebox.showinfo("Success", f"Task {task_id} deleted")
            self.update_task_list()
        else:
             messagebox.showerror("Error", "Failed to delete task or task is DONE")

    def delete_task_ui(self):
        pass 
    
    def edit_task_prompt(self, task):
        win = tk.Toplevel(self.root)
        win.title(f"Edit Task {task.task_id}")
        win.geometry("300x300")
        
        tk.Label(win, text="CPU Req:").pack(pady=5)
        e_cpu = tk.Entry(win)
        e_cpu.insert(0, str(task.cpu_req))
        e_cpu.pack()
        
        tk.Label(win, text="Mem Req:").pack(pady=5)
        e_mem = tk.Entry(win)
        e_mem.insert(0, str(task.mem_req))
        e_mem.pack()
        
        tk.Label(win, text="Energy Req:").pack(pady=5)
        e_en = tk.Entry(win)
        e_en.insert(0, str(task.energy_req))
        e_en.pack()
        
        tk.Label(win, text="Duration:").pack(pady=5)
        e_dur = tk.Entry(win)
        e_dur.insert(0, str(task.duration))
        e_dur.pack()
        
        def save():
            try:
                cpu = int(e_cpu.get())
                mem = int(e_mem.get())
                en = int(e_en.get())
                dur = int(e_dur.get())
                
                if self.scheduler.update_task(task.task_id, cpu, mem, en, dur):
                     messagebox.showinfo("Success", "Task updated")
                     win.destroy()
                     self.update_task_list()
                else:
                     messagebox.showerror("Error", "Could not update task (maybe DONE?)")
            except ValueError:
                messagebox.showerror("Error", "Invalid values")
                
        tk.Button(win, text="Save Changes", command=save, bg="#4caf50", fg="white").pack(pady=20)

    def open_gs_calendar(self):
        win = tk.Toplevel(self.root)
        win.title("Ground Station / Calendar View")
        win.geometry("600x400")
        
        tree = ttk.Treeview(win, columns=("GS", "ID", "Start Time", "Duration"), show="headings")
        tree.heading("GS", text="Ground Station")
        tree.heading("ID", text="Task ID")
        tree.heading("Start Time", text="Scheduled Start")
        tree.heading("Duration", text="Duration")
        tree.column("GS", width=100)
        tree.column("ID", width=100)
        tree.column("Start Time", width=150)
        tree.column("Duration", width=80)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # populate
        import time
        from datetime import datetime
        cur_time = time.time()
        count = 0
        for gs in self.scheduler.ground_stations:
            for task in gs.buffer:
                 wait = task.earliest_start - cur_time
                 dt_str = datetime.fromtimestamp(task.earliest_start).strftime("%H:%M:%S")
                 wait_str = f"{dt_str} (in {wait:.1f}s)" if wait > 0 else "Ready"
                 tree.insert("", "end", values=(gs.gs_id, task.task_id, wait_str, task.duration))
                 count += 1
                 
        if count == 0:
            tk.Label(win, text="No waiting tasks in GS buffers.", bg="white").pack(fill=tk.X)
            
        cur_dt = datetime.fromtimestamp(cur_time).strftime("%Y-%m-%d %H:%M:%S")
        tk.Label(win, text=f"Current Time: {cur_dt}", font=("Arial", 10, "bold")).pack(pady=5)

    def open_history_window(self):
        win = tk.Toplevel(self.root)
        win.title("Execution History")
        win.geometry("700x400")
        
        tree = ttk.Treeview(win, columns=("TaskID", "Sat", "Start", "End", "Status"), show="headings")
        tree.heading("TaskID", text="Task ID")
        tree.heading("Sat", text="Satellite")
        tree.heading("Start", text="Start Time")
        tree.heading("End", text="End Time")
        tree.heading("Status", text="Status")
        
        tree.column("TaskID", width=100)
        tree.column("Sat", width=80)
        tree.column("Start", width=150)
        tree.column("End", width=150)
        tree.column("Status", width=80)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # fetch data
        from backend.database import get_execution_history
        history = get_execution_history(limit=100)
        
        for h in history:
            tag = "ok" if h["status"] == "DONE" else "fail"
            tree.insert("", "end", values=(h["task_id"], h["satellite"], h["start"], h["end"], h["status"]), tags=(tag,))
            
        tree.tag_configure("ok", foreground="green")
        tree.tag_configure("fail", foreground="red")

if __name__ == "__main__":
    root = tk.Tk()
    app = SECSimulatorApp(root)
    root.mainloop()
