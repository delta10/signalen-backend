# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.
from django.db import models
from pydantic import BaseModel

class LlmResponse(BaseModel):
    main_category: str
    sub_category: str
    text: str

class LlmPrediction(models.Model):
    llm_predicted_category = models.TextField(null=False, blank=False)
    tfidf_predicted_category = models.TextField(null=False, blank=False)
    signal = models.ForeignKey(
        'signals.Signal',
        null=False, on_delete=models.CASCADE
    )

    class Meta:
        ordering = ('id',)