from django.db import models

class SalesPartner(models.Model):
    name = models.CharField("매출처명", max_length=200)
    biz_no = models.CharField("사업자번호", max_length=50, blank=True)
    fax = models.CharField("팩스번호", max_length=50, blank=True)
    address = models.CharField("주소", max_length=300, blank=True)
    email = models.EmailField("대표 이메일", blank=True)

    class Meta:
        db_table = "partners_salespartner"
        verbose_name = "매출처"
        verbose_name_plural = "매출처 목록"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.name} ({self.biz_no})" if self.biz_no else self.name


class SalesPartnerContact(models.Model):
    partner = models.ForeignKey(
        SalesPartner,
        related_name="contacts",
        on_delete=models.CASCADE,
    )
    name = models.CharField("담당자명", max_length=100)
    department = models.CharField("부서", max_length=100, blank=True)
    phone = models.CharField("연락처", max_length=50, blank=True)
    extension = models.CharField("내선", max_length=20, blank=True)
    email = models.EmailField("이메일", blank=True)

    class Meta:
        db_table = "partners_salespartner_contact"
        verbose_name = "매출처 담당자"
        verbose_name_plural = "매출처 담당자 목록"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} - {self.partner.name}"