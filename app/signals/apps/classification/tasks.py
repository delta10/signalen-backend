from signals.celery import app


@app.task
def train_classifier(training_set_ids):
    print("will train a classifier using training sets:", training_set_ids)