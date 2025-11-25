# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.
from signals.apps.llm_prediction.models import LlmPrediction
from signals.apps.llm_prediction.services.prediction import get_prediction, resolve_prediction
from signals.apps.signals.models import Signal
from signals.celery import app

@app.task()
def predict_signal(signal_id: int) -> None:
    """Task to predict signal category using LLM."""
    signal = Signal.objects.get(pk=signal_id)

    prediction = get_prediction(signal.text)

    main_slug, sub_slug = resolve_prediction(prediction)

    LlmPrediction.objects.create(
        llm_predicted_category=f"{main_slug} / {sub_slug}",
        tfidf_predicted_category=f"{signal.category_assignment.category.parent.slug} / {signal.category_assignment.category.slug}",
        signal=signal
    )

