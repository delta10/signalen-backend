from datetime import datetime

from django.test import TestCase
from django.utils.timezone import get_default_timezone
from freezegun import freeze_time

from signals.apps.services.domain.deadlines import DeadlineCalculationService
from signals.apps.signals.factories import (
    CategoryAssignmentFactory,
    CategoryFactory,
    ServiceLevelObjectiveFactory,
    SignalFactory
)

FULL_TEST_CASES = [
    # Columns below: created_at, n_days, use_calendar_days, factor, deadline
    # One working day throughout week
    (datetime(2021, 2, 15, 12, 0, 0), 1, False, 1, datetime(2021, 2, 16, 12, 0, 0)),  # Monday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 16, 12, 0, 0), 1, False, 1, datetime(2021, 2, 17, 12, 0, 0)),  # Tuesday 12:00 -> Wednesday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 1, False, 1, datetime(2021, 2, 22, 12, 0, 0)),  # Friday 12:00 -> Monday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 1, False, 1, datetime(2021, 2, 23, 0, 0, 0)),  # Saturday 12:00 -> Tuesday 00:00
    (datetime(2021, 2, 21, 12, 0, 0), 1, False, 1, datetime(2021, 2, 23, 0, 0, 0)),  # Sunday 12:00 -> Tuesday 00:00

    # One working day throughout week, factor 3
    (datetime(2021, 2, 15, 12, 0, 0), 1, False, 3, datetime(2021, 2, 18, 12, 0, 0)),  # Monday 12:00 -> Thursday 12:00
    (datetime(2021, 2, 16, 12, 0, 0), 1, False, 3, datetime(2021, 2, 19, 12, 0, 0)),  # Tuesday 12:00 -> Friday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 1, False, 3, datetime(2021, 2, 24, 12, 0, 0)),  # Friday 12:00 -> Wednesday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 1, False, 3, datetime(2021, 2, 25, 0, 0, 0)),  # Saturday 12:00 -> Thursday 00:00
    (datetime(2021, 2, 21, 12, 0, 0), 1, False, 3, datetime(2021, 2, 25, 0, 0, 0)),  # Sunday 12:00 -> Thursday 00:00

    # One calendar day throughout the week
    (datetime(2021, 2, 15, 12, 0, 0), 1, True, 1, datetime(2021, 2, 16, 12, 0, 0)),  # Monday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 16, 12, 0, 0), 1, True, 1, datetime(2021, 2, 17, 12, 0, 0)),  # Tuesday 12:00 -> Wednesday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 1, True, 1, datetime(2021, 2, 20, 12, 0, 0)),  # Friday 12:00 -> Monday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 1, True, 1, datetime(2021, 2, 21, 12, 0, 0)),  # Saturday 12:00 -> Saturday 12:00
    (datetime(2021, 2, 21, 12, 0, 0), 1, True, 1, datetime(2021, 2, 22, 12, 0, 0)),  # Sunday 12:00 -> Monday 12:00

    # One calendar day throughout the week, factor 3
    (datetime(2021, 2, 15, 12, 0, 0), 1, True, 3, datetime(2021, 2, 18, 12, 0, 0)),  # Monday 12:00 -> Thursday 12:00
    (datetime(2021, 2, 16, 12, 0, 0), 1, True, 3, datetime(2021, 2, 19, 12, 0, 0)),  # Tuesday 12:00 -> Friday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 1, True, 3, datetime(2021, 2, 22, 12, 0, 0)),  # Friday 12:00 -> Monday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 1, True, 3, datetime(2021, 2, 23, 12, 0, 0)),  # Saturday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 21, 12, 0, 0), 1, True, 3, datetime(2021, 2, 24, 12, 0, 0)),  # Sunday 12:00 -> Wednesday 12:00

    # Two working days throughout week
    (datetime(2021, 2, 15, 12, 0, 0), 2, False, 1, datetime(2021, 2, 17, 12, 0, 0)),  # Monday 12:00 -> Wednesday 12:00
    (datetime(2021, 2, 18, 12, 0, 0), 2, False, 1, datetime(2021, 2, 22, 12, 0, 0)),  # Thursday 12:00 -> Monday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 2, False, 1, datetime(2021, 2, 23, 12, 0, 0)),  # Friday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 2, False, 1, datetime(2021, 2, 24, 0, 0, 0)),  # Saturday 12:00 -> Wednesday 00:00

    # Three working days throughout week
    (datetime(2021, 2, 15, 12, 0, 0), 3, False, 1, datetime(2021, 2, 18, 12, 0, 0)),  # Monday 12:00 -> Thursday 12:00
    (datetime(2021, 2, 18, 12, 0, 0), 3, False, 1, datetime(2021, 2, 23, 12, 0, 0)),  # Thursday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 3, False, 1, datetime(2021, 2, 24, 12, 0, 0)),  # Friday 12:00 -> Wednesday 12:00
    (datetime(2021, 2, 20, 12, 0, 0), 3, False, 1, datetime(2021, 2, 25, 0, 0, 0)),  # Saturday 12:00 -> Thursday 00:00
    (datetime(2021, 2, 21, 12, 0, 0), 3, False, 1, datetime(2021, 2, 25, 0, 0, 0)),  # Sunday 12:00 -> Thursday 00:00

    # Ten working days
    (datetime(2021, 2, 15, 12, 0, 0), 10, False, 1, datetime(2021, 3, 1, 12, 0, 0)),  # Monday 12:00 -> Monday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 10, False, 1, datetime(2021, 3, 5, 12, 0, 0)),  # Friday 12:00 -> Friday 12:00

    # Eleven working days
    (datetime(2021, 2, 15, 12, 0, 0), 11, False, 1, datetime(2021, 3, 2, 12, 0, 0)),  # Monday 12:00 -> Tuesday 12:00
    (datetime(2021, 2, 19, 12, 0, 0), 11, False, 1, datetime(2021, 3, 8, 12, 0, 0)),  # Friday 12:00 -> Monday 12:00
]


class TestDeadlineCalculationService(TestCase):
    def test_get_start(self):
        """
        Test start of work period for ServiceLevelObjectives in working days.
        """
        TEST_CASES = [
            (datetime(2021, 2, 15, 12, 0, 0), datetime(2021, 2, 15, 12, 0, 0)),  # Monday 12:00 -> Monday 12:00
            (datetime(2021, 2, 16, 12, 0, 0), datetime(2021, 2, 16, 12, 0, 0)),  # Tuesday 12:00 -> Tuesday 12:00
            (datetime(2021, 2, 20, 12, 0, 0), datetime(2021, 2, 22, 0, 0, 0)),  # Saturday 12:00 -> Monday 00:00
            (datetime(2021, 2, 21, 12, 0, 0), datetime(2021, 2, 22, 0, 0, 0)),  # Sunday 12:00 -> Monday 00:00
        ]
        for created_at, start in TEST_CASES:
            calculated_start = DeadlineCalculationService.get_start(created_at)
            self.assertEqual(calculated_start, start)

    def test_get_end(self):
        """
        Test end of work period for ServiceLevelObjectives in working days.
        """
        # We do not test weekends here (get_end is only called with weekdays)
        TEST_CASES = [
            # Columns below: created_at, n_days, factor, deadline
            (datetime(2021, 2, 15, 12, 0, 0), 1, 1, datetime(2021, 2, 16, 12, 0, 0)),  # Monday 12:00 -> Tuesday 12:00
            (datetime(2021, 2, 19, 12, 0, 0), 1, 1, datetime(2021, 2, 22, 12, 0, 0)),  # Friday 12:00 -> Monday 12:00
            (datetime(2021, 2, 22, 0, 0, 0), 1, 1, datetime(2021, 2, 23, 0, 0, 0)),  # Monday 00:00 -> Tuesday 00:00
        ]
        for start, n_days, factor, end in TEST_CASES:
            calculated_end = DeadlineCalculationService.get_end(start, n_days, factor)
            self.assertEqual(calculated_end, end)

    def test_get_deadline(self):
        """
        Test full deadline calculation for a suite of start and end times.

        Note:
        - this tests both ServiceLevelObjectives given in calendar days and
          those given in working days.
        """
        # Go through testcases check that we get the correct answers.
        for created_at, n_days, use_calendar_days, factor, deadline in FULL_TEST_CASES:
            calculated_deadline = DeadlineCalculationService.get_deadline(
                created_at, n_days, use_calendar_days, factor)
            self.assertEqual(calculated_deadline, deadline)

    def test_from_signal_and_category(self):
        """
        Call into the deadline calculation service using Django ORM objects.
        """
        tzinfo = get_default_timezone()
        start = datetime(2021, 2, 19, 12, 0, 0, tzinfo=tzinfo)
        true_deadline = datetime(2021, 2, 22, 12, 0, 0, tzinfo=tzinfo)
        true_deadline_factor_3 = datetime(2021, 2, 24, 12, 0, 0, tzinfo=tzinfo)

        cat = CategoryFactory.create()
        ServiceLevelObjectiveFactory.create(n_days=1, use_calendar_days=False, category=cat)

        with freeze_time(start):
            signal = SignalFactory(category_assignment__category=cat)

        deadline, deadline_factor_3 = DeadlineCalculationService.from_signal_and_category(signal, cat)
        self.assertEqual(deadline, true_deadline)
        self.assertEqual(deadline_factor_3, true_deadline_factor_3)

    def test_category_assignment_model(self):
        """
        CategoryAssignmentFactory.save() calls the deadline calculations, check that mechanism here.
        """
        tzinfo = get_default_timezone()
        start = datetime(2021, 2, 19, 12, 0, 0, tzinfo=tzinfo)
        true_deadline = datetime(2021, 2, 22, 12, 0, 0, tzinfo=tzinfo)
        true_deadline_factor_3 = datetime(2021, 2, 24, 12, 0, 0, tzinfo=tzinfo)

        cat = CategoryFactory.create()
        ServiceLevelObjectiveFactory.create(n_days=1, use_calendar_days=False, category=cat)

        with freeze_time(start):
            cas = CategoryAssignmentFactory(category=cat)

        self.assertEqual(cas._signal.created_at, start)
        self.assertEqual(cas.deadline, true_deadline)
        self.assertEqual(cas.deadline_factor_3, true_deadline_factor_3)
