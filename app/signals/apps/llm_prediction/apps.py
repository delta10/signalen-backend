# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.

from django.apps import AppConfig


class LlmPredictionConfig(AppConfig):
    name = 'signals.apps.llm_prediction'
    verbose_name = 'LLM Prediction'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signal_receivers  # noqa
