import os
import re

import pandas as pd
import nltk
from django.core.files.base import ContentFile
from nltk.stem.snowball import DutchStemmer
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, accuracy_score
import pickle

from signals.apps.classification.models import TrainingSet, Classifier


class TrainClassifier:
    def __init__(self, training_set_id):
        self.training_set_id = training_set_id
        self.training_set = self.get_training_set()
        self.df = None
        self.model = None
        self.train_texts = None
        self.test_texts = None
        self.train_labels = None
        self.test_labels = None
        self.classifier_id = None
        self.train_sub_model = False
        self.columns = ["Main"]
        self.model_name = "_main_model"

        nltk.download('stopwords')

    def get_training_set(self):
        return TrainingSet.objects.get(pk=self.training_set_id)

    def read_file(self):
        _, extension = os.path.splitext(self.training_set.file.name)

        if extension == '.csv':
            self.df = pd.read_csv(self.training_set.file, sep=None, engine='python')
        elif extension == '.xlsx':
            self.df = pd.read_excel(self.training_set.file)
        else:
            raise Exception('Could not read input file. Extension should be .csv or .xlsx')

    def preprocess_file(self):
        self.df = self.df.dropna(axis=0)
        self.df["_main_label"] = self.df["Main"]
        self.df["_sub_label"] = f'{self.df["Main"]}|{self.df["Sub"]}'

    def stopper(self):
        stop_words = list(set(nltk.corpus.stopwords.words('dutch')))
        return stop_words

    def preprocessor(self, text):
        stemmer = DutchStemmer(ignore_stopwords=True)

        text = str(text)
        text = text.lower()

        words = re.split("\\s+", text)
        stemmed_words = [stemmer.stem(word=word) for word in words]
        return ' '.join(stemmed_words)

    def train_test_split(self):
        if self.train_sub_model:
            self.columns = ["Main", "Sub"]

        labels = self.df[self.columns].map(lambda x: x.lower().capitalize()).apply('|'.join, axis=1)

        self.train_texts, self.test_texts, self.train_labels, self.test_labels = train_test_split(
            self.df["Text"], labels, test_size=0.2, stratify=labels
        )

    def train_model(self):
        stop_words = self.stopper()

        pipeline = Pipeline([
            ('vect', CountVectorizer(preprocessor=self.preprocessor, stop_words=stop_words)),
            ('tfidf', TfidfTransformer()),
            ('clf', LogisticRegression()),
        ])

        parameters_slow = {
            'clf__class_weight': (None, 'balanced'),
            'clf__max_iter': (300, 500),
            'clf__penalty': ('l1',),
            'clf__multi_class': ('auto',),
            'clf__solver': ('liblinear',),
            'tfidf__norm': ('l2',),
            'tfidf__use_idf': (False,),
            'vect__max_df': (1.0,),
            'vect__max_features': (None,),
            'vect__ngram_range': ((1, 1), (1, 2))
        }

        grid_search = GridSearchCV(pipeline, parameters_slow, verbose=True, n_jobs=1, cv=5)
        grid_search.fit(self.train_texts, self.train_labels)

        self.model = grid_search

    def evaluate_model(self):
        test_predict = self.model.predict(self.test_texts)
        precision = str(round(precision_score(self.test_labels, test_predict, average='macro', zero_division=0), 2))
        recall = str(round(recall_score(self.test_labels, test_predict, average='macro'), 2))
        accuracy = str(round(accuracy_score(self.test_labels, test_predict), 2))

        return precision, recall, accuracy

    def save_model(self):
        pickled_model = pickle.dumps(self.model, pickle.HIGHEST_PROTOCOL)

        precision, recall, accuracy = self.evaluate_model()

        classifier = Classifier.objects.create(
            main_model=ContentFile(pickled_model, f'{self.model_name}.pkl'),
            precision=precision,
            recall=recall,
            accuracy=accuracy,
            name=self.training_set.name,
            is_active=False
        )

        classifier.save()

        self.classifier_id = classifier.id

    def update_model(self):
        self.model_name = "_sub_model"

        pickled_model = pickle.dumps(self.model, pickle.HIGHEST_PROTOCOL)

        precision, recall, accuracy = self.evaluate_model()

        classifier = Classifier.objects.get(pk=self.classifier_id)
        classifier.sub_model = ContentFile(pickled_model, f'{self.model_name}.pkl')
        classifier.precision = str(round((float(classifier.precision) + float(precision)) / 2, 2))
        classifier.recall = str(round((float(classifier.recall) + float(recall)) / 2, 2))
        classifier.accuracy = str(round((float(classifier.accuracy) + float(accuracy)) / 2, 2))

        classifier.save()

    def run(self):
        self.read_file()
        self.preprocess_file()

        # Train main model
        self.train_test_split()
        self.train_model()
        self.save_model()

        # Train sub model
        self.train_sub_model = True
        self.train_test_split()
        self.train_model()
        self.update_model()
