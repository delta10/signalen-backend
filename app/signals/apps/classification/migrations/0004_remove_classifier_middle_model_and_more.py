# Generated by Django 4.2.11 on 2024-09-19 08:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classification', '0003_classifier_accuracy_classifier_precision_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classifier',
            name='middle_model',
        ),
        migrations.RemoveField(
            model_name='classifier',
            name='middle_sub_model',
        ),
        migrations.AddField(
            model_name='classifier',
            name='main_model',
            field=models.FileField(blank=True, max_length=255, null=True, upload_to='classification_models/middle/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='classifier',
            name='sub_model',
            field=models.FileField(blank=True, max_length=255, null=True, upload_to='classification_models/middle_sub/%Y/%m/%d/'),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='accuracy',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='precision',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='recall',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]