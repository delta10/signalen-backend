from signals.celery import app


@app.task
def run_training_task():
    print("running a training task")