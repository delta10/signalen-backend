# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2021 - 2022 Gemeente Amsterdam
import logging
from abc import ABC

from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template, loader

from signals.apps.email_integrations.models import EmailTemplate
from signals.apps.email_integrations.utils import make_email_context
from signals.apps.signals.models import Signal

logger = logging.getLogger(__name__)


class AbstractAction(ABC):
    """
    This class is used to define email action's.

    The derived class action must implement a custom Rule. For example the SignalCreatedAction uses the
    SignalCreatedRule to determine if it should trigger and send the Signal created email.
    """

    # A rule class based on the AbstractRule
    rule = None

    # The key of the email template. Is used to retrieve the corresponding EmailTemplate from the database
    # If there is no EmailTemplate with this key a fallback email template is used.
    # The fallback email templates:
    # - email/signal_default.txt
    # - email/signal_default.html)
    key = None

    # The subject of the email
    subject = None
    from_email = settings.DEFAULT_FROM_EMAIL

    # Will be used to create a note on the Signal after the email has been sent
    note = None

    def __call__(self, signal, dry_run=False):
        if self.rule(signal):
            if dry_run:
                return True

            if self.send_mail(signal):
                self.add_note(signal)
                return True

        return False

    def get_additional_context(self, signal):
        """
        Overwrite this function if additional email context is needed.
        """
        return {}

    def get_context(self, signal):
        """
        Email context
        """
        context = make_email_context(signal, self.get_additional_context(signal))
        return context

    def render_mail_data(self, context):
        """
        Renders the subject, text message body and html message body
        """
        try:
            email_template = EmailTemplate.objects.get(key=self.key)

            rendered_context = {
                'subject': Template(email_template.title).render(Context(context)),
                'body': Template(email_template.body).render(Context(context, autoescape=False))
            }

            subject = Template(email_template.title).render(Context(context, autoescape=False))
            message = loader.get_template('email/_base.txt').render(rendered_context)
            html_message = loader.get_template('email/_base.html').render(rendered_context)
        except EmailTemplate.DoesNotExist:
            logger.warning(f'EmailTemplate {self.key} does not exists')

            subject = self.subject.format(signal_id=context['signal_id'])
            message = loader.get_template('email/signal_default.txt').render(context)
            html_message = loader.get_template('email/signal_default.html').render(context)

        return subject, message, html_message

    def send_mail(self, signal):
        """
        Send the email to the reporter
        """
        context = self.get_context(signal)
        subject, message, html_message = self.render_mail_data(context)
        return send_mail(subject=subject, message=message, from_email=self.from_email,
                         recipient_list=[signal.reporter.email, ], html_message=html_message)

    def add_note(self, signal):
        if self.note:
            Signal.actions.create_note({'text': self.note}, signal=signal)
