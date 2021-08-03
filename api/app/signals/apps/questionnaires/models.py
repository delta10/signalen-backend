# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2021 Gemeente Amsterdam
import uuid
from datetime import timedelta

from django.contrib.gis.db import models
from django.utils import timezone

from signals.apps.questionnaires.app_settings import SESSION_DURATION
from signals.apps.questionnaires.fieldtypes import field_type_choices
from signals.apps.questionnaires.managers import (
    QuestionManager,
    QuestionnaireManager,
    SessionManager
)


class Questionnaire(models.Model):
    EXTRA_PROPERTIES = 'EXTRA_PROPERTIES'
    REACTION_REQUEST = 'REACTION_REQUEST'
    FEEDBACK_REQUEST = 'FEEDBACK_REQUEST'
    FLOW_CHOICES = (
        (EXTRA_PROPERTIES, 'Uitvraag'),
        (REACTION_REQUEST, 'Reactie gevraagd'),
        (FEEDBACK_REQUEST, 'Klanttevredenheidsonderzoek'),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(editable=False, auto_now_add=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True, help_text='Describe the Questionnaire')
    is_active = models.BooleanField(default=True)

    graph = models.ForeignKey(
        'QuestionGraph', on_delete=models.SET_NULL, related_name='questionnaire', null=True, blank=True)
    flow = models.CharField(max_length=255, choices=FLOW_CHOICES, default=EXTRA_PROPERTIES)

    objects = QuestionnaireManager()

    def __str__(self):
        return f'Questionnaire "{self.name or self.uuid}" ({"" if self.is_active else "not"} active)'

    @property
    def first_question(self):
        if self.graph:
            return self.graph.first_question
        return None


class Edge(models.Model):  # aka edge list / adjacency list
    graph = models.ForeignKey('QuestionGraph', on_delete=models.CASCADE, related_name='edges')

    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='+')
    next_question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='+')

    order = models.IntegerField(default=0)  # Default is order of creation, can be overridden.
    payload = models.JSONField(null=True, blank=True)  # <- validate using question field when saving

    class Meta:
        ordering = ['order', 'id']


class ActionTrigger(models.Model):
    REOPEN_SIGNAL = 'reopen signal'
    ACTION_CHOICES = [
        (REOPEN_SIGNAL, 'Melding heropenen'),
    ]

    graph = models.ForeignKey('QuestionGraph', on_delete=models.CASCADE, related_name='action_triggers')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='+')
    payload = models.JSONField(null=True, blank=True)  # <- validate using question field when saving

    order = models.IntegerField(default=0)  # Default is order of creation, can be overridden.

    action = models.CharField(max_length=255, choices=ACTION_CHOICES)
    arguments = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['order', 'id']


class InfoTrigger(models.Model):
    # We check whether information should be shown by checking for a match:
    graph = models.ForeignKey('QuestionGraph', on_delete=models.CASCADE, related_name='info_triggers')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='+')
    payload = models.JSONField(null=True, blank=True)  # <- validate using question field when saving

    # It is possible to define several
    order = models.IntegerField(default=0)  # Default is order of creation, can be overridden.

    title = models.CharField(max_length=255)
    information = models.TextField()  # TODO: allow markdown

    class Meta:
        ordering = ['order', 'id']


class QuestionGraph(models.Model):
    name = models.CharField(max_length=255, unique=True)
    first_question = models.ForeignKey('Question', blank=True, null=True, on_delete=models.SET_NULL, related_name='+')

    def _set_model_order(self, question, model, ids):
        all_ids = set(model.objects.filter(graph=self, question=question).values_list('id', flat=True))
        if set(ids) != all_ids and len(ids) == len(all_ids):
            msg = f'Cannot update {model.__name__} order, {model.__name__} instance ids are not correct.'
            raise Exception(msg)

        for i, id_ in enumerate(ids):
            instance = model.objects.get(id=id_)
            instance.order = i
            instance.save()

        return model.objects.filter(graph=self, question=question).values_list('id', flat=True)

    def get_edges(self, question):
        return Edge.objects.filter(graph=self, question=question)

    def get_edge_order(self, question):
        return Edge.objects.filter(graph=self, question=question).values_list('id', flat=True)

    def set_edge_order(self, question, ids):
        return self._set_model_order(question, Edge, ids)

    def get_info_triggers(self, question):
        return InfoTrigger.objects.filter(graph=self, question=question)

    def get_info_trigger_order(self, question):
        return InfoTrigger.objects.filter(graph=self, question=question).values_list('id', flat=True)

    def set_info_trigger_order(self, question, ids):
        return self._set_model_order(question, InfoTrigger, ids)

    def get_action_triggers(self, question):
        return ActionTrigger.objects.filter(graph=self, question=question)

    def get_action_trigger_order(self, question):
        return ActionTrigger.objects.filter(graph=self, question=question).values_list('id', flat=True)

    def set_action_trigger_order(self, question, ids):
        return self._set_model_order(question, ActionTrigger, ids)


class Choice(models.Model):
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='choices')
    payload = models.JSONField(blank=True, null=True)

    class Meta:
        order_with_respect_to = 'question'


class Question(models.Model):  # aka node
    key = models.CharField(unique=True, max_length=255, null=True, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    label = models.CharField(max_length=255)
    short_label = models.CharField(max_length=255)
    field_type = models.CharField(choices=field_type_choices(), max_length=255)
    required = models.BooleanField(default=False)
    enforce_choices = models.BooleanField(default=False)

    objects = QuestionManager()

    def __str__(self):
        return f'{self.key or self.uuid} ({self.field_type})'

    @property
    def ref(self):
        return self.key if self.key else str(self.uuid)


class Answer(models.Model):
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    session = models.ForeignKey('Session', on_delete=models.CASCADE, null=True, related_name='answers')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, null=True, related_name='+')

    payload = models.JSONField(blank=True, null=True)


class Session(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(editable=False, auto_now_add=True)

    started_at = models.DateTimeField(blank=True, null=True)
    submit_before = models.DateTimeField(blank=True, null=True)
    duration = models.DurationField(default=timedelta(seconds=SESSION_DURATION))

    questionnaire = models.ForeignKey('Questionnaire', on_delete=models.CASCADE, related_name='+')
    frozen = models.BooleanField(default=False)
    _signal = models.ForeignKey('signals.Signal', on_delete=models.CASCADE, null=True)

    objects = SessionManager()

    @property
    def is_expired(self):
        return (
            (self.submit_before and self.submit_before < timezone.now()) or
            (self.started_at and self.started_at + self.duration < timezone.now())
        )

    @property
    def too_late(self):
        return not self.frozen or self.is_expired
