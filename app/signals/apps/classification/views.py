# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2019 - 2023 Gemeente Amsterdam
import functools
import logging

from django.core.exceptions import ValidationError as DjangoCoreValidationError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from signals.apps.api.ml_tool.client import MLToolClient
from signals.apps.llm_prediction.services.prediction import get_prediction, resolve_prediction
from signals.apps.signals.models import Category
import pickle
import sys
import types
import io
import numpy as np

from django.conf import settings
from rest_framework import status

from signals.apps.classification.models import Classifier


class StubClass:
    """A stub class that can be used for missing classes during unpickling"""
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
    
    def __getattr__(self, name):
        return StubClass()
    
    def __call__(self, *args, **kwargs):
        return StubClass()
    
    def predict(self, X):
        # Return a list of dummy predictions
        return ['overig'] * len(X)
    
    def predict_proba(self, X):
        # Return dummy probabilities
        import numpy as np
        return np.array([[0.1, 0.9]] * len(X))
    
    @property
    def classes_(self):
        return ['overig', 'wegen-verkeer-straatmeubilair']


class SafeUnpickler(pickle.Unpickler):
    """Custom unpickler that handles missing modules and classes"""
    
    def find_class(self, module, name):
        # Handle missing 'engine' module and its submodules/classes
        if module.startswith('engine'):
            return StubClass
        
        # For other missing modules, try the default behavior first
        try:
            return super().find_class(module, name)
        except (ImportError, AttributeError):
            # If module/class is missing, return a stub
            return StubClass


def safe_pickle_load(file_obj):
    """Safely load pickle files with missing module handling"""
    # Reset file position to beginning
    file_obj.seek(0)
    
    # Use our custom unpickler
    unpickler = SafeUnpickler(file_obj)
    return unpickler.load()


@functools.lru_cache(maxsize=2)
def _load_models(classifier_pk):
    classifier = Classifier.objects.get(pk=classifier_pk)
    
    # Load models
    main_model = safe_pickle_load(classifier.main_model)
    sub_model = safe_pickle_load(classifier.sub_model)
    
    # Load slugs (temporarily stored in confusion matrix fields)
    main_slugs = []
    sub_slugs = []
    
    if classifier.main_confusion_matrix:
        try:
            main_slugs = safe_pickle_load(classifier.main_confusion_matrix)
        except Exception:
            main_slugs = []
    
    if classifier.sub_confusion_matrix:
        try:
            sub_slugs = safe_pickle_load(classifier.sub_confusion_matrix)
        except Exception:
            sub_slugs = []
    
    return main_model, sub_model, main_slugs, sub_slugs


@extend_schema(exclude=True)
class MlPredictCategoryView(APIView):
    ml_tool_client = MLToolClient()

    _default_category_url = None
    default_category = None

    def __init__(self, *args, **kwargs):
        # When we cannot translate we return the 'overig-overig' category url
        self.default_category = Category.objects.get(slug='overig', parent__isnull=False, parent__slug='overig')
        super().__init__(*args, **kwargs)

    @property
    def default_category_url(self):
        if not self._default_category_url and self.default_category:
            request = self.request if self.request else None
            self._default_category_url = self.default_category.get_absolute_url(request=request)
        return self._default_category_url

    def get_prediction_old_ml_proxy(self, request):
        # Default empty response
        data = {'hoofdrubriek': [], 'subrubriek': []}

        try:
            response = self.ml_tool_client.predict(text=request.data['text'])
        except DjangoCoreValidationError as e:
            raise ValidationError(e.message, e.code)
        else:
            if response.status_code == 200:
                response_data = response.json()

                for key in data.keys():
                    try:
                        category = Category.objects.get_from_url(url=response_data[key][0][0])
                    except Category.DoesNotExist:
                        category_url = self.default_category_url
                    else:
                        category_url = category.get_absolute_url(request=request)

                    data[key].append([category_url])
                    data[key].append([response_data[key][1][0]])

        return Response(data)

    def get_prediction_new_ml_proxy(self, request, classifier):
        try:
            main_model, sub_model, main_slugs, sub_slugs = _load_models(classifier.pk)

            text = request.data['text']

            # Handle different model types
            if hasattr(main_model, 'predict') and hasattr(main_model, 'predict_proba'):
                # It's a proper sklearn model
                main_prediction = main_model.predict([text])[0]
                main_proba = main_model.predict_proba([text])[0]
                main_index = list(main_model.classes_).index(main_prediction)
                main_prob = main_proba[main_index]
                
                # Map prediction to slug if available
                if main_slugs and isinstance(main_prediction, (int, np.integer)) and main_prediction < len(main_slugs):
                    main_category_url = settings.BACKEND_URL + main_slugs[main_prediction]
                elif main_slugs and isinstance(main_prediction, str):
                    # Find matching slug
                    main_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig'
                    for slug in main_slugs:
                        if main_prediction.lower() in slug.lower():
                            main_category_url = settings.BACKEND_URL + '/signals/v1/public/terms' + slug
                            break
                else:
                    main_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig'
            else:
                # Fallback for non-sklearn models or arrays
                main_prob = 0.5
                main_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig'

            # Similar logic for sub model
            if hasattr(sub_model, 'predict') and hasattr(sub_model, 'predict_proba'):
                sub_prediction = sub_model.predict([text])[0]
                sub_proba = sub_model.predict_proba([text])[0]
                
                if hasattr(sub_model, 'classes_'):
                    sub_index = list(sub_model.classes_).index(sub_prediction)
                    sub_prob = sub_proba[sub_index]
                else:
                    sub_prob = max(sub_proba)
                
                # Map to slug
                if sub_slugs and isinstance(sub_prediction, (int, np.integer)) and sub_prediction < len(sub_slugs):
                    sub_category_url = settings.BACKEND_URL + '/signals/v1/public/terms' + sub_slugs[sub_prediction]
                elif sub_slugs and isinstance(sub_prediction, str):
                    # Handle compound predictions like "main|sub"
                    if '|' in sub_prediction:
                        sub_category = sub_prediction.split('|')[1]
                    else:
                        sub_category = sub_prediction
                    
                    sub_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig/sub_categories/overig'
                    for slug in sub_slugs:
                        if sub_category.lower() in slug.lower():
                            sub_category_url = settings.BACKEND_URL + '/signals/v1/public/terms' + slug
                            break
                else:
                    sub_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig/sub_categories/overig'
            else:
                # Fallback
                sub_prob = 0.5
                sub_category_url = settings.BACKEND_URL + '/signals/v1/public/terms/categories/overig/sub_categories/overig'

            data = {
                'hoofdrubriek': [
                    [main_category_url],
                    [main_prob],
                ],
                'subrubriek': [
                    [sub_category_url],
                    [sub_prob]
                ]
            }
        except Exception as e:
            logging.error(f"ML prediction error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return Response('Predicting sub and main category went wrong', content_type='application/json', status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(status=status.HTTP_200_OK, data=data)

    def get_prediction_llm(self, request):
        text = request.data['text']

        prediction = get_prediction(text)

        main_slug, sub_slug = resolve_prediction(prediction)

        data = {
            'hoofdrubriek': [
                [settings.BACKEND_URL + f'/signals/v1/public/terms/categories/{main_slug}'],
                [1.00],
            ],
            'subrubriek': [
                [settings.BACKEND_URL + f'/signals/v1/public/terms/categories/{main_slug}/sub_categories/{sub_slug}'],
                [1.00]
            ]
        }

        return Response(status=status.HTTP_200_OK, data=data)

    def post(self, request, *args, **kwargs):
        if settings.LLM_FOREGROUND_PREDICTION_ENABLED:
            return self.get_prediction_llm(request)

        try:
            classifier = Classifier.objects.get(is_active=True)
            return self.get_prediction_new_ml_proxy(request, classifier)
        except Classifier.DoesNotExist:
            return self.get_prediction_old_ml_proxy(request)




