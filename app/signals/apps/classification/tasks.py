import logging
import os
import pickle
import re
from datetime import datetime

import pandas as pd
from nltk.stem.snowball import DutchStemmer
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.linear_model._logistic import LogisticRegression
from sklearn.metrics._classification import precision_score, recall_score, accuracy_score
from sklearn.model_selection._search import GridSearchCV
from sklearn.model_selection._split import train_test_split
from sklearn.pipeline import Pipeline
import nltk

from signals.apps.classification.models import TrainingSet, Classifier
from signals.celery import app

logger = logging.getLogger(__name__)

# TODO: train sub model
# TODO: create functions


def preprocessor(text):
    nltk.download('stopwords')
    stemmer = DutchStemmer(ignore_stopwords=True)

    text = str(text)
    text = text.lower()

    words = re.split("\\s+", text)
    stemmed_words = [stemmer.stem(word=word) for word in words]
    return ' '.join(stemmed_words)


@app.task
def train_classifier(training_set_id):
    training_set = TrainingSet.objects.get(pk=training_set_id)

    # step 1: read file
    _, extension = os.path.splitext(training_set.file.name)

    if extension == '.csv':
        df = pd.read_csv(training_set.file, sep=None, engine='python')
    elif extension == '.xlsx':
        df = pd.read_excel(training_set.file)
    else:
        raise Exception('Could not read input file. Extension should be .csv or .xlsx')

    # step 2: preprocess file
    df = df.dropna(
        axis=0,
    )

    df["_main_label"] = df["Main"]
    df["_sub_label"] = df["Main"] + "|" + df["Sub"]

    # step 3: stemmer and stopper
    stop_words = list(set(nltk.corpus.stopwords.words('dutch')))

    # step 4: train model
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        df["Text"], df["_main_label"], test_size=0.2, stratify=df["_main_label"])

    pipeline = Pipeline([
        ('vect', CountVectorizer(preprocessor=preprocessor, stop_words=stop_words)),
        ('tfidf', TfidfTransformer()),
        ('clf', LogisticRegression()),
    ])

    # multiple hyperparameters, slow training, better optimization
    parameters_slow = {
        'clf__class_weight': (None, 'balanced'),  # "balanced",
        'clf__max_iter': (300, 500),  # 500,1000
        'clf__penalty': ('l1',),  # 'l2',
        'clf__multi_class': ('auto',),
        'clf__solver': ('liblinear',),  # lbfgs
        'tfidf__norm': ('l2',),  # 'l1'
        'tfidf__use_idf': (False,),
        'vect__max_df': (1.0,),
        'vect__max_features': (None,),
        'vect__ngram_range': ((1, 1), (1, 2))  # (1,2)
    }

    grid_search = GridSearchCV(pipeline, parameters_slow, verbose=True, n_jobs=1, cv=5)
    grid_search.fit(train_texts, train_labels)

    model = grid_search

    # step 5: evaluation
    test_predict = model.predict(test_texts)
    precision = str(round(precision_score(test_labels, test_predict, average='macro', zero_division=0), 2))
    recall = str(round(recall_score(test_labels, test_predict, average='macro'), 2))
    accuracy = str(round(accuracy_score(test_labels, test_predict), 2))

    # step 6: save model
    save_dir = datetime.now().strftime('classification_models/main/%Y/%m/%d/')
    os.makedirs(save_dir, exist_ok=True)

    model_file_path = os.path.join(save_dir, 'main_model.pkl')
    with open(model_file_path, 'wb') as f:
        pickle.dump(model, f, pickle.HIGHEST_PROTOCOL)

    classifier = Classifier.objects.create(
        main_model=model_file_path,
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        name=training_set.name,
        is_active=False
    )

    classifier.save()

