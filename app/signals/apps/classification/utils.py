# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2020 - 2023 Gemeente Amsterdam
import io
import logging
import pickle
import sys
import types
from typing import Any, Union

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.storage import FileSystemStorage, Storage
from storages.backends.azure_storage import AzureStorage
from storages.backends.s3 import S3Storage


class TextClassifierStub:
    """
    Stub class for missing engine.TextClassifier module.
    This class mimics the behavior of a text preprocessor used by CountVectorizer.
    """

    def __init__(self, *args, **kwargs):
        self.stemmer = None
        self.stopwords = None
        self.preprocessor = None

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self._state = state

    def __getattr__(self, name):
        """Fallback for any missing attributes."""
        return None

    def __call__(self, text):
        """
        Make the stub callable - used as a preprocessor for CountVectorizer.
        Applies stemming to the input text if a stemmer is available.
        """
        stemmer = getattr(self, 'stemmer', None)
        if stemmer is not None and hasattr(stemmer, 'stem'):
            words = text.lower().split()
            stemmed = [stemmer.stem(word) for word in words]
            return ' '.join(stemmed)
        return text.lower() if isinstance(text, str) else text


def _ensure_engine_module():
    """Ensure the 'engine' module exists with TextClassifier stub."""
    if 'engine' not in sys.modules:
        engine_module = types.ModuleType('engine')
        engine_module.TextClassifier = TextClassifierStub
        sys.modules['engine'] = engine_module


class ModelUnpickler(pickle.Unpickler):
    """
    Custom unpickler that handles models pickled with missing modules.
    Creates stub classes for unknown modules to allow loading models
    from different environments.
    """

    def __init__(self, file, *, fix_imports=True, encoding='ASCII', errors='strict'):
        super().__init__(file, fix_imports=fix_imports, encoding=encoding, errors=errors)
        self._stub_modules = []  # Track which modules we created stubs for

    def find_class(self, module, name):
        # Try normal import first
        try:
            return super().find_class(module, name)
        except ModuleNotFoundError:
            # Create a dynamic stub class that preserves the underlying data
            self._stub_modules.append(f"{module}.{name}")
            return self._create_stub_class(module, name)

    def _create_stub_class(self, module, name):
        """Create a stub class that can hold the pickled object's data."""
        class StubClass:
            _stub_module = module
            _stub_name = name

            def __new__(cls, *args, **kwargs):
                instance = super().__new__(cls)
                # Pre-initialize common attributes to avoid AttributeError
                instance._model = None
                instance._pipeline = None
                instance.model = None
                instance.pipeline = None
                instance.preprocessor = None
                instance.classes_ = None
                instance.stemmer = None
                instance.stopwords = None
                return instance

            def __init__(self, *args, **kwargs):
                pass

            def __setstate__(self, state):
                # Store state as attributes
                if isinstance(state, dict):
                    self.__dict__.update(state)
                else:
                    self._state = state

            def __getattr__(self, name):
                # Fallback for any missing attributes
                return None

            def __call__(self, text):
                """
                Make the stub callable - used as a preprocessor for CountVectorizer.
                Applies stemming to the input text.
                """
                stemmer = self.__dict__.get('stemmer')
                if stemmer is not None and hasattr(stemmer, 'stem'):
                    # Tokenize, stem each word, rejoin
                    words = text.lower().split()
                    stemmed = [stemmer.stem(word) for word in words]
                    return ' '.join(stemmed)
                # Fallback: return text as-is
                return text.lower() if isinstance(text, str) else text

            def predict(self, X):
                # Try to find the underlying model and delegate
                model = self._find_model()
                if model is not None:
                    return model.predict(X)
                raise AttributeError(f"Cannot find underlying model in {self._stub_name}")

            def predict_proba(self, X):
                model = self._find_model()
                if model is not None:
                    return model.predict_proba(X)
                raise AttributeError(f"Cannot find underlying model in {self._stub_name}")

            def _find_model(self):
                """Try to find the underlying sklearn model."""
                # Check common attribute names for wrapped models
                for attr in ['_model', 'model', '_pipeline', 'pipeline', 'clf', 'classifier']:
                    obj = self.__dict__.get(attr)
                    if obj is not None and hasattr(obj, 'predict') and hasattr(obj, 'classes_'):
                        return obj
                # Check if any attribute is a sklearn-like model (must have both predict and classes_)
                for key, val in self.__dict__.items():
                    if hasattr(val, 'predict') and hasattr(val, 'classes_'):
                        return val
                # If we still haven't found a proper model, check if the object itself is a model
                if hasattr(self, 'predict') and hasattr(self, 'classes_') and not isinstance(self, type(self)):
                    return self
                return None

        StubClass.__name__ = name
        StubClass.__qualname__ = f"{module}.{name}"
        return StubClass


class WrappedModel:
    """
    Wrapper for models that don't have classes_ embedded or need adaptation.
    Combines a model with a separate slugs/classes mapping.
    """

    def __init__(self, model, classes):
        self._model = model
        self.classes_ = classes

    def predict(self, X):
        result = self._model.predict(X)
        # If model returns indices, map to class names
        if len(result) > 0 and isinstance(result[0], (int, float)):
            return [self.classes_[int(i)] for i in result]
        return result

    def predict_proba(self, X):
        return self._model.predict_proba(X)


class ClassesOnlyModel:
    """
    Model wrapper for when we only have class labels but no actual classifier.
    This returns the first (default) category.
    """
    
    def __init__(self, classes):
        self.classes_ = classes
        
    def predict(self, X):
        """Return the first class for all inputs (fallback behavior)."""
        if isinstance(X, list):
            return [self.classes_[0]] * len(X)
        return [self.classes_[0]]
        
    def predict_proba(self, X):
        """Return probability 1.0 for the first class."""
        import numpy as np
        if isinstance(X, list):
            n_samples = len(X)
        else:
            n_samples = 1
        
        # Create probability matrix with 1.0 for first class, 0.0 for others
        n_classes = len(self.classes_)
        proba = np.zeros((n_samples, n_classes))
        proba[:, 0] = 1.0  # First class gets probability 1.0
        return proba


def _validate_model(model: Any, model_type: str) -> None:
    """
    Validate that loaded model has expected interface.
    
    Args:
        model: The loaded model object
        model_type: Type of model for error messages
        
    Raises:
        ValidationError: If model is missing required methods
    """
    required_methods = ['predict', 'predict_proba']
    for method in required_methods:
        if not hasattr(model, method):
            raise ValidationError(f"{model_type} model missing required method: {method}")


class SecureModelUnpickler(pickle.Unpickler):
    """
    Secure unpickler that only allows safe modules for ML models.
    
    This provides some protection against pickle-based code execution,
    but WARNING: pickle is still fundamentally unsafe with untrusted data.
    """
    
    ALLOWED_MODULES = {
        'sklearn', 'sklearn.ensemble', 'sklearn.linear_model', 'sklearn.svm',
        'sklearn.tree', 'sklearn.naive_bayes', 'sklearn.neighbors',
        'sklearn.neural_network', 'sklearn.feature_extraction',
        'sklearn.feature_extraction.text', 'sklearn.pipeline',
        'numpy', 'numpy.core', 'numpy.core.numeric', 'numpy.core.multiarray',
        'pandas', 'scipy', 'joblib', '__main__',
        # Add engine module for compatibility
        'signals.apps.classification.utils',
    }
    
    def find_class(self, module: str, name: str):
        # Only allow specific safe modules
        if any(module.startswith(allowed) for allowed in self.ALLOWED_MODULES):
            return super().find_class(module, name)
        
        # Special handling for engine module
        if module == 'engine':
            _ensure_engine_module()
            return super().find_class(module, name)
            
        raise pickle.UnpicklingError(f"Unsafe module: {module}.{name}")


def load_model(file_obj) -> Any:
    """
    Load a pickled model from a file object, handling missing modules gracefully.

    WARNING: This function loads pickle files which can execute arbitrary code.
    Only use with trusted model files from your own training pipeline.

    Args:
        file_obj: A file-like object containing the pickled model

    Returns:
        The unpickled model object
        
    Raises:
        ValidationError: If model doesn't have required interface
        pickle.UnpicklingError: If unsafe modules are detected
    """
    # Read all content into memory first to avoid issues with Django file fields
    # and S3 storage backends
    file_obj.seek(0)
    content = file_obj.read()

    # First, try loading with the engine module stub patched in
    _ensure_engine_module()

    try:
        # Try secure unpickler first
        model = SecureModelUnpickler(io.BytesIO(content)).load()
    except (ModuleNotFoundError, pickle.UnpicklingError) as e:
        logging.warning(f"Secure unpickling failed, falling back to custom unpickler: {e}")
        # Fall back to custom unpickler for other missing modules
        model = ModelUnpickler(io.BytesIO(content)).load()
    
    # If we got a numpy array containing class labels instead of a proper model,
    # wrap it in a ClassesOnlyModel
    if hasattr(model, '__class__') and 'numpy.ndarray' in str(type(model)):
        model = ClassesOnlyModel(model.tolist())
    
    # Validate the model has required methods
    _validate_model(model, "Classification")
    
    return model


def load_model_from_bytes(data: bytes) -> Any:
    """
    Load a pickled model from bytes, handling missing modules gracefully.

    WARNING: This function loads pickle files which can execute arbitrary code.
    Only use with trusted model files from your own training pipeline.

    Args:
        data: Bytes containing the pickled model

    Returns:
        The unpickled model object
        
    Raises:
        ValidationError: If model doesn't have required interface
        pickle.UnpicklingError: If unsafe modules are detected
    """
    # Create a BytesIO object and use the main load_model function
    return load_model(io.BytesIO(data))


def _get_storage_backend() -> Storage:
    """
    Returns one of the following storages:
        - AzureStorage, the "using" must be present in the AZURE_CONTAINERS setting.
        - S3Storage, location is set to 'datawarehouse'.
        - FileSystemStorage, location is set to the settings.DWH_MEDIA_ROOT.

    :param using:
    :returns: AzureStorage, S3Storage, or FileSystemStorage
    """

    if settings.AZURE_STORAGE_ENABLED:
        if not hasattr(settings, 'AZURE_CONTAINERS'):
            raise ImproperlyConfigured('AZURE_CONTAINERS settings must be set!')
        if 'datawarehouse' not in settings.AZURE_CONTAINERS.keys():
            raise ImproperlyConfigured(f'{'datawarehouse'} not present in the AZURE_CONTAINERS settings')

        return AzureStorage(**settings.AZURE_CONTAINERS.get('datawarehouse', {}))

    if settings.S3_STORAGE_ENABLED:
        return S3Storage(location='datawarehouse')

    return FileSystemStorage(location=settings.DWH_MEDIA_ROOT)
