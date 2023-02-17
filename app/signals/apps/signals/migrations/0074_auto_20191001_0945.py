# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2019 - 2021 Gemeente Amsterdam
# Generated by Django 2.1.11 on 2019-10-01 07:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0073_set_slo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categorytranslation',
            name='old_category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='translations', to='signals.Category'),  # noqa
        ),
    ]