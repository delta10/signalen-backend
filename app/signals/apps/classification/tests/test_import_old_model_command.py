# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2026 Delta10 B.V.
import pickle
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
from django.core.management import CommandError, call_command
from django.test import TestCase

from signals.apps.classification.models import Classifier


# =============================================================================
# Pickle-able mock classes for testing
# =============================================================================
# These need to be at module level to be pickle-able

class MockClassifier:
    """Mock classifier for testing."""
    def __init__(self):
        self.classes_ = np.array([])


class MockPipeline:
    """Mock pipeline for testing."""
    def __init__(self):
        self.steps = [('vectorizer', {}), ('classifier', MockClassifier())]


class MockModel:
    """Mock GridSearchCV model for testing."""
    def __init__(self):
        self.best_estimator_ = MockPipeline()
        self.scorer_ = None
        self.multimetric_ = False


class TestImportOldModelCommand(TestCase):
    """Tests for the import_old_model management command."""

    def setUp(self):
        """Create temporary model and slug files for testing."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test files paths
        self.main_model_path = Path(self.temp_dir) / 'main_model.pkl'
        self.main_slugs_path = Path(self.temp_dir) / 'main_slugs.pkl'
        self.sub_model_path = Path(self.temp_dir) / 'sub_model.pkl'
        self.sub_slugs_path = Path(self.temp_dir) / 'sub_slugs.pkl'

        # Create placeholder model files (will be mocked by joblib.load in tests)
        # We don't need actual model content since joblib.load is mocked
        with open(self.main_model_path, 'wb') as f:
            pickle.dump({'placeholder': 'main_model'}, f)
        with open(self.sub_model_path, 'wb') as f:
            pickle.dump({'placeholder': 'sub_model'}, f)

        # Save test slugs in old format
        main_slugs = ['/categories/afval', '/categories/overlast-openbare-ruimte']
        sub_slugs = [
            '/categories/afval/sub_categories/container',
            '/categories/overlast-openbare-ruimte/sub_categories/parkeeroverlast'
        ]

        with open(self.main_slugs_path, 'wb') as f:
            pickle.dump(main_slugs, f)
        with open(self.sub_slugs_path, 'wb') as f:
            pickle.dump(sub_slugs, f)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('signals.apps.classification.management.commands.import_old_model.joblib.load')
    def test_import_old_model_success(self, mock_joblib_load):
        """Test successful import of old models."""
        mock_joblib_load.return_value = MockModel()

        out = StringIO()
        call_command(
            'import_old_model',
            '--main-model', str(self.main_model_path),
            '--main-slugs', str(self.main_slugs_path),
            '--sub-model', str(self.sub_model_path),
            '--sub-slugs', str(self.sub_slugs_path),
            stdout=out
        )

        # Check classifier was created
        self.assertEqual(Classifier.objects.count(), 1)

        classifier = Classifier.objects.first()
        self.assertIn('Geimporteerd model', classifier.name)
        self.assertEqual(classifier.training_status, 'COMPLETED')
        self.assertIsNone(classifier.precision)
        self.assertIsNone(classifier.recall)
        self.assertIsNone(classifier.accuracy)
        self.assertFalse(classifier.is_active)

        # Check output message
        output = out.getvalue()
        self.assertIn('Successfully imported Classifier', output)
        self.assertIn('Main categories:', output)
        self.assertIn('Sub categories:', output)

    @patch('signals.apps.classification.management.commands.import_old_model.joblib.load')
    def test_import_old_model_with_activate(self, mock_joblib_load):
        """Test import with --activate flag."""
        # Create existing active classifier (without metrics, so import is allowed)
        Classifier.objects.create(
            name='Existing Model',
            is_active=True,
            training_status='COMPLETED',
            precision=None,
            recall=None,
            accuracy=None
        )

        mock_joblib_load.return_value = MockModel()

        out = StringIO()
        call_command(
            'import_old_model',
            '--main-model', str(self.main_model_path),
            '--main-slugs', str(self.main_slugs_path),
            '--sub-model', str(self.sub_model_path),
            '--sub-slugs', str(self.sub_slugs_path),
            '--activate',
            stdout=out
        )

        # Check new classifier is active and old one is not
        self.assertEqual(Classifier.objects.count(), 2)
        active_classifier = Classifier.objects.get(is_active=True)
        self.assertIn('Geimporteerd model', active_classifier.name)

        # Check output indicates activation
        output = out.getvalue()
        self.assertIn('Active: True', output)

    def test_import_old_model_file_not_found(self):
        """Test error when model file doesn't exist."""
        with self.assertRaises(CommandError) as cm:
            call_command(
                'import_old_model',
                '--main-model', '/nonexistent/path.pkl',
                '--main-slugs', str(self.main_slugs_path),
                '--sub-model', str(self.sub_model_path),
                '--sub-slugs', str(self.sub_slugs_path),
            )

        self.assertIn('does not exist', str(cm.exception))

    def test_import_old_model_prevents_overwrite_trained_model(self):
        """Test that import is blocked when trained model is active."""
        # Create active trained model with metrics
        Classifier.objects.create(
            name='Trained Model',
            is_active=True,
            training_status='COMPLETED',
            precision=0.85,
            recall=0.82,
            accuracy=0.84
        )

        with self.assertRaises(CommandError) as cm:
            call_command(
                'import_old_model',
                '--main-model', str(self.main_model_path),
                '--main-slugs', str(self.main_slugs_path),
                '--sub-model', str(self.sub_model_path),
                '--sub-slugs', str(self.sub_slugs_path),
                '--activate',
            )

        self.assertIn('Active classifier', str(cm.exception))
        self.assertIn('already a trained model with metrics', str(cm.exception))

    def test_slug_transformation_main(self):
        """Test main category slug transformation."""
        from signals.apps.classification.management.commands.import_old_model import transform_main_slug

        # Test main category transformation
        self.assertEqual(transform_main_slug('/categories/afval'), 'afval')
        self.assertEqual(transform_main_slug('/categories/overlast-openbare-ruimte/'), 'overlast-openbare-ruimte')

        # Already transformed slug should remain unchanged
        self.assertEqual(transform_main_slug('afval'), 'afval')

    def test_slug_transformation_sub(self):
        """Test sub category slug transformation."""
        from signals.apps.classification.management.commands.import_old_model import transform_sub_slug

        # Test sub category transformation
        self.assertEqual(
            transform_sub_slug('/categories/afval/sub_categories/container'),
            'afval|container'
        )
        self.assertEqual(
            transform_sub_slug('/categories/overlast-openbare-ruimte/sub_categories/parkeeroverlast/'),
            'overlast-openbare-ruimte|parkeeroverlast'
        )

        # Already transformed slug should remain unchanged
        self.assertEqual(transform_sub_slug('afval|container'), 'afval|container')

    @patch('signals.apps.classification.management.commands.import_old_model.joblib.load')
    def test_scorer_cleanup(self, mock_joblib_load):
        """Test that scorer references are cleaned up."""
        # Create mock with scorer that should be cleaned
        mock_model_instance = MockModel()
        mock_model_instance.scorer_ = 'some_scorer'  # Should be cleaned to None
        mock_model_instance.multimetric_ = True  # Should be set to False
        
        mock_joblib_load.return_value = mock_model_instance

        call_command(
            'import_old_model',
            '--main-model', str(self.main_model_path),
            '--main-slugs', str(self.main_slugs_path),
            '--sub-model', str(self.sub_model_path),
            '--sub-slugs', str(self.sub_slugs_path),
        )

        # Verify scorer was cleaned
        self.assertIsNone(mock_model_instance.scorer_)
        self.assertFalse(mock_model_instance.multimetric_)
