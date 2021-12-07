# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2021 Gemeente Amsterdam
from datapunt_api.rest import DisplayField, HALSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from signals.apps.questionnaires.models import Answer, Edge, Question, Questionnaire, Session
from signals.apps.questionnaires.rest_framework.fields import (
    EmptyHyperlinkedIdentityField,
    QuestionHyperlinkedIdentityField,
    QuestionnairePublicHyperlinkedIdentityField,
    SessionPublicHyperlinkedIdentityField,
    UUIDRelatedField
)
from signals.apps.questionnaires.services.utils import get_session_service


class PublicQuestionSerializer(HALSerializer):
    serializer_url_field = QuestionHyperlinkedIdentityField
    next_rules = serializers.SerializerMethodField()
    _display = DisplayField()
    key = serializers.CharField(source='retrieval_key')

    class Meta:
        model = Question
        fields = (
            '_links',
            '_display',
            'key',
            'retrieval_key',
            'analysis_key',
            'uuid',
            'label',
            'short_label',
            'field_type',
            'next_rules',
            'required',
        )
        read_only_fields = fields  # No create or update allowed

    def get_next_rules(self, obj):
        # For backwards compatibility with earlier REST API version, this is
        # candidate for removal. This also only makes sense for questions seen
        # as part of a QuestionGraph, as the next_rules are no longer on the
        # Question object --- graph structure is now explicitly modelled in the
        # QuestionGraph and Edge objects.
        next_rules = None
        if graph := self.context.get('graph', None):
            outgoing_edges = Edge.objects.filter(graph=graph, question=obj)

            next_rules = []
            for edge in outgoing_edges:
                payload = edge.choice.payload if edge.choice else None
                next_rules.append({'key': edge.next_question.ref, 'payload': payload})

        return next_rules


class PublicQuestionDetailedSerializer(PublicQuestionSerializer):
    pass


class PublicQuestionnaireSerializer(HALSerializer):
    serializer_url_field = QuestionnairePublicHyperlinkedIdentityField

    _display = DisplayField()
    first_question = PublicQuestionSerializer()

    class Meta:
        model = Questionnaire
        fields = (
            '_links',
            '_display',
            'uuid',
            'name',
            'description',
            'is_active',
            'first_question'
        )
        read_only_fields = fields  # No create or update allowed


class PublicQuestionnaireDetailedSerializer(PublicQuestionnaireSerializer):
    first_question = PublicQuestionDetailedSerializer()


class PublicSessionSerializer(HALSerializer):
    serializer_url_field = SessionPublicHyperlinkedIdentityField

    _display = DisplayField()

    can_freeze = serializers.SerializerMethodField()
    path_questions = serializers.SerializerMethodField()
    path_answered_question_uuids = serializers.SerializerMethodField()
    path_unanswered_question_uuids = serializers.SerializerMethodField()
    path_validation_errors_by_uuid = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = (
            '_links',
            '_display',
            'uuid',
            'started_at',
            'submit_before',
            'duration',
            'created_at',
            # generated using the SessionService in serializer context:
            'can_freeze',
            'path_questions',
            'path_answered_question_uuids',
            'path_unanswered_question_uuids',
            'path_validation_errors_by_uuid'
            )
        read_only_fields = (
            'id',
            'uuid',
            'created_at',
            # generated using the SessionService in serializer context:
            'can_freeze',
            'path_questions',
            'path_path_answered_question_uuids',
            'path_unanswered_question_uuids',
            'path_validation_errors_by_uuid'
        )

    def get_can_freeze(self, obj):
        session_service = self.context.get('session_service')
        return session_service.can_freeze

    def get_path_questions(self, obj):
        session_service = self.context.get('session_service')
        serializer = PublicQuestionSerializer(session_service.path_questions, many=True, context=self.context)
        return serializer.data

    def get_path_answered_question_uuids(self, obj):
        session_service = self.context.get('session_service')
        return session_service.path_answered_question_uuids

    def get_path_unanswered_question_uuids(self, obj):
        session_service = self.context.get('session_service')
        return session_service.path_unanswered_question_uuids

    def get_path_validation_errors_by_uuid(self, obj):
        session_service = self.context.get('session_service')
        # Possibly turn all UUIDs into str(UUID)s in SessionService.
        return {str(k): v for k, v in session_service.path_validation_errors_by_uuid.items()}


class PublicSessionDetailedSerializer(PublicSessionSerializer):
    pass


class PublicAnswerSerializer(HALSerializer):
    serializer_url_field = EmptyHyperlinkedIdentityField

    _display = DisplayField()

    session = UUIDRelatedField(uuid_field='uuid', queryset=Session.objects.retrieve_valid_sessions(), required=False)
    questionnaire = UUIDRelatedField(uuid_field='uuid', queryset=Questionnaire.objects.active(), required=False)

    class Meta:
        model = Answer
        fields = (
            '_links',
            '_display',
            'payload',
            'session',
            'questionnaire',
            'created_at',
        )
        read_only_fields = (
            'created_at',
        )

    def validate(self, attrs):
        attrs = super(PublicAnswerSerializer, self).validate(attrs=attrs)

        if 'session' in attrs and 'questionnaire' in attrs:
            raise ValidationError('session and questionnaire cannot be used both!')
        elif 'session' not in attrs and 'questionnaire' not in attrs:
            raise ValidationError('Either the session or questionnaire is mandatory!')

        return attrs

    def create(self, validated_data):
        question = self.context['question']
        payload = validated_data.pop('payload')

        if 'session' in validated_data:
            session = validated_data.pop('session')
            session_service = get_session_service(session)
        else:
            questionnaire = validated_data.pop('questionnaire')
            session = Session.objects.create(questionnaire=questionnaire)
            session_service = get_session_service(session)

        session_service.refresh_from_db()
        return session_service.create_answer(payload, question)


class PublicSessionAnswerSerializer(serializers.Serializer):
    question_uuid = serializers.UUIDField()
    payload = serializers.JSONField()

    class Meta:
        fields = (
            'question_uuid',
            'payload',
        )
        read_only_fields = (
            'created_at',
        )