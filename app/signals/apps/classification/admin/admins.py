from django.contrib import admin, messages
from signals.apps.classification.tasks import run_training_task
import openpyxl


class TrainingSetAdmin(admin.ModelAdmin):
    list_display = ('name', 'file', )
    actions = ["run_training_with_training_set"]

    @admin.action(description="Train model met geselecteerde dataset")
    def run_training_with_training_set(self, request, queryset):
        """
        Run validation, if validation fails show an error message.

        First we validate if there are no missing columns (Main, Sub and Text column are required), after this we check if there is atleast one row of data (next
        to the headers)
        """
        for training_set in queryset:
            file = training_set.file

            wb = openpyxl.load_workbook(file)
            first_sheet = wb.active

            headers = [cell.value for cell in first_sheet[1]]
            required_columns = ["Main", "Sub", "Text"]
            missing_columns = [col for col in required_columns if col not in headers]

            if missing_columns:
                self.message_user(
                    request,
                    f"Training set { training_set.name } is missing required columns: {', '.join(missing_columns)}",
                    messages.ERROR,
                )

                return

            data_rows = list(first_sheet.iter_rows(min_row=2, values_only=True))
            if not any(data_rows):
                self.message_user(
                    request,
                    f"The training set { training_set.name } does not contain any data rows.",
                    messages.ERROR
                    )
                return

            # TODO: run actual training task
            run_training_task.delay()

            self.message_user(
                request,
                "Training of the model has been initiated.",
                messages.SUCCESS,
            )


class ClassifierAdmin(admin.ModelAdmin):
    """
    Creating or disabling classifiers by hand in the Admin interface is disabled,

    a successful training job should create his own classifier object.
    """
    list_display = ('name',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [f.name for f in self.model._meta.fields]
        return []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
