from signals.apps.classification.train import TrainClassifier
from signals.celery import app


@app.task
def train_classifier(training_set_id):
    train_model = TrainClassifier(training_set_id)
    train_model.run()

