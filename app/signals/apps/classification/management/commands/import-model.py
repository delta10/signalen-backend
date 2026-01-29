# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2024 Gemeente Amsterdam
import pickle
import re
import sys

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from signals.apps.classification.models import Classifier
from signals.apps.classification.utils import load_model, WrappedModel


FILE_TYPES = ['main-model', 'main-slugs', 'sub-model', 'sub-slugs']


def _transform_main_slug(slug):
    """
    Transform a main category slug/URL to the expected format.
    Examples:
        '/categories/afval' -> 'afval'
        'afval' -> 'afval'
    """
    if slug.startswith('/categories/'):
        return slug.split('/categories/')[-1].rstrip('/')
    return slug


def _transform_sub_slug(slug):
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


class Command(BaseCommand):
    help = """Import pre-trained classification models from pickle files via stdin.

Examples:
    # Import all files using the same --name (creates on first, reuses after):
    cat main_model.pkl | python manage.py import-model --file-type main-model --name "My Model"
    cat main_slugs.pkl | python manage.py import-model --file-type main-slugs --name "My Model"
    cat sub_model.pkl | python manage.py import-model --file-type sub-model --name "My Model"
    cat sub_slugs.pkl | python manage.py import-model --file-type sub-slugs --name "My Model"

    # Finalize and activate:
    python manage.py import-model --name "My Model" --finalize --activate
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

    def _read_stdin(self):
        """Read binary data from stdin."""
        if sys.stdin.isatty():
            raise CommandError("No data provided on stdin. Pipe a file to this command.")
        return sys.stdin.buffer.read()

    def _get_or_create_classifier(self, options):
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
                    training_status="RUNNING",  # Not complete until finalized
                )
                return classifier, True
        else:
            raise CommandError("--name or --classifier is required")

    def _save_file(self, classifier, file_type, content):
        """Save a file to the classifier."""
        filename = f"{classifier.pk}_{file_type.replace('-', '_')}.pkl"

        if file_type == 'main-model':
            classifier.main_model.save(filename, ContentFile(content))
        elif file_type == 'sub-model':
            classifier.sub_model.save(filename, ContentFile(content))
        elif file_type == 'main-slugs':
            # Store slugs temporarily in main_confusion_matrix field
            classifier.main_confusion_matrix.save(f"{classifier.pk}_main_slugs.pkl", ContentFile(content))
        elif file_type == 'sub-slugs':
            # Store slugs temporarily in sub_confusion_matrix field
            classifier.sub_confusion_matrix.save(f"{classifier.pk}_sub_slugs.pkl", ContentFile(content))
        classifier.save()

    def _finalize_classifier(self, classifier, activate):
        """Finalize the classifier by combining models with slugs if needed."""
        # Check we have the required model files
        if not classifier.main_model:
            raise CommandError("Missing main-model. Import it first.")
        if not classifier.sub_model:
            raise CommandError("Missing sub-model. Import it first.")

        # Load main model using custom unpickler (handles missing modules)
        main_model = load_model(classifier.main_model)
        self.stdout.write(f"  Loaded main model: {type(main_model).__name__}")

        # Check if it's a valid sklearn model with predict methods
        is_sklearn_model = (
            hasattr(main_model, 'predict') and
            callable(getattr(main_model, 'predict', None)) and
            hasattr(main_model, 'predict_proba') and
            callable(getattr(main_model, 'predict_proba', None))
        )

        # For sklearn models, classes_ might be on the model or best_estimator_
        classes_attr = None
        if hasattr(main_model, 'classes_') and main_model.classes_ is not None:
            classes_attr = main_model.classes_
        elif hasattr(main_model, 'best_estimator_') and hasattr(main_model.best_estimator_, 'classes_'):
            classes_attr = main_model.best_estimator_.classes_

        has_classes = classes_attr is not None and len(classes_attr) > 0
        self.stdout.write(f"  Is sklearn model: {is_sklearn_model}, Has classes: {has_classes}")

        # Check if we need to wrap with slugs
        if not has_classes:
            if not classifier.main_confusion_matrix:
                raise CommandError(
                    "Main model doesn't have classes_ embedded and no main-slugs file was provided."
                )
            classifier.main_confusion_matrix.seek(0)
            main_slugs = pickle.load(classifier.main_confusion_matrix)
            if isinstance(main_slugs, dict):
                classes = [main_slugs[i] for i in sorted(main_slugs.keys())]
            else:
                classes = list(main_slugs)
            # Transform slugs to expected format
            classes = [_transform_main_slug(s) for s in classes]
            main_model = WrappedModel(main_model, classes)
            self.stdout.write(f"  Wrapped main model with {len(classes)} classes: {classes[:3]}...")

            # Save the wrapped model
            main_content = pickle.dumps(main_model, protocol=pickle.HIGHEST_PROTOCOL)
            classifier.main_model.delete(save=False)
            classifier.main_model.save(
                f"{classifier.pk}_main_model.pkl",
                ContentFile(main_content)
            )
            # Clear the temporary slugs storage
            classifier.main_confusion_matrix.delete(save=False)

        # Load sub model using custom unpickler
        sub_model = load_model(classifier.sub_model)
        self.stdout.write(f"  Loaded sub model: {type(sub_model).__name__}")

        # Check if it's a valid sklearn model with predict methods
        is_sklearn_model = (
            hasattr(sub_model, 'predict') and
            callable(getattr(sub_model, 'predict', None)) and
            hasattr(sub_model, 'predict_proba') and
            callable(getattr(sub_model, 'predict_proba', None))
        )

        # For sklearn models, classes_ might be on the model or best_estimator_
        classes_attr = None
        if hasattr(sub_model, 'classes_') and sub_model.classes_ is not None:
            classes_attr = sub_model.classes_
        elif hasattr(sub_model, 'best_estimator_') and hasattr(sub_model.best_estimator_, 'classes_'):
            classes_attr = sub_model.best_estimator_.classes_

        has_classes = classes_attr is not None and len(classes_attr) > 0
        self.stdout.write(f"  Is sklearn model: {is_sklearn_model}, Has classes: {has_classes}")

        # Check if we need to wrap with slugs
        if not has_classes:
            if not classifier.sub_confusion_matrix:
                raise CommandError(
                    "Sub model doesn't have classes_ embedded and no sub-slugs file was provided."
                )
            classifier.sub_confusion_matrix.seek(0)
            sub_slugs = pickle.load(classifier.sub_confusion_matrix)
            if isinstance(sub_slugs, dict):
                classes = [sub_slugs[i] for i in sorted(sub_slugs.keys())]
            else:
                classes = list(sub_slugs)
            # Transform slugs to expected 'main|sub' format
            classes = [_transform_sub_slug(s) for s in classes]
            sub_model = WrappedModel(sub_model, classes)
            self.stdout.write(f"  Wrapped sub model with {len(classes)} classes: {classes[:3]}...")

            # Save the wrapped model
            sub_content = pickle.dumps(sub_model, protocol=pickle.HIGHEST_PROTOCOL)
            classifier.sub_model.delete(save=False)
            classifier.sub_model.save(
                f"{classifier.pk}_sub_model.pkl",
                ContentFile(sub_content)
            )
            # Clear the temporary slugs storage
            classifier.sub_confusion_matrix.delete(save=False)

        # Get final classes for validation and logging
        if hasattr(sub_model, 'classes_') and sub_model.classes_ is not None:
            sub_classes = list(sub_model.classes_)
        elif hasattr(sub_model, 'best_estimator_') and hasattr(sub_model.best_estimator_, 'classes_'):
            sub_classes = list(sub_model.best_estimator_.classes_)
        else:
            sub_classes = []

        if hasattr(main_model, 'classes_') and main_model.classes_ is not None:
            main_classes = list(main_model.classes_)
        elif hasattr(main_model, 'best_estimator_') and hasattr(main_model.best_estimator_, 'classes_'):
            main_classes = list(main_model.best_estimator_.classes_)
        else:
            main_classes = []

        # Validate sub model classes format
        invalid_classes = [c for c in sub_classes if '|' not in str(c)]
        if invalid_classes:
            self.stdout.write(self.style.WARNING(
                f"Warning: Some sub model classes don't follow 'main|sub' format: {invalid_classes[:3]}"
            ))

        # Mark as completed
        classifier.training_status = "COMPLETED"

        if activate:
            Classifier.objects.filter(is_active=True).update(is_active=False)
            classifier.is_active = True
            self.stdout.write("  Classifier is now ACTIVE")

        classifier.save()

        self.stdout.write(f"  Main model: {len(main_classes)} classes")
        self.stdout.write(f"  Sub model: {len(sub_classes)} classes")

    def handle(self, *args, **options):
        file_type = options.get("file_type")
        finalize = options.get("finalize")

        # Finalize mode
        if finalize:
            if options.get("classifier"):
                try:
                    classifier = Classifier.objects.get(pk=options["classifier"])
                except Classifier.DoesNotExist:
                    raise CommandError(f"Classifier with ID {options['classifier']} not found")
            elif options.get("name"):
                try:
                    classifier = Classifier.objects.get(name=options["name"])
                except Classifier.DoesNotExist:
                    raise CommandError(f"Classifier with name '{options['name']}' not found")
            else:
                raise CommandError("--classifier or --name is required with --finalize")

            self.stdout.write(f"Finalizing classifier {classifier.pk} ('{classifier.name}')...")
            self._finalize_classifier(classifier, options.get("activate"))
            self.stdout.write(self.style.SUCCESS(
                f"Successfully finalized classifier (ID: {classifier.pk})"
            ))
            return

        # Import file mode
        if not file_type:
            raise CommandError("--file-type is required when importing a file")

        # Read from stdin
        content = self._read_stdin()
        self.stdout.write(f"Read {len(content)} bytes from stdin")

        # Get or create classifier
        classifier, created = self._get_or_create_classifier(options)
        if created:
            self.stdout.write(f"Created new classifier (ID: {classifier.pk}, Name: '{classifier.name}')")
        else:
            self.stdout.write(f"Using existing classifier (ID: {classifier.pk}, Name: '{classifier.name}')")

        # Save the file
        self._save_file(classifier, file_type, content)
        self.stdout.write(self.style.SUCCESS(f"Saved {file_type} to classifier {classifier.pk}"))

        # Print next steps
        if created:
            self.stdout.write(f"\nNext steps:")
            self.stdout.write(f"  1. Import remaining files with --name \"{classifier.name}\"")
            self.stdout.write(f"  2. Finalize with: python manage.py import-model --name \"{classifier.name}\" --finalize --activate")
