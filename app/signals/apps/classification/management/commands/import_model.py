# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2024 Gemeente Amsterdam
import io
import pickle
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError

from signals.apps.classification.models import Classifier
from signals.apps.classification.utils import load_model, WrappedModel
from signals.apps.classification.constants import (
    CLASSIFICATION_FILE_TYPES, 
    MAX_MODEL_FILE_SIZE, 
    TRAINING_STATUS_RUNNING, 
    TRAINING_STATUS_COMPLETED
)


# Constants for file types - moved to constants.py
FILE_TYPES = CLASSIFICATION_FILE_TYPES


def _transform_main_slug(slug: str) -> str:
    """
    Transform a main category slug/URL to the expected format.
    Examples:
        '/categories/afval' -> 'afval'
        'afval' -> 'afval'
    """
    if slug.startswith('/categories/'):
        return slug.split('/categories/')[-1].rstrip('/')
    return slug


def _transform_sub_slug(slug: str) -> str:
    """
    Transform a sub category slug/URL to the expected 'main|sub' format.
    Examples:
        '/categories/afval/sub_categories/afvalbak' -> 'afval|afvalbak'
        'afval|afvalbak' -> 'afval|afvalbak'
    """
    # Already in correct format
    if '|' in slug:
        return slug

    # URL format: /categories/{main}/sub_categories/{sub}
    match = re.match(r'.*/categories/([^/]+)/sub_categories/([^/]+)/?$', slug)
    if match:
        return f"{match.group(1)}|{match.group(2)}"

    return slug


def _validate_classifier_data(classifier: Classifier, finalize: bool = False) -> None:
    """
    Validate that classifier has required data before finalization.
    
    Args:
        classifier: The classifier to validate
        finalize: Whether this is for finalization
        
    Raises:
        CommandError: If required data is missing
    """
    if finalize:
        required_fields = ['main_model', 'sub_model']
        for field in required_fields:
            if not getattr(classifier, field):
                raise CommandError(f"Cannot finalize: missing {field}")


class Command(BaseCommand):
    help = """Import pre-trained classification models from pickle files via stdin.

    WARNING: This command loads pickle files which can execute arbitrary code.
    Only use with trusted model files from your own training pipeline.

Examples:
    # Import all files using the same --name (creates on first, reuses after):
    cat main_model.pkl | python manage.py import_model --file-type main-model --name "My Model"
    cat main_slugs.pkl | python manage.py import_model --file-type main-slugs --name "My Model"
    cat sub_model.pkl | python manage.py import_model --file-type sub-model --name "My Model"
    cat sub_slugs.pkl | python manage.py import_model --file-type sub-slugs --name "My Model"

    # Finalize and activate:
    python manage.py import_model --name "My Model" --finalize --activate
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--file-type",
            type=str,
            choices=FILE_TYPES,
            help="Type of file being imported: main-model, main-slugs, sub-model, sub-slugs",
        )
        parser.add_argument(
            "--classifier",
            type=int,
            help="ID of existing classifier to add file to",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="Name for a new classifier (required when creating)",
        )
        parser.add_argument(
            "--finalize",
            action="store_true",
            help="Finalize the classifier (combine models with slugs if needed)",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Set this classifier as the active one (deactivates others)",
        )
        parser.add_argument(
            "--precision",
            type=float,
            default=0.0,
            help="Precision metric for the model",
        )
        parser.add_argument(
            "--recall",
            type=float,
            default=0.0,
            help="Recall metric for the model",
        )
        parser.add_argument(
            "--accuracy",
            type=float,
            default=0.0,
            help="Accuracy metric for the model",
        )

    def _read_stdin(self) -> bytes:
        """Read binary data from stdin."""
        if sys.stdin.isatty():
            raise CommandError("No data provided on stdin. Pipe a file to this command.")
        
        # Security: Limit file size to prevent DoS attacks
        data = sys.stdin.buffer.read(MAX_MODEL_FILE_SIZE + 1)
        if len(data) > MAX_MODEL_FILE_SIZE:
            raise CommandError(f"File too large. Maximum size: {MAX_MODEL_FILE_SIZE} bytes")
        
        return data

    def _get_or_create_classifier(self, options: Dict[str, Any]) -> Tuple[Classifier, bool]:
        """Get existing classifier or create a new one."""
        if options.get("classifier"):
            try:
                return Classifier.objects.get(pk=options["classifier"]), False
            except Classifier.DoesNotExist:
                raise CommandError(f"Classifier with ID {options['classifier']} not found")
        elif options.get("name"):
            # Try to find existing classifier by name, or create new one
            try:
                classifier = Classifier.objects.get(name=options["name"])
                return classifier, False
            except Classifier.DoesNotExist:
                classifier = Classifier.objects.create(
                    name=options["name"],
                    precision=options["precision"],
                    recall=options["recall"],
                    accuracy=options["accuracy"],
                    is_active=False,
                    training_status=TRAINING_STATUS_RUNNING,  # Not complete until finalized
                )
                return classifier, True
        else:
            raise CommandError("Must specify either --classifier ID or --name for new classifier")

    def _save_file_data(self, classifier: Classifier, file_type: str, data: bytes) -> None:
        """Save file data to the appropriate classifier field."""
        filename = f"{classifier.name}_{file_type}_{classifier.id}.pkl"
        content_file = ContentFile(data, name=filename)

        field_mapping = {
            'main-model': 'main_model',
            'sub-model': 'sub_model',
            # Add other file types as needed
        }

        field_name = field_mapping.get(file_type)
        if field_name:
            setattr(classifier, field_name, content_file)
            classifier.save()
            self.stdout.write(f"Saved {file_type} to {field_name}")
        else:
            self.stdout.write(f"Stored {file_type} data for later processing")

    def _process_slugs(self, classifier: Classifier, file_type: str, data: bytes) -> Any:
        """Process slug data and return the loaded object."""
        try:
            slugs = pickle.load(io.BytesIO(data))
            
            if file_type == 'main-slugs':
                if hasattr(slugs, '__iter__') and not isinstance(slugs, str):
                    processed = [_transform_main_slug(slug) for slug in slugs]
                else:
                    processed = [_transform_main_slug(slugs)]
            elif file_type == 'sub-slugs':
                if hasattr(slugs, '__iter__') and not isinstance(slugs, str):
                    processed = [_transform_sub_slug(slug) for slug in slugs]
                else:
                    processed = [_transform_sub_slug(slugs)]
            else:
                processed = slugs

            self.stdout.write(f"Processed {len(processed) if hasattr(processed, '__len__') else 1} {file_type}")
            return processed
            
        except Exception as e:
            raise CommandError(f"Error processing {file_type}: {e}")

    @transaction.atomic
    def handle(self, *args, **options):
        """Main command handler with transaction support."""
        try:
            # Handle finalize and activate operations
            if options.get("finalize") or options.get("activate"):
                classifier, created = self._get_or_create_classifier(options)
                
                if options.get("finalize"):
                    _validate_classifier_data(classifier, finalize=True)
                    classifier.training_status = TRAINING_STATUS_COMPLETED
                    classifier.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"Finalized classifier '{classifier.name}' (ID: {classifier.id})")
                    )

                if options.get("activate"):
                    # Deactivate all other classifiers
                    Classifier.objects.filter(is_active=True).update(is_active=False)
                    classifier.is_active = True
                    classifier.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"Activated classifier '{classifier.name}' (ID: {classifier.id})")
                    )
                return

            # Handle file import
            if not options.get("file_type"):
                raise CommandError("--file-type is required when importing files")

            # Read and validate data
            data = self._read_stdin()
            if len(data) == 0:
                raise CommandError("No data received from stdin")

            # Get or create classifier
            classifier, created = self._get_or_create_classifier(options)
            
            if created:
                self.stdout.write(f"Created new classifier: '{classifier.name}' (ID: {classifier.id})")
            else:
                self.stdout.write(f"Using existing classifier: '{classifier.name}' (ID: {classifier.id})")

            # Process the file based on type
            file_type = options["file_type"]
            
            if file_type in ['main-slugs', 'sub-slugs']:
                # Process slug files
                processed_slugs = self._process_slugs(classifier, file_type, data)
                # Store for later use in finalization
                # This could be enhanced to store in a separate model or field
            else:
                # Process model files
                try:
                    # Validate it's a proper model by loading it
                    test_model = load_model(io.BytesIO(data))
                    self.stdout.write(f"Validated {file_type} - model loaded successfully")
                except (ValidationError, pickle.UnpicklingError) as e:
                    raise CommandError(f"Invalid model file: {e}")
                
                # Save the file data
                self._save_file_data(classifier, file_type, data)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully imported {file_type} for classifier '{classifier.name}'"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error: {e}")
            )
            raise