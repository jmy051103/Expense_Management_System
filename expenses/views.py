# expenses/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import ExpenseReportForm, ExpenseItemFormSet, ContractForm
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
       '저장하기' => draft, '품의요청' => submitted
    """
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    if request.method == "POST":
        is_submit = request.POST.get("submit_final") == "1"
        status = "submitted" if is_submit else "draft"

        form = ContractForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                contract = form.save(commit=False)
                contract.writer = request.user
                contract.status = status
                contract.title = contract.customer_company or "무제 계약"
                contract.save()

                for f in request.FILES.getlist("images"):
                    ContractImage.objects.create(contract=contract, original=f)

            return redirect(reverse("contract_detail", args=[contract.id]))
        else:
            # 폼 에러를 템플릿에서 표시할 수 있게 넘김
            ctx = {
                "sales_people": sales_people,
                "customer_managers": [],
                "form_errors": form.errors,   # {{ form_errors }} 로 출력 가능
                "is_edit": True,
            }
            return render(request, "add_contract.html", ctx)

    # GET
    ctx = {"sales_people": sales_people, "customer_managers": []}
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


@login_required
def contract_edit(request, pk):
    """계약 수정: add_contract.html 폼 재사용, 이미지 업로드 시 기존에 추가로 붙음"""
    contract = get_object_or_404(
        Contract.objects.select_related("writer", "sales_owner").prefetch_related("images"),
        pk=pk
    )

    # (선택) 권한 정책: 작성자만 수정 가능. 필요 없으면 이 블록 제거.
    if not (request.user.is_superuser or request.user == contract.writer):
        messages.error(request, "수정 권한이 없습니다. (작성자만 수정 가능)")
        return redirect("contract_detail", pk=contract.pk)

    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    if request.method == "POST":
        is_submit = request.POST.get("submit_final") == "1"
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            with transaction.atomic():
                contract = form.save(commit=False)
                contract.writer = contract.writer  # 유지
                # 버튼 분기: 품의요청만 submitted로 바꾸고, 아니면 draft로 저장
                contract.status = "submitted" if is_submit else "draft"
                contract.title = contract.customer_company or (contract.title or "무제 계약")
                contract.save()

                # 새로 업로드된 이미지는 기존에 추가로 붙음
                for f in request.FILES.getlist("images"):
                    ContractImage.objects.create(contract=contract, original=f)

                del_ids = request.POST.getlist("del_image_ids[]")
                if del_ids:
                    ContractImage.objects.filter(contract=contract, id__in=del_ids).delete()

            return redirect("contract_detail", pk=contract.pk)
        else:
            ctx = {
                "sales_people": sales_people,
                "customer_managers": [],
                "form_errors": form.errors,
                "contract": contract,     # 템플릿에서 기존 값/이미지 접근용(선택)
                "is_edit": True,
            }
            return render(request, "add_contract.html", ctx)

    # GET
    # 폼 자체는 add_contract.html에서 input name으로 받으니,
    # 여기선 드롭다운 등 컨텍스트만 넘겨도 됨(필요시 initial을 템플릿 value로 매핑)
    ctx = {
        "sales_people": sales_people,
        "customer_managers": [],
        "contract": contract,
        "is_edit": True,
    }
    return render(request, "add_contract.html", ctx)


@login_required
@require_POST
def contract_delete(request, pk):
    """계약 삭제: 작성자 또는 superuser만"""
    contract = get_object_or_404(Contract, pk=pk)
    if not (request.user.is_superuser or request.user == contract.writer):
        from django.contrib import messages
        messages.error(request, "삭제 권한이 없습니다. (작성자만 삭제 가능)")
        return redirect("contract_detail", pk=contract.pk)  # 상세 페이지로 되돌리기

    contract.delete()
    from django.contrib import messages
    messages.success(request, "계약이 성공적으로 삭제되었습니다.")
    return redirect("contract_list")

