from database import save_execution
from services.notifier import notify

class Monitor:
    def __init__(self):
        self.history = []

    def record(self, result):
        self.history.append(result)
        save_execution(result)

        if result["status"] == "FAILED":
            notify(f"Task {result['task_id']} failed")
