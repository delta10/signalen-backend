from signals.apps.classification.train import TrainClassifier
from signals.celery import app


@app.task
def train_classifier(training_set_id):
    # Train model for main category
    main_category_train_model = TrainClassifier(training_set_id, ["Main"], "_main_model")
    classifier = main_category_train_model.run()

    # Train model for sub category
    sub_category_train_model = TrainClassifier(training_set_id, ["Main", "Sub"], "_sub_model", classifier.id)
    sub_category_train_model.run()



