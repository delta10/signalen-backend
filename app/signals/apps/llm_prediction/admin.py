# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.
from django.contrib import admin

from signals.apps.llm_prediction.forms import LlmPredictionForm
from signals.apps.llm_prediction.models import LlmPrediction


class LlmPredictionAdmin(admin.ModelAdmin):
    form = LlmPredictionForm
    list_display = ['signal_id', 'llm_predicted_category', 'tfidf_predicted_category', 'signal_text']
    readonly_fields = ['signal', 'signal_text', 'llm_predicted_category', 'tfidf_predicted_category']

    def signal_text(self, obj):
        return obj.signal.text

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(LlmPrediction, LlmPredictionAdmin)