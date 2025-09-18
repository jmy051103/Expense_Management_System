# partners/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .models import SalesPartner
from .forms import (
    SalesPartnerForm,
    SalesPartnerContactFormSetCreate,
    SalesPartnerContactFormSetEdit,
)
from .models import PurchasePartner
from .forms import (
    PurchasePartnerForm,
    PurchasePartnerContactFormSetCreate,
    PurchasePartnerContactFormSetEdit,
)
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def api_partner_detail(request, pk):
    p = SalesPartner.objects.filter(pk=pk).prefetch_related("contacts").first()
    if not p:
        return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({
        "id": p.id,
        "name": p.name or "",
        "biz_no": p.biz_no or "",
        "contacts": [
            {
                "id": c.id,
                "name": c.name or "",
                "department": c.department or "",
                "phone": c.phone or "",
                "extension": c.extension or "",
                "email": c.email or "",
            } for c in p.contacts.all().order_by("id")
        ]
    })

def partner_contacts_api(request, pk):
    partner = get_object_or_404(SalesPartner, pk=pk)
    contacts = [
        {
            "id": c.id,
            "name": c.name,
            "department": c.department or "",
            "phone": c.phone or "",
            "email": c.email or "",
            "display": f"{c.name} / {c.department}" if (c.department or "").strip() else c.name,
        }
        for c in partner.contacts.all().order_by("name")  
    ]
    return JsonResponse({"contacts": contacts})

def sales_partner_list(request):
    if request.method == "POST":
        ids = request.POST.getlist("ids")
        if ids:
            SalesPartner.objects.filter(id__in=ids).delete()
        return redirect("partners:sales_partner_list")

    qs = SalesPartner.objects.prefetch_related("contacts").order_by("-id")

    q_name = (request.GET.get("q_name") or "").strip()
    q_contact = (request.GET.get("q_contact") or "").strip()  # 폼에 있으니 함께 유지
    if q_name:
        qs = qs.filter(name__icontains=q_name)
    if q_contact:
        qs = qs.filter(contacts__name__icontains=q_contact).distinct()

    per_page_options = [10, 20, 30, 50, 100]
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    qs_keep = request.GET.copy()
    qs_keep.pop('page', None)
    qs_without_page = qs_keep.urlencode()
    is_popup = request.GET.get("popup") == "1" 

    return render(request, "sales_partner_list.html", {
        "page_obj": page_obj,
        "per_page_options": per_page_options,
        "per_page": per_page,
        "q_name": q_name,
        "q_contact": q_contact,
        "qs": qs_without_page,
        "is_popup": is_popup,
    })


def sales_partner_create(request):
    """매출처 등록 (담당자 1줄 기본 제공)"""
    if request.method == "POST":
        form = SalesPartnerForm(request.POST)
        # POST는 TOTAL_FORMS가 폼 데이터로 결정되므로 Create 폼셋 그대로 사용
        formset = SalesPartnerContactFormSetCreate(request.POST, prefix="contacts")
        if form.is_valid() and formset.is_valid():
            partner = form.save()
            formset.instance = partner
            formset.save()
            return redirect("partners:sales_partner_list")
    else:
        form = SalesPartnerForm()
        # GET: 등록 화면에서만 기본 1줄 노출 (extra=1)
        formset = SalesPartnerContactFormSetCreate(prefix="contacts")

    return render(request, "sales_partner_form.html", {
        "form": form,
        "formset": formset,
    })


def sales_partner_edit(request, pk):
    """매출처 수정 (자동 빈 줄 없음)"""
    partner = get_object_or_404(SalesPartner, pk=pk)

    if request.method == "POST":
        form = SalesPartnerForm(request.POST, instance=partner)
        formset = SalesPartnerContactFormSetEdit(
            request.POST, instance=partner, prefix="contacts"
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect("partners:sales_partner_list")
    else:
        form = SalesPartnerForm(instance=partner)
        formset = SalesPartnerContactFormSetEdit(instance=partner, prefix="contacts")

    return render(request, "sales_partner_form.html", {
        "form": form,
        "formset": formset,
        "partner": partner,
    })


def sales_partner_delete(request, pk):
    partner = get_object_or_404(SalesPartner, pk=pk)
    if request.method == "POST":
        partner.delete()
        return redirect("partners:sales_partner_list")
    return redirect("partners:sales_partner_list")


def purchase_partner_list(request):
    return render(request, "purchase_partner_list.html")

@login_required
def api_purchase_detail(request, pk):
    p = PurchasePartner.objects.filter(pk=pk).prefetch_related("contacts").first()
    if not p:
        return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse({
        "id": p.id,
        "name": p.name or "",
        "biz_no": p.biz_no or "",
        "contacts": [
            {
                "id": c.id,
                "name": c.name or "",
                "department": c.department or "",
                "phone": c.phone or "",
                "extension": c.extension or "",
                "email": c.email or "",
            } for c in p.contacts.all().order_by("id")
        ]
    })

def purchase_partner_contacts_api(request, pk):
    partner = get_object_or_404(PurchasePartner, pk=pk)
    contacts = [
        {
            "id": c.id,
            "name": c.name,
            "department": c.department or "",
            "phone": c.phone or "",
            "email": c.email or "",
            "display": f"{c.name} / {c.department}" if (c.department or "").strip() else c.name,
        }
        for c in partner.contacts.all().order_by("name")
    ]
    return JsonResponse({"contacts": contacts})

# ====== 매입처 목록/등록/수정/삭제 ======
def purchase_partner_list(request):
    if request.method == "POST":
        ids = request.POST.getlist("ids")
        if ids:
            PurchasePartner.objects.filter(id__in=ids).delete()
        return redirect("partners:purchase_partner_list")

    qs = PurchasePartner.objects.prefetch_related("contacts").order_by("-id")

    q_name = (request.GET.get("q_name") or "").strip()
    q_contact = (request.GET.get("q_contact") or "").strip()
    if q_name:
        qs = qs.filter(name__icontains=q_name)
    if q_contact:
        qs = qs.filter(contacts__name__icontains=q_contact).distinct()

    per_page_options = [10, 20, 30, 50, 100]
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    qs_keep = request.GET.copy()
    qs_keep.pop('page', None)
    qs_without_page = qs_keep.urlencode()
    is_popup = request.GET.get("popup") == "1"

    return render(request, "purchase_partner_list.html", {
        "page_obj": page_obj,
        "per_page_options": per_page_options,
        "per_page": per_page,
        "q_name": q_name,
        "q_contact": q_contact,
        "qs": qs_without_page,
        "is_popup": is_popup,
    })


def purchase_partner_create(request):
    if request.method == "POST":
        form = PurchasePartnerForm(request.POST)
        formset = PurchasePartnerContactFormSetCreate(request.POST, prefix="contacts")
        if form.is_valid() and formset.is_valid():
            partner = form.save()
            formset.instance = partner
            formset.save()
            return redirect("partners:purchase_partner_list")
    else:
        form = PurchasePartnerForm()
        formset = PurchasePartnerContactFormSetCreate(prefix="contacts")

    return render(request, "purchase_partner_form.html", {
        "form": form,
        "formset": formset,
    })


def purchase_partner_edit(request, pk):
    partner = get_object_or_404(PurchasePartner, pk=pk)

    if request.method == "POST":
        form = PurchasePartnerForm(request.POST, instance=partner)
        formset = PurchasePartnerContactFormSetEdit(
            request.POST, instance=partner, prefix="contacts"
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect("partners:purchase_partner_list")
    else:
        form = PurchasePartnerForm(instance=partner)
        formset = PurchasePartnerContactFormSetEdit(instance=partner, prefix="contacts")

    return render(request, "purchase_partner_form.html", {
        "form": form,
        "formset": formset,
        "partner": partner,
    })


def purchase_partner_delete(request, pk):
    partner = get_object_or_404(PurchasePartner, pk=pk)
    if request.method == "POST":
        partner.delete()
        return redirect("partners:purchase_partner_list")
    return redirect("partners:purchase_partner_list")