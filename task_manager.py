# Fichier task_manager.py

class TaskManager:
    def __init__(self):
        self.tasks = {}

    def set_task(self, task_id, value):
        self.tasks[task_id] = value

    def get_task(self, task_id):
        return self.tasks.get(task_id)

task_manager = TaskManager()


