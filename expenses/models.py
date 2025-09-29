# expenses/models.py
from django.conf import settings
from django.db import models
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone

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
        ("submitted", "결재요청"),
        ("processing", "결재처리중"),
        ("completed", "결재완료"),
    ]

    title = models.CharField(max_length=200, default="무제 계약")
    writer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contracts_written")
    sales_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="contracts_owned")

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
    collect_note = models.CharField(max_length=999999, blank=True)
    special_note = models.CharField(max_length=999999, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ 처음엔 null 허용으로 추가 (마이그레이션/백필 후 원하면 null=False로 변경)
    contract_no = models.CharField(max_length=32, unique=True, blank=True, null=True)
    year = models.PositiveIntegerField(editable=False, db_index=True, null=True, blank=True)
    seq  = models.PositiveIntegerField(editable=False, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['year', 'seq'], name='uniq_contract_year_seq'),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and not self.contract_no:
            y = timezone.localdate().year
            self.year = y
            with transaction.atomic():
                last_seq = (
                    Contract.objects
                    .filter(year=y)
                    .select_for_update()
                    .order_by('-seq')
                    .values_list('seq', flat=True)
                    .first() or 0
                )
                self.seq = last_seq + 1
                self.contract_no = f"{y}DJ{self.seq}"
        super().save(*args, **kwargs)

    @property
    def margin_month(self):
        """세금계산서 발행일 기준 YYYY-MM 문자열 반환"""
        if self.collect_invoice_date:
            return self.collect_invoice_date.strftime("%Y-%m")
        return None
        
    
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

    contract   = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    name       = models.CharField(max_length=200)
    qty        = models.PositiveIntegerField(default=0)
    spec       = models.CharField(max_length=100, blank=True)
    sell_unit  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sell_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    buy_unit   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    buy_total  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    vendor     = models.CharField(max_length=200, blank=True)
    vat_mode   = models.CharField(max_length=10, choices=VAT_CHOICES, default="separate")

    def margin_month(self):
        """세금계산서 발행일 기준 YYYY-MM 문자열 반환"""
        if self.collect_invoice_date:
            return self.collect_invoice_date.strftime("%Y-%m")
        return None

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} x{self.qty}"