from django.conf import settings
from django.db import models

class ExpenseReport(models.Model):
    VAT_CHOICES = [(0, "0%"), (10, "10%")]

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expense_reports")
    company = models.CharField(max_length=100)
    contact_phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    handler = models.CharField(max_length=50, blank=True)  # 담당자
    vat_rate = models.IntegerField(choices=VAT_CHOICES, default=10)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def vat_amount(self):
        return int(self.subtotal * (self.vat_rate / 100))

    @property
    def grand_total(self):
        return self.subtotal + self.vat_amount

    def __str__(self):
        return f"[{self.id}] {self.company} by {self.creator}"
    

class ExpenseItem(models.Model):
    report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name="items")
    product = models.CharField("품목", max_length=100)
    quantity = models.PositiveIntegerField("수량", default=1)
    unit_price = models.PositiveIntegerField("매입단가", default=0)  # 원 단위

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product} x {self.quantity}"
