# Generated by Django 4.2.11 on 2024-09-17 09:53

from django.db import migrations, models

import signals.apps.services.domain.checker_factories
import signals.apps.services.domain.mimetypes
import signals.apps.services.validator.file
import signals.apps.signals.models.utils


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=255)),
                ('file', models.FileField(max_length=255, upload_to='training_sets/%Y/%m/%d/', validators=[
                    signals.apps.services.validator.file.MimeTypeAllowedValidator(
                        signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(),
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    ),
                    signals.apps.services.validator.file.MimeTypeIntegrityValidator(
                        signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(),
                        signals.apps.services.domain.mimetypes.MimeTypeFromFilenameResolverFactory()
                    ),
                    signals.apps.services.validator.file.ContentIntegrityValidator(
                        signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(),
                        signals.apps.services.domain.checker_factories.ContentCheckerFactory()
                    ),
                    signals.apps.services.validator.file.FileSizeValidator(20971520)
                ])),
            ],
        ),
    ]
