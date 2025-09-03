from django import forms
from django.forms import inlineformset_factory
from .models import ExpenseReport, ExpenseItem, Contract

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

class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            "sales_owner", "customer_company", "customer_manager",
            "customer_phone", "customer_email",
            "ship_item", "ship_date", "ship_addr", "ship_phone",
            "collect_invoice_date", "collect_date", "collect_note",
            "special_note",
        ]
        widgets = {
            "ship_date": forms.DateInput(attrs={"type": "date"}),
            "collect_invoice_date": forms.DateInput(attrs={"type": "date"}),
            "collect_date": forms.DateInput(attrs={"type": "date"}),
        }

    # 선택 필드들은 빈값을 None 처리 (FK/Date에 "" 들어가는 걸 방지)
    def clean_sales_owner(self):
        v = self.cleaned_data.get("sales_owner")
        return v or None

    def clean_ship_date(self):
        v = self.cleaned_data.get("ship_date")
        return v or None

    def clean_collect_invoice_date(self):
        v = self.cleaned_data.get("collect_invoice_date")
        return v or None

    def clean_collect_date(self):
        v = self.cleaned_data.get("collect_date")
        return v or None

    def clean(self):
        cd = super().clean()
        # 최소 필수값 체크
        if not cd.get("customer_company"):
            self.add_error("customer_company", "회사명은 필수입니다.")
        return cd