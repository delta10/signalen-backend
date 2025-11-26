# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.
from django import forms

from signals.apps.llm_prediction.models import LlmPrediction


class LlmPredictionForm(forms.ModelForm):
    class Meta:
        model = LlmPrediction
        fields = '__all__'