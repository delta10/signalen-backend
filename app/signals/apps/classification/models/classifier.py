from django.contrib.gis.db import models


class Classifier(models.Model):
    """
    This model represents a classification model consisting of a reference to the "Main" model and a reference to the

    "Main, Sub" model
    """
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    name = models.CharField(max_length=255, null=False, blank=False)
    precision = models.FloatField(null=True, blank=True, default=0)
    recall = models.FloatField(null=True, blank=True, default=0)
    accuracy = models.FloatField(null=True, blank=True, default=0)

    main_model = models.FileField(
        upload_to='classification_models/middle/%Y/%m/%d/',
        null=True,
        blank=True,
        max_length=255,
    )

    sub_model = models.FileField(
        upload_to='classification_models/middle_sub/%Y/%m/%d/',
        null=True,
        blank=True,
        max_length=255,
    )