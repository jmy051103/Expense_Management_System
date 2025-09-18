# expenses/views.py
# expenses/views.py (top)
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import F
from django.core.paginator import Paginator

from .forms import ExpenseReportForm, ExpenseItemFormSet, ContractForm
from .models import ExpenseReport, Contract, ContractImage, ContractItem

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
                
                names = request.POST.getlist("item_name[]") or []
                qtys  = request.POST.getlist("qty[]") or []
                specs = request.POST.getlist("spec[]") or []
                su    = request.POST.getlist("sell_unit[]") or []
                st    = request.POST.getlist("sell_total[]") or []
                bu    = request.POST.getlist("buy_unit[]") or []
                bt    = request.POST.getlist("buy_total[]") or []
                vend  = request.POST.getlist("vendor[]") or []
                vat   = request.POST.getlist("item_vat_mode[]") or []

                def get(lst, i, default=""):
                    return lst[i] if i < len(lst) else default
                
                for i in range(len(names)):
                    name = (get(names, i, "") or "").strip()
                    qty  = _i(get(qtys, i, 0))
                    if not name or qty <= 0:
                        continue  # 서버에서도 최소 검증

                    sell_unit  = _d(get(su, i, 0))
                    buy_unit   = _d(get(bu, i, 0))
                    sell_total = _d(get(st, i, 0))
                    buy_total  = _d(get(bt, i, 0))

                    # 서버에서 금액 재계산(신뢰성 향상): 단가/수량이 있으면 금액 덮어쓰기
                    if qty and sell_unit:
                        sell_total = (sell_unit * qty).quantize(Decimal("1."))  # 반올림 규칙은 필요시 변경
                    if qty and buy_unit:
                        buy_total  = (buy_unit * qty).quantize(Decimal("1."))

                    ContractItem.objects.create(
                        contract=contract,
                        name=name,
                        qty=qty,
                        spec=get(specs, i, "") or "",
                        sell_unit=sell_unit,
                        sell_total=sell_total,
                        buy_unit=buy_unit,
                        buy_total=buy_total,
                        vendor=get(vend, i, "") or "",
                        vat_mode=(get(vat, i, "separate") or "separate"),
                    )

            return redirect("contract_detail", pk=contract.pk)
        else:
            # 폼 에러를 템플릿에서 표시할 수 있게 넘김
            ctx = {
                "sales_people": sales_people,
                "customer_managers": [],
                "form_errors": form.errors,
            }
            return render(request, "add_contract.html", ctx)

    # GET
    ctx = {"sales_people": sales_people, "customer_managers": []}
    return render(request, "add_contract.html", ctx)

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
    contract = get_object_or_404(
        Contract.objects.select_related("writer", "sales_owner").prefetch_related("images"),
        pk=pk
    )

    # (선택) 작성자만 수정 가능
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
                # 1) 계약 저장
                contract = form.save(commit=False)
                contract.status = "submitted" if is_submit else "draft"
                contract.title  = contract.customer_company or (contract.title or "무제 계약")
                contract.save()

                # 2) 이미지 삭제/추가
                del_ids = request.POST.getlist("del_image_ids[]")
                if del_ids:
                    ContractImage.objects.filter(contract=contract, id__in=del_ids).delete()

                for f in request.FILES.getlist("images"):
                    ContractImage.objects.create(contract=contract, original=f)

            
                contract.items.all().delete()   # related_name='items'인 경우

                # 새 항목 읽기
                names = request.POST.getlist("item_name[]") or []
                qtys  = request.POST.getlist("qty[]") or []
                specs = request.POST.getlist("spec[]") or []
                su    = request.POST.getlist("sell_unit[]") or []
                st    = request.POST.getlist("sell_total[]") or []
                bu    = request.POST.getlist("buy_unit[]") or []
                bt    = request.POST.getlist("buy_total[]") or []
                vend  = request.POST.getlist("vendor[]") or []
                vat   = request.POST.getlist("item_vat_mode[]") or []

                # 안전 인덱싱 helper (리스트 길이가 달라도 IndexError 방지)
                def get(lst, i, default=""):
                    return lst[i] if i < len(lst) else default

                for i in range(len(names)):
                    name = (get(names, i, "") or "").strip()
                    qty  = int(get(qtys, i, 0) or 0)
                    if not name or qty <= 0:
                        continue

                    sell_unit  = _d(get(su, i, 0))
                    buy_unit   = _d(get(bu, i, 0))
                    sell_total = _d(get(st, i, 0))
                    buy_total  = _d(get(bt, i, 0))

                    if qty and sell_unit: sell_total = (sell_unit * qty).quantize(Decimal("1."))
                    if qty and buy_unit:  buy_total  = (buy_unit  * qty).quantize(Decimal("1."))
                    
                    ContractItem.objects.create(
                        contract=contract,
                        name=name,
                        qty=_i(get(qtys, i, 0)),
                        spec=get(specs, i, "") or "",
                        sell_unit=_d(get(su, i, 0)),
                        sell_total=_d(get(st, i, 0)),
                        buy_unit=_d(get(bu, i, 0)),
                        buy_total=_d(get(bt, i, 0)),
                        vendor=get(vend, i, "") or "",
                        vat_mode=(get(vat, i, "separate") or "separate"),
                    )

            return redirect("contract_detail", pk=contract.pk)

        # 폼 에러 → 다시 렌더
        ctx = {
            "sales_people": sales_people,
            "customer_managers": [],
            "form_errors": form.errors,
            "contract": contract,
            "is_edit": True,
        }
        return render(request, "add_contract.html", ctx)

    # GET
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


@login_required
def contract_list(request):
    """계약 목록 (검색 + per_page 선택 + 숫자 페이지네이션 + 행 선택 체크박스만)"""
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    qs = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("images", "items")
        .order_by(
            F("collect_invoice_date").desc(nulls_last=True),
            "-created_at",
            "-id",
        )
    )

    # ===== 검색/필터 =====
    date_from   = (request.GET.get("date_from") or "").strip()
    date_to     = (request.GET.get("date_to") or "").strip()
    q_customer  = (request.GET.get("q_customer") or "").strip()
    q_vendor    = (request.GET.get("q_vendor") or "").strip()
    owner_id    = (request.GET.get("owner") or "").strip()
    q_item      = (request.GET.get("q_item") or "").strip()
    contract_no = (request.GET.get("contract_no") or "").strip()
    status      = (request.GET.get("status") or "").strip()

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)
    if q_vendor:
        qs = qs.filter(items__vendor__icontains=q_vendor).distinct()
    if owner_id:
        qs = qs.filter(sales_owner_id=owner_id)
    if q_item:
        qs = qs.filter(items__name__icontains=q_item).distinct()
    if contract_no:
        qs = qs.filter(contract_no__icontains=contract_no)
    if status:
        qs = qs.filter(status=status)

    # ===== per_page & 페이지네이션 =====
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

    # page 파라미터 제거한 쿼리스트링 (숫자 페이지네이션 링크에 사용)
    qs_keep = request.GET.copy()
    qs_keep.pop("page", None)
    qs_without_page = qs_keep.urlencode()

    return render(request, "contract_list.html", {
        "page_obj": page_obj,
        "per_page_options": per_page_options,
        "per_page": per_page,
        "qs": qs_without_page,
        "sales_people": sales_people,
    })

def _d(v):
    """'1,234' -> Decimal('1234'); blanks -> Decimal('0')"""
    s = (str(v) if v is not None else "").replace(",", "").strip()
    try:
        return Decimal(s) if s else Decimal("0")
    except InvalidOperation:
        return Decimal("0")
    
def _i(v):
    """int parser that tolerates commas/blank"""
    try:
        return int(_d(v))
    except Exception:
        return 0