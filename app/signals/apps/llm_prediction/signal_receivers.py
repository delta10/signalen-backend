# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from signals.apps.signals.managers import create_initial
from signals.apps.signals.models import Category
from signals import settings

from . import tasks
from .services.prediction import get_system_prompt


@receiver(create_initial, dispatch_uid='get_llm_prediction')
def create_initial_handler(sender, signal_obj, *args, **kwargs):
    if settings.LLM_BACKGROUND_PREDICTION_ENABLED:
        tasks.predict_signal.delay(signal_id=signal_obj.pk)


@receiver(post_save, sender=Category, dispatch_uid='clear_llm_prompt_cache_on_category_save')
@receiver(post_delete, sender=Category, dispatch_uid='clear_llm_prompt_cache_on_category_delete')
def clear_system_prompt_cache(sender, **kwargs):
    """Clear the cached LLM system prompt when categories are modified."""
    get_system_prompt.cache_clear()