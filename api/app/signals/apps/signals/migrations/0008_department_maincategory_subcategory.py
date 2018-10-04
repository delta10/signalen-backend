# Generated by Django 2.1 on 2018-09-13 11:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0007_auto_20180913_0848'),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False,
                                        verbose_name='ID')),
                ('code', models.CharField(max_length=3)),
                ('name', models.CharField(max_length=255)),
                ('is_intern', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='MainCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False,
                                        verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='SubCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False,
                                        verbose_name='ID')),
                ('code', models.CharField(max_length=4, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('handling', models.CharField(choices=[
                    ('A3DMC', 'A3DMC'),
                    ('A3DEC', 'A3DEC'),
                    ('A3WMC', 'A3WMC'),
                    ('A3WEC', 'A3WEC'),
                    ('I5DMC', 'I5DMC'),
                    ('STOPEC', 'STOPEC'),
                    ('KLOKLICHTZC', 'KLOKLICHTZC'),
                    ('GLADZC', 'GLADZC'),
                    ('A3DEVOMC', 'A3DEVOMC'),
                    ('WS1EC', 'WS1EC'),
                    ('WS2EC', 'WS2EC'),
                    ('REST', 'REST')
                ], max_length=20)),
                ('departments', models.ManyToManyField(to='signals.Department')),
                ('main_category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                    related_name='sub_categories',
                                                    to='signals.MainCategory')),
            ],
        ),
    ]