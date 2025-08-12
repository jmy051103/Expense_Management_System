from django import forms
from django.forms import inlineformset_factory
from .models import ExpenseReport, ExpenseItem

class ExpenseReportForm(forms.ModelForm):
    class Meta:
        model = ExpenseReport
        fields = ["company", "contact_phone", "email", "handler", "vat_rate", "notes"]

ExpenseItemFormSet = inlineformset_factory(
    ExpenseReport,
    ExpenseItem,
    fields=["product", "quantity", "unit_price"],
    extra=1,
    can_delete=True,
)
