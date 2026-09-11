def notify(message):
    print(f"[ALERT] {message}")
    try:
        from datetime import datetime
        with open("alerts.log", "a") as f:
            f.write(f"[{datetime.now()}] {message}\n")
    except Exception as e:
        print(f"Failed to log alert: {e}")