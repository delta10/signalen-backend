# Generated by Django 4.2.15 on 2024-10-17 09:55

from django.db import migrations, models
import signals.apps.classification.utils
import signals.apps.services.domain.checker_factories
import signals.apps.services.domain.mimetypes
import signals.apps.services.validator.file


class Migration(migrations.Migration):

    dependencies = [
        ('classification', '0005_classifier_is_active_alter_classifier_main_model_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifier',
            name='training_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='classifier',
            name='training_status',
            field=models.CharField(choices=[('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed')], default='RUNNING', max_length=20),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='main_model',
            field=models.FileField(blank=True, max_length=255, null=True, storage=signals.apps.classification.utils._get_storage_backend, upload_to='classification_models/main/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='sub_model',
            field=models.FileField(blank=True, max_length=255, null=True, storage=signals.apps.classification.utils._get_storage_backend, upload_to='classification_models/main_sub/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='trainingset',
            name='file',
            field=models.FileField(max_length=255, storage=signals.apps.classification.utils._get_storage_backend, upload_to='training_sets/%Y/%m/%d/', validators=[signals.apps.services.validator.file.MimeTypeAllowedValidator(signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), signals.apps.services.validator.file.MimeTypeIntegrityValidator(signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(), signals.apps.services.domain.mimetypes.MimeTypeFromFilenameResolverFactory()), signals.apps.services.validator.file.ContentIntegrityValidator(signals.apps.services.domain.mimetypes.MimeTypeFromContentResolverFactory(), signals.apps.services.domain.checker_factories.ContentCheckerFactory()), signals.apps.services.validator.file.FileSizeValidator(20971520)]),
        ),
    ]