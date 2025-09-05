# expenses/models.py
from django.conf import settings
from django.db import models

# ---------------- 기존 보고서 모델 ----------------
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


# ---------------- 새로 추가: 계약/이미지 모델 ----------------
class Contract(models.Model):
    STATUS_CHOICES = [
        ("draft", "임시저장"),
        ("submitted", "품의요청"),
        ("processing", "결재처리중"),
        ("completed", "결재완료"),
    ]

    title = models.CharField(max_length=200, default="무제 계약")
    writer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contracts_written")
    sales_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts_owned"
    )

    # 매출처
    customer_company = models.CharField(max_length=200, blank=True)
    customer_manager = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)

    # 배송
    ship_item = models.CharField(max_length=200, blank=True)
    ship_date = models.DateField(null=True, blank=True)
    ship_addr = models.CharField(max_length=300, blank=True)
    ship_phone = models.CharField(max_length=50, blank=True)

    # 회수/비고
    collect_invoice_date = models.DateField(null=True, blank=True)
    collect_date = models.DateField(null=True, blank=True)
    collect_note = models.CharField(max_length=500, blank=True)
    special_note = models.CharField(max_length=500, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title} (#{self.pk})"


class ContractImage(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="images")

    # 파일들 (원본/파생)
    original = models.ImageField(upload_to="contracts/orig/%Y/%m/%d/")
    thumb    = models.ImageField(upload_to="contracts/thumb/%Y/%m/%d/", blank=True)
    medium   = models.ImageField(upload_to="contracts/medium/%Y/%m/%d/", blank=True)

    # 메타정보
    filename = models.CharField(max_length=255, db_index=True, blank=True)
    width    = models.IntegerField(null=True, blank=True)
    height   = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=50, blank=True)

    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["contract", "uploaded_at"])]

    def __str__(self):
        return self.filename or self.original.name
    
class ContractItem(models.Model):
    VAT_CHOICES = [
        ("separate", "VAT별도"),
        ("included", "VAT포함"),
        ("exempt",   "면세"),
    ]

    contract   = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="items")
    name       = models.CharField(max_length=200)
    qty        = models.PositiveIntegerField(default=0)
    spec       = models.CharField(max_length=100, blank=True)
    sell_unit  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sell_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    buy_unit   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    buy_total  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vendor     = models.CharField(max_length=200, blank=True)
    vat_mode   = models.CharField(max_length=10, choices=VAT_CHOICES, default="separate")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} x{self.qty}"