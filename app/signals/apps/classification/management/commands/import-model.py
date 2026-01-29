import sys
import tempfile
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from signals.apps.classification.models import Classifier


class Command(BaseCommand):
    help = 'Import classification models from stdin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file-type',
            choices=['main-model', 'sub-model', 'main-slugs', 'sub-slugs'],
            required=True,
            help='Type of model file to import'
        )
        parser.add_argument(
            '--name',
            required=True,
            help='Name of the classifier'
        )

    def handle(self, *args, **options):
        file_type = options['file_type']
        name = options['name']

        # Read model data from stdin
        model_data = sys.stdin.buffer.read()
        
        if not model_data:
            raise CommandError("No data received from stdin")

        # Get or create classifier
        classifier, created = Classifier.objects.get_or_create(
            name=name,
            defaults={
                'is_active': True,
                'training_status': 'COMPLETED'
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created new classifier: {name}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Using existing classifier: {name}')
            )

        # Create temporary file with the model data
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as temp_file:
            temp_file.write(model_data)
            temp_file.flush()
            
            # Create Django File object
            with open(temp_file.name, 'rb') as f:
                django_file = File(f, name=f'{name}_{file_type.replace("-", "_")}.pkl')
                
                # Save to appropriate field
                if file_type == 'main-model':
                    classifier.main_model.save(
                        django_file.name,
                        django_file,
                        save=True
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully imported main model for {name}')
                    )
                elif file_type == 'sub-model':
                    classifier.sub_model.save(
                        django_file.name,
                        django_file,
                        save=True
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully imported sub model for {name}')
                    )
                elif file_type == 'main-slugs':
                    # Store main slugs in main_confusion_matrix field as a temporary solution
                    classifier.main_confusion_matrix.save(
                        django_file.name,
                        django_file,
                        save=True
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully imported main slugs for {name}')
                    )
                elif file_type == 'sub-slugs':
                    # Store sub slugs in sub_confusion_matrix field as a temporary solution
                    classifier.sub_confusion_matrix.save(
                        django_file.name,
                        django_file,
                        save=True
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully imported sub slugs for {name}')
                    )

        # Clean up temporary file
        Path(temp_file.name).unlink(missing_ok=True)