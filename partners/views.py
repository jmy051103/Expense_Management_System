# partners/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import SalesPartner
from .forms import SalesPartnerForm, SalesPartnerContactFormSet
from django.core.paginator import Paginator

def sales_partner_list(request):
    if request.method == "POST":
        ids = request.POST.getlist("ids") 
        if ids:
            SalesPartner.objects.filter(id__in=ids).delete()
        return redirect("sales_partner_list")


    qs = SalesPartner.objects.all().order_by("-id")

    q_name = (request.GET.get("q_name") or "").strip()
    if q_name:
        qs = qs.filter(name__icontains=q_name)

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

    return render(request, "sales_partner_list.html", {
        "page_obj": page_obj,
        "per_page_options": per_page_options,
    })


def sales_partner_create(request):
    """매출처 등록"""
    if request.method == "POST":
        form = SalesPartnerForm(request.POST)
        formset = SalesPartnerContactFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            partner = form.save()
            formset.instance = partner
            formset.save()
            return redirect("sales_partner_list")
    else:
        form = SalesPartnerForm()
        formset = SalesPartnerContactFormSet()

    return render(request, "sales_partner_form.html", {
        "form": form,
        "formset": formset,
    })
4

def sales_partner_edit(request, pk):
    """매출처 수정"""
    partner = get_object_or_404(SalesPartner, pk=pk)
    if request.method == "POST":
        form = SalesPartnerForm(request.POST, instance=partner)
        formset = SalesPartnerContactFormSet(request.POST, instance=partner)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect("sales_partner_list")
    else:
        form = SalesPartnerForm(instance=partner)
        formset = SalesPartnerContactFormSet(instance=partner)

    return render(request, "sales_partner_form.html", {
        "form": form,
        "formset": formset,
        "partner": partner,
    })


def sales_partner_delete(request, pk):
    """매출처 삭제"""
    partner = get_object_or_404(SalesPartner, pk=pk)
    if request.method == "POST":
        partner.delete()
        return redirect("sales_partner_list")
    return redirect("sales_partner_list")


def purchase_partner_list(request):
    """매입처 목록 (추후 구현)"""
    return render(request, "purchase_partner_list.html")