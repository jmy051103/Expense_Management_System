# expenses/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction

from .forms import ExpenseReportForm, ExpenseItemFormSet
from .models import ExpenseReport


def _is_approver(user) -> bool:
    """approver 그룹 또는 superuser라면 True"""
    return user.is_superuser or user.groups.filter(name="approver").exists()


@login_required
def report_list(request):
    """누가 작성했든 전부 보이기"""
    reports = (
        ExpenseReport.objects
        .select_related("creator")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    can_delete = _is_approver(request.user)
    return render(request, "expenses/report_list.html", {
        "reports": reports,
        "can_delete": can_delete,
    })


@login_required
def report_create(request):
    if request.method == "POST":
        form = ExpenseReportForm(request.POST)
        formset = ExpenseItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                report = form.save(commit=False)
                report.creator = request.user
                report.save()
                formset.instance = report
                formset.save()
            return redirect(reverse("report_detail", args=[report.id]))
    else:
        form = ExpenseReportForm()
        formset = ExpenseItemFormSet()

    return render(
        request,
        "expenses/report_form.html",
        {"form": form, "formset": formset, "is_edit": False},
    )


@login_required
def report_edit(request, pk):
    """
    모든 로그인 사용자가 수정 가능.
    (주의: 실제 서비스에서는 권한 정책에 맞춰 제한 권장)
    """
    report = get_object_or_404(ExpenseReport, pk=pk)

    if request.method == "POST":
        form = ExpenseReportForm(request.POST, instance=report)
        formset = ExpenseItemFormSet(request.POST, instance=report)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            return redirect(reverse("report_detail", args=[report.id]))
    else:
        form = ExpenseReportForm(instance=report)
        formset = ExpenseItemFormSet(instance=report)

    return render(
        request,
        "expenses/report_form.html",
        {"form": form, "formset": formset, "is_edit": True, "report": report},
    )


@login_required
def report_detail(request, pk):
    """누구나 상세 열람 가능"""
    report = get_object_or_404(
        ExpenseReport.objects.select_related("creator").prefetch_related("items"),
        pk=pk,
    )
    can_delete = _is_approver(request.user)
    return render(request, "expenses/report_detail.html", {
        "report": report,
        "can_delete": can_delete,
    })


@login_required
@require_POST
def report_delete(request, pk):
    """approver(또는 superuser)만 삭제 가능"""
    if not _is_approver(request.user):
        raise PermissionDenied("You do not have permission to delete this report.")

    report = get_object_or_404(ExpenseReport, pk=pk)
    report.delete()
    return redirect("report_list")
