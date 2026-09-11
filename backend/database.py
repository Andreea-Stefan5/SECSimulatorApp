import pyodbc

SERVER = "ANDREEA\\SQLEXPRESS"
DATABASE = "sec_scheduler"

DRIVER = "ODBC Driver 17 for SQL Server"

def get_connection():
    conn_str = f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;"
    return pyodbc.connect(conn_str)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='satellites' AND xtype='U')
    CREATE TABLE satellites (
        sat_id NVARCHAR(50) PRIMARY KEY,
        cpu_total INT,
        mem_total INT,
        battery_capacity FLOAT
    )
    """)

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='tasks' AND xtype='U')
    CREATE TABLE tasks (
        task_id NVARCHAR(50) PRIMARY KEY,
        user_id NVARCHAR(50),
        cpu_req INT,
        mem_req INT,
        energy_req FLOAT,
        duration INT,
        earliest_start BIGINT,
        deadline BIGINT,
        status NVARCHAR(20),
        assigned_satellite NVARCHAR(50),
        start_time BIGINT,
        end_time BIGINT
    )
    """)

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('tasks') AND name = 'user_id')
    ALTER TABLE tasks ADD user_id NVARCHAR(50) DEFAULT 'User1';
    """)

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='executions' AND xtype='U')
    CREATE TABLE executions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        task_id NVARCHAR(50),
        satellite_id NVARCHAR(50),
        start_time NVARCHAR(50),
        end_time NVARCHAR(50),
        status NVARCHAR(20),
        exit_code INT
    )
    """)

    # Schema updates for spatial coordinates
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'x')
    ALTER TABLE satellites ADD x FLOAT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'y')
    ALTER TABLE satellites ADD y FLOAT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'z')
    ALTER TABLE satellites ADD z FLOAT DEFAULT 0;
    """)

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'cpu_used')
    ALTER TABLE satellites ADD cpu_used INT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'mem_used')
    ALTER TABLE satellites ADD mem_used INT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'energy')
    ALTER TABLE satellites ADD energy FLOAT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'inclination')
    ALTER TABLE satellites ADD inclination FLOAT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'raan')
    ALTER TABLE satellites ADD raan FLOAT DEFAULT 0;
    """)
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('satellites') AND name = 'angle')
    ALTER TABLE satellites ADD angle FLOAT DEFAULT 0;
    """)

    conn.commit()
    conn.close()

def save_task(task):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE tasks SET 
        user_id=?, cpu_req=?, mem_req=?, energy_req=?, duration=?, earliest_start=?, deadline=?, 
        status=?, assigned_satellite=?, start_time=?, end_time=?
        WHERE task_id=?
    """, (
        task.user_id, task.cpu_req, task.mem_req, task.energy_req, task.duration, task.earliest_start, task.deadline, 
        task.status, task.assigned_satellite.sat_id if task.assigned_satellite else None, 
        task.start_time, task.end_time,
        task.task_id
    ))
    
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO tasks (
                task_id, user_id, cpu_req, mem_req, energy_req, duration, earliest_start, 
                deadline, status, assigned_satellite, start_time, end_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id, task.user_id, task.cpu_req, task.mem_req, task.energy_req, task.duration, task.earliest_start, 
            task.deadline, task.status, task.assigned_satellite.sat_id if task.assigned_satellite else None, 
            task.start_time, task.end_time
        ))

    conn.commit()
    conn.close()

def save_execution(result):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO executions (task_id, satellite_id, start_time, end_time, status, exit_code)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        result["task_id"],
        result["satellite"],
        result["start"],
        result["end"],
        result["status"],
        0 if result["status"] == "DONE" else 1
    ))
    conn.commit()
    conn.close()

def delete_task(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()

def get_execution_history(limit=50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, satellite_id, start_time, end_time, status FROM executions ORDER BY id DESC")
    rows = cursor.fetchmany(limit)
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "task_id": r.task_id,
            "satellite": r.satellite_id,
            "start": r.start_time,
            "end": r.end_time,
            "status": r.status
        })
    return history

def save_satellite(sat):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT count(*) FROM satellites WHERE sat_id = ?", (sat.sat_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
        INSERT INTO satellites (sat_id, cpu_total, mem_total, battery_capacity, x, y, z, cpu_used, mem_used, energy, inclination, raan, angle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sat.sat_id,
            sat.cpu_total,
            sat.mem_total,
            sat.battery_capacity,
            sat.x, sat.y, sat.z,
            sat.cpu_used, sat.mem_used, sat.energy,
            sat.inclination, sat.raan, sat.angle
        ))
    else:
        cursor.execute("""
        UPDATE satellites SET
            cpu_total=?, mem_total=?, battery_capacity=?, x=?, y=?, z=?, cpu_used=?, mem_used=?, energy=?,
            inclination=?, raan=?, angle=?
        WHERE sat_id=?
        """, (
            sat.cpu_total, sat.mem_total, sat.battery_capacity,
            sat.x, sat.y, sat.z,
            sat.cpu_used, sat.mem_used, sat.energy,
            sat.inclination, sat.raan, sat.angle,
            sat.sat_id
        ))

    conn.commit()
    conn.close()

def update_satellite_state(sat):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE satellites 
        SET x=?, y=?, z=?, cpu_used=?, mem_used=?, energy=?, angle=?
        WHERE sat_id=?
    """, (sat.x, sat.y, sat.z, sat.cpu_used, sat.mem_used, sat.energy, sat.angle, sat.sat_id))

    conn.commit()
    conn.close()

def get_all_satellites_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sat_id, cpu_total, mem_total, battery_capacity, inclination, raan, angle FROM satellites")
    rows = cursor.fetchall()
    conn.close()
    
    sats = []
    for r in rows:
        sats.append({
            "sat_id": r.sat_id,
            "cpu": r.cpu_total,
            "mem": r.mem_total,
            "battery": r.battery_capacity,
            "inclination": r.inclination,
            "raan": r.raan,
            "angle": r.angle
        })
    return sats

def delete_satellite(sat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM satellites WHERE sat_id = ?", (sat_id,))
    conn.commit()
    conn.close()
