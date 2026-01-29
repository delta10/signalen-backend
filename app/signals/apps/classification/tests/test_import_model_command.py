# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2024 Gemeente Amsterdam
import io
import pickle
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from signals.apps.classification.models import Classifier


class ImportModelCommandTest(TestCase):
    """Test cases for the import_model management command."""

    def setUp(self):
        """Set up test data."""
        self.classifier_name = "Test Classifier"
        self.test_model_data = self._create_mock_model_data()

    def _create_mock_model_data(self) -> bytes:
        """Create mock model data for testing."""
        # Create a simple mock model that has predict and predict_proba methods
        class MockModel:
            def __init__(self):
                self.classes_ = ['class1', 'class2']
                
            def predict(self, X):
                return [self.classes_[0]] * len(X) if isinstance(X, list) else [self.classes_[0]]
                
            def predict_proba(self, X):
                import numpy as np
                n_samples = len(X) if isinstance(X, list) else 1
                return np.array([[1.0, 0.0]] * n_samples)
        
        mock_model = MockModel()
        return pickle.dumps(mock_model)

    def test_create_classifier_with_name(self):
        """Test creating a new classifier with --name parameter."""
        initial_count = Classifier.objects.count()
        
        with patch('sys.stdin.buffer.read', return_value=self.test_model_data):
            call_command(
                'import_model',
                '--name', self.classifier_name,
                '--file-type', 'main-model'
            )
        
        self.assertEqual(Classifier.objects.count(), initial_count + 1)
        classifier = Classifier.objects.get(name=self.classifier_name)
        self.assertEqual(classifier.name, self.classifier_name)
        self.assertEqual(classifier.training_status, "RUNNING")
        self.assertFalse(classifier.is_active)

    def test_finalize_classifier(self):
        """Test finalizing a classifier."""
        # Create a classifier with models
        classifier = Classifier.objects.create(
            name=self.classifier_name,
            training_status="RUNNING"
        )
        
        # Mock the file fields to simulate having models
        with patch.object(classifier, 'main_model', MagicMock()):
            with patch.object(classifier, 'sub_model', MagicMock()):
                call_command(
                    'import_model',
                    '--name', self.classifier_name,
                    '--finalize'
                )
        
        classifier.refresh_from_db()
        self.assertEqual(classifier.training_status, "COMPLETED")

    def test_activate_classifier(self):
        """Test activating a classifier."""
        # Create multiple classifiers
        classifier1 = Classifier.objects.create(name="Classifier 1", is_active=True)
        classifier2 = Classifier.objects.create(name="Classifier 2", is_active=False)
        
        # Activate classifier2
        call_command(
            'import_model',
            '--classifier', classifier2.id,
            '--activate'
        )
        
        # Refresh from database
        classifier1.refresh_from_db()
        classifier2.refresh_from_db()
        
        self.assertFalse(classifier1.is_active)
        self.assertTrue(classifier2.is_active)

    def test_no_stdin_data_raises_error(self):
        """Test that command raises error when no stdin data is provided."""
        with patch('sys.stdin.isatty', return_value=True):
            with self.assertRaises(CommandError) as context:
                call_command(
                    'import_model',
                    '--name', self.classifier_name,
                    '--file-type', 'main-model'
                )
            self.assertIn("No data provided on stdin", str(context.exception))

    def test_file_size_limit(self):
        """Test that large files are rejected."""
        large_data = b'x' * (101 * 1024 * 1024)  # 101MB
        
        with patch('sys.stdin.buffer.read', return_value=large_data):
            with self.assertRaises(CommandError) as context:
                call_command(
                    'import_model',
                    '--name', self.classifier_name,
                    '--file-type', 'main-model'
                )
            self.assertIn("File too large", str(context.exception))

    def test_invalid_model_data(self):
        """Test handling of invalid model data."""
        invalid_data = b'not a pickle file'
        
        with patch('sys.stdin.buffer.read', return_value=invalid_data):
            with self.assertRaises(CommandError) as context:
                call_command(
                    'import_model',
                    '--name', self.classifier_name,
                    '--file-type', 'main-model'
                )
            self.assertIn("Invalid model file", str(context.exception))

    def test_missing_required_arguments(self):
        """Test that missing required arguments raise appropriate errors."""
        with patch('sys.stdin.buffer.read', return_value=self.test_model_data):
            # Missing --file-type
            with self.assertRaises(CommandError) as context:
                call_command(
                    'import_model',
                    '--name', self.classifier_name
                )
            self.assertIn("--file-type is required", str(context.exception))
            
            # Missing --name or --classifier
            with self.assertRaises(CommandError) as context:
                call_command(
                    'import_model',
                    '--file-type', 'main-model'
                )
            self.assertIn("Must specify either --classifier ID or --name", str(context.exception))

    def test_classifier_validation_on_finalize(self):
        """Test that finalization validates required fields."""
        classifier = Classifier.objects.create(
            name=self.classifier_name,
            training_status="RUNNING"
        )
        # Don't set main_model or sub_model
        
        with self.assertRaises(CommandError) as context:
            call_command(
                'import_model',
                '--classifier', classifier.id,
                '--finalize'
            )
        self.assertIn("Cannot finalize: missing", str(context.exception))