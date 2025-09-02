# expenses/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib.auth.models import User

from .forms import ExpenseReportForm, ExpenseItemFormSet
from .models import ExpenseReport, Contract, ContractImage

def _is_approver(user) -> bool:
    """approver 그룹 또는 superuser라면 True"""
    return user.is_superuser or user.groups.filter(name="approver").exists()

# ------------------- 기존 보고서(ExpenseReport) 뷰들 그대로 -------------------
@login_required
def report_list(request):
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
    if not _is_approver(request.user):
        raise PermissionDenied("You do not have permission to delete this report.")
    report = get_object_or_404(ExpenseReport, pk=pk)
    report.delete()
    return redirect("report_list")

# ------------------- 여기부터 계약(Contract) 뷰 -------------------

@login_required
def add_contract(request):
    """계약정보 등록 + 이미지 다중 업로드.
       '저장하기' => draft, '품의요청' => submitted 로 상태 저장
    """
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    if request.method == "POST":
        # 어떤 버튼인지 확인: 품의요청 버튼은 name="submit_final" value="1"
        is_submit = request.POST.get("submit_final") == "1"
        status = "submitted" if is_submit else "draft"

        # 폼 값 받기 (네 HTML name들과 1:1)
        sales_owner_id   = request.POST.get("sales_owner") or None
        customer_company = request.POST.get("customer_company", "").strip()
        customer_manager = request.POST.get("customer_manager", "").strip()  # 선택사항이면 문자열로
        customer_phone   = request.POST.get("customer_phone", "").strip()
        customer_email   = request.POST.get("customer_email", "").strip()

        ship_item = request.POST.get("ship_item", "").strip()
        ship_date = request.POST.get("ship_date") or None
        ship_addr = request.POST.get("ship_addr", "").strip()
        ship_phone = request.POST.get("ship_phone", "").strip()

        collect_invoice_date = request.POST.get("collect_invoice_date") or None
        collect_date = request.POST.get("collect_date") or None
        collect_note = request.POST.get("collect_note", "").strip()
        special_note = request.POST.get("special_note", "").strip()

        # (필요시 필수값 검사)
        if not customer_company:
            # 간단 유효성 피드백
            ctx = {
                "sales_people": sales_people,
                "customer_managers": [],
                "error": "회사명을 입력해주세요.",
            }
            return render(request, "add_contract.html", ctx)

        with transaction.atomic():
            # Contract 저장 (Neon/Postgres에 들어감)
            contract = Contract.objects.create(
                title=customer_company or "무제 계약",
                writer=request.user,
                sales_owner_id=sales_owner_id,

                customer_company=customer_company,
                customer_manager=customer_manager,
                customer_phone=customer_phone,
                customer_email=customer_email,

                ship_item=ship_item,
                ship_date=ship_date,
                ship_addr=ship_addr,
                ship_phone=ship_phone,

                collect_invoice_date=collect_invoice_date,
                collect_date=collect_date,
                collect_note=collect_note,
                special_note=special_note,

                status=status,
            )

            # 이미지 여러 개 저장 (name="images")
            for f in request.FILES.getlist("images"):
                ContractImage.objects.create(contract=contract, original=f)

        # 저장 후 상세 페이지 이동
        return redirect(reverse("contract_detail", args=[contract.id]))

    # GET: 폼 렌더링
    ctx = {
        "sales_people": sales_people,
        "customer_managers": [],
    }
    return render(request, "add_contract.html", ctx)


@login_required
def contract_list(request):
    """계약 목록 (최신순)"""
    contracts = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    return render(request, "contract_list.html", {"contracts": contracts})


@login_required
def contract_detail(request, pk):
    """계약 상세"""
    contract = get_object_or_404(
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("images"),
        pk=pk
    )
    return render(request, "contract_detail.html", {"contract": contract})