from django import forms
from django.forms import inlineformset_factory
from .models import SalesPartner, SalesPartnerContact, PurchasePartner, PurchasePartnerContact


class SalesPartnerForm(forms.ModelForm):
    class Meta:
        model = SalesPartner
        fields = ["name", "biz_no", "fax", "address", "email"] 
        widgets = {
            "name": forms.TextInput(attrs={"class": "inp", "placeholder": "매출처명"}),
            "biz_no": forms.TextInput(attrs={"class": "inp", "placeholder": "사업자번호"}),
            "fax": forms.TextInput(attrs={"class": "inp", "placeholder": "팩스번호"}),
            "address": forms.TextInput(attrs={"class": "inp", "placeholder": "주소"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "대표 이메일"}),
        }



class SalesPartnerContactForm(forms.ModelForm):
    class Meta:
        model = SalesPartnerContact
        fields = ["name", "department", "phone", "extension", "email"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "inp", "placeholder": "담당자명"}),
            "department": forms.TextInput(attrs={"class": "inp", "placeholder": "부서"}),
            "phone": forms.TextInput(attrs={"class": "inp", "placeholder": "연락처"}),
            "extension": forms.TextInput(attrs={"class": "inp", "placeholder": "내선"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "이메일"}),
        }


SalesPartnerContactFormSetCreate = inlineformset_factory(
    SalesPartner,
    SalesPartnerContact,
    form=SalesPartnerContactForm,
    extra=1,
    can_delete=True,
)

# ✅ 수정 화면용: 추가 빈 줄 없음
SalesPartnerContactFormSetEdit = inlineformset_factory(
    SalesPartner,
    SalesPartnerContact,
    form=SalesPartnerContactForm,
    extra=0,
    can_delete=True,
)

class PurchasePartnerForm(forms.ModelForm):
    class Meta:
        model = PurchasePartner
        fields = ["name", "biz_no", "fax", "address", "email"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "inp", "placeholder": "매입처명"}),
            "biz_no": forms.TextInput(attrs={"class": "inp", "placeholder": "사업자번호"}),
            "fax": forms.TextInput(attrs={"class": "inp", "placeholder": "팩스번호"}),
            "address": forms.TextInput(attrs={"class": "inp", "placeholder": "주소"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "대표 이메일"}),
        }

class PurchasePartnerContactForm(forms.ModelForm):
    class Meta:
        model = PurchasePartnerContact
        fields = ["name", "department", "phone", "extension", "email"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "inp", "placeholder": "담당자명"}),
            "department": forms.TextInput(attrs={"class": "inp", "placeholder": "부서"}),
            "phone": forms.TextInput(attrs={"class": "inp", "placeholder": "연락처"}),
            "extension": forms.TextInput(attrs={"class": "inp", "placeholder": "내선"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "이메일"}),
        }

PurchasePartnerContactFormSetCreate = inlineformset_factory(
    PurchasePartner, PurchasePartnerContact,
    form=PurchasePartnerContactForm,
    extra=1, can_delete=True,
)

PurchasePartnerContactFormSetEdit = inlineformset_factory(
    PurchasePartner, PurchasePartnerContact,
    form=PurchasePartnerContactForm,
    extra=0, can_delete=True,
)