# accounts/views.py
from decimal import Decimal, InvalidOperation
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

# 대시보드 KPI 집계에 사용
from expenses.models import ContractItem

from .forms import ProfileEditForm, UserEditForm
from .models import Profile

# 외부 앱 모델들(없을 수도 있으니 안전하게)
try:
    from expenses.models import ExpenseReport
except Exception:
    ExpenseReport = None

try:
    from expenses.models import Contract
except Exception:
    Contract = None

# 품목(Catalog) 화면에서 사용할 Item 모델 별칭
try:
    from expenses.models import ContractItem as Item
except Exception:
    try:
        from accounts.models import ContractItem as Item
    except Exception:
        Item = None

try:
    from partners.models import SalesPartner
except Exception:
    SalesPartner = None


# ---------------------
# 유틸/권한 헬퍼
# ---------------------
def _get_access(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return ""
    if user.is_superuser:
        return "SUPER"
    try:
        return getattr(getattr(user, "profile", None), "access", "") or ""
    except Exception:
        return ""


def _is_employee(user) -> bool:
    return (not user.is_superuser) and _get_access(user) == "직원모드"


def _redirect_by_status(status: str) -> str:
    return {
        "draft": "accounts:contract_temporary",
        "submitted": "accounts:contract_processing",
        "processing": "accounts:contract_process",
        "completed": "accounts:contract_approved",
    }.get(status, "accounts:dashboard")

def _pagination_block(page_obj, paginator, block_size=10):
    cur = page_obj.number
    num_pages = paginator.num_pages
    block_idx = (cur - 1) // block_size
    start_page = block_idx * block_size + 1
    end_page = min(start_page + block_size - 1, num_pages)
    prev_block = start_page - block_size if start_page > 1 else None
    next_block = start_page + block_size if end_page < num_pages else None
    return {
        "start_page": start_page,
        "end_page": end_page,
        "prev_block": prev_block,
        "next_block": next_block,
        "num_pages": num_pages,
    }

def can_manage_accounts(user):
    """'관리자모드' 또는 '사장모드'만 허용 (슈퍼유저는 항상 허용)"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return getattr(user, "profile", None) and user.profile.access in ("관리자모드", "사장모드")
    except Profile.DoesNotExist:
        return False


def _to_decimal(v, default="0"):
    try:
        return Decimal(str(v).replace(",", "").strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


# ---------------------
# 대시보드/계정
# ---------------------
@login_required
def dashboard(request):
    groups = list(request.user.groups.values_list("name", flat=True))
    role = getattr(getattr(request.user, "profile", None), "role", None)

    recent_reports = []
    if ExpenseReport:
        recent_reports = (
            ExpenseReport.objects.select_related("creator")
            .order_by("-created_at")[:5]
        )

    stats = {
        "temp": 0,
        "request_count": 0,
        "in_progress": 0,
        "done": 0,
        "accounts": SalesPartner.objects.count() if SalesPartner else 0,
    }
    if Contract:
        qs = Contract.objects.all()
        stats["temp"] = qs.filter(status="draft").count()
        stats["request_count"] = qs.filter(status="submitted").count()
        stats["in_progress"] = qs.filter(status="processing").count()
        stats["done"] = qs.filter(status="completed").count()

    # ===== 이번 달 합계/마진율 집계 추가 =====
    today = timezone.localdate()
    month_start = today.replace(day=1)
    # 다음달 1일(배타)
    if month_start.month == 12:
        month_end_excl = date(month_start.year + 1, 1, 1)
    else:
        month_end_excl = date(month_start.year, month_start.month + 1, 1)

    monthly_kpis = {"sales_total": 0, "buy_total": 0, "margin_rate": 0.0, "contract_count": 0}
    
    # 이번 달 계약 건수 (Contract 기준)
    if Contract:
        monthly_kpis["contract_count"] = Contract.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lt=month_end_excl,
        ).count()

    # ContractItem 기준으로 합산
    qi = ContractItem.objects.filter(
        contract__created_at__date__gte=month_start,
        contract__created_at__date__lt=month_end_excl,
    )
    agg = qi.aggregate(
        sales_total=Coalesce(Sum("sell_total"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=2))),
        buy_total=Coalesce(Sum("buy_total"), Value(0, output_field=DecimalField(max_digits=18, decimal_places=2))),
    )
    sales_total = Decimal(agg["sales_total"] or 0)
    buy_total = Decimal(agg["buy_total"] or 0)
    margin_amt = sales_total - buy_total
    margin_rate = float((margin_amt / sales_total * 100) if sales_total else 0)

    monthly_kpis["sales_total"] = sales_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    monthly_kpis["buy_total"]   = buy_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    monthly_kpis["margin_rate"] = round(margin_rate, 2) 
    # ======================================

    return render(request, "dashboard.html", {
        "groups": groups,
        "role": role,
        "recent_reports": recent_reports,
        "stats": stats,
        "monthly_kpis": monthly_kpis, 
    })


@login_required
def create_profile(request):
    # 모델에서 choices 꺼내서 템플릿에 넘길 준비
    role_choices   = getattr(Profile, "ROLE_CHOICES", [])
    dept_choices   = getattr(Profile, "DEPT_CHOICES", [])
    access_choices = getattr(Profile, "ACCESS_CHOICES", [])

    if request.method == "POST":
        username   = (request.POST.get("username") or "").strip()
        password   = request.POST.get("password") or ""
        name       = (request.POST.get("name") or "").strip()
        email      = (request.POST.get("email") or "").strip()     # ✅ 추가
        role       = (request.POST.get("position") or "").strip()
        department = (request.POST.get("department") or "").strip()
        access     = (request.POST.get("access") or "").strip()

        # 기본 검증 (이메일은 선택 사항으로 처리)
        if not username or not password:
            messages.error(request, "아이디와 패스워드는 필수입니다.")
        elif not role or not department or not access:
            messages.error(request, "직책/부서/권한을 선택해주세요.")
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(username=username, password=password)

                    # ✅ 이름/이메일 업데이트 (있는 값만 저장)
                    updates = []
                    if name:
                        user.first_name = name
                        updates.append("first_name")
                    if email:
                        user.email = email
                        updates.append("email")
                    if updates:
                        user.save(update_fields=updates)

                    Profile.objects.create(
                        user=user, role=role, department=department, access=access
                    )
                return redirect("accounts:dashboard")
            except IntegrityError:
                messages.error(request, "이미 존재하는 아이디입니다. 다른 아이디를 입력하세요.")

        # 여기로 오면 에러 → 입력값 유지해서 다시 렌더
        return render(request, "create_profile.html", {
            "role_choices": role_choices,
            "dept_choices": dept_choices,
            "access_choices": access_choices,
            "form": {
                "username": username,
                "name": name,
                "email": email,                   # ✅ 추가
                "role": role,
                "department": department,
                "access": access,
            },
        })

    # GET
    return render(request, "create_profile.html", {
        "role_choices": role_choices,
        "dept_choices": dept_choices,
        "access_choices": access_choices,
        "form": {"username": "", "name": "", "email": "", "role": "", "department": "", "access": ""},  # ✅ 추가
    })


@login_required
@user_passes_test(can_manage_accounts)
def view_profile(request):
    users = User.objects.select_related("profile").order_by("username")
    return render(request, "view_profile.html", {"users": users})


@login_required
@user_passes_test(can_manage_accounts)
def edit_account(request, user_id):
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile = getattr(target, "profile", None) or Profile.objects.create(user=target)

    if request.method == "POST":
        uform = UserEditForm(request.POST, instance=target)
        pform = ProfileEditForm(request.POST, instance=profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()

            new_pw = (uform.cleaned_data.get("password1") or "").strip()
            if new_pw:
                target.set_password(new_pw)
                target.save(update_fields=["password"])
                if request.user.id == target.id:
                    update_session_auth_hash(request, target)  # 본인 비번 변경 시 로그아웃 방지

            return redirect("accounts:view_profile")
        messages.error(request, "입력값을 확인해주세요.")
    else:
        uform = UserEditForm(instance=target)
        pform = ProfileEditForm(instance=profile)

    return render(request, "edit_account.html", {
        "uform": uform, "pform": pform, "target": target
    })




# ---------------------
# 계약 목록들
# ---------------------
@login_required
def contract_temporary_list(request):
    """
    임시저장(status='draft') 전용 목록
    - contract_list와 동일한 검색/페이지네이션/엑셀(선택 id 전달) UX
    """
    # 작성자 셀렉트용
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    qs = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("items")
        .filter(status="draft")   # ★ 임시저장만
        .order_by(
            # collect_invoice_date 최신 우선 → 없으면 작성일 최신
            "-created_at",
            "-id",
            F("collect_invoice_date").desc(nulls_last=True),
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
    # status 필터는 임시저장 화면에선 고정이므로 없음

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)
    if q_vendor:
        qs = qs.filter(items__vendor__icontains=q_vendor).distinct()
    if owner_id:
        try:
            qs = qs.filter(writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass
    if q_item:
        qs = qs.filter(items__name__icontains=q_item).distinct()
    if contract_no:
        qs = qs.filter(contract_no__icontains=contract_no)

    # ===== per_page & 페이지네이션 =====
    per_page_options = [10, 20, 30, 50, 100]
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    block = _pagination_block(page_obj, paginator)

    # page 제외 쿼리스트링 (엑셀/페이지 링크에 재사용)
    qs_keep = request.GET.copy()
    qs_keep.pop("page", None)
    qs_without_page = qs_keep.urlencode()

    BLOCK_SIZE = 10
    cur = page_obj.number
    num_pages = paginator.num_pages
    block_index = (cur - 1) // BLOCK_SIZE
    start_page = block_index * BLOCK_SIZE + 1
    end_page = min(start_page + BLOCK_SIZE - 1, num_pages)

    prev_block = start_page - BLOCK_SIZE if start_page > 1 else None
    next_block = start_page + BLOCK_SIZE if end_page < num_pages else None

    return render(request, "temporary.html", {
        "contracts": page_obj,             # ← 반복에 그대로 사용
        "page_obj": page_obj,
        "per_page_options": per_page_options,
        "per_page": per_page,
        "qs": qs_without_page,             # ← 엑셀/페이지 링크에서 재사용
        "sales_people": sales_people,      # ← 작성자 드롭다운
        "page_title": "임시저장 목록",

        **block,
    })


@login_required
def contract_processing_list(request):
    """
    결재요청 목록 (status=submitted)
    - contract_list/temporary 와 동일한 검색/정렬/페이지네이션/엑셀 선택 동작
    """
    # 작성자 드롭다운용
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    # 기본 쿼리 (정렬: 세금계산서발행일 최신 → 작성일 최신 → id 최신)
    qs = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("items")
        .filter(status="submitted")
        .order_by(
            "-created_at",
            "-id",
            F("collect_invoice_date").desc(nulls_last=True),
        )
    )

    # ===== 검색 파라미터 =====
    date_from   = (request.GET.get("date_from") or "").strip()
    date_to     = (request.GET.get("date_to") or "").strip()
    q_customer  = (request.GET.get("q_customer") or "").strip()
    q_vendor    = (request.GET.get("q_vendor") or "").strip()
    owner_id    = (request.GET.get("owner") or "").strip()
    q_item      = (request.GET.get("q_item") or "").strip()
    contract_no = (request.GET.get("contract_no") or "").strip()

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)
    if q_vendor:
        qs = qs.filter(items__vendor__icontains=q_vendor).distinct()
    if owner_id:
        try:
            qs = qs.filter(writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass
    if q_item:
        qs = qs.filter(items__name__icontains=q_item).distinct()
    if contract_no:
        qs = qs.filter(contract_no__icontains=contract_no)

    # ===== 페이지 사이즈 & 페이지네이션 =====
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
    block = _pagination_block(page_obj, paginator)

    # page 파라미터만 제거한 쿼리스트링 (페이지 번호 링크/엑셀에 사용)
    qs_keep = request.GET.copy()
    qs_keep.pop("page", None)
    qs_without_page = qs_keep.urlencode()

    return render(request, "processing.html", {
        "contracts": page_obj,            # 템플릿에서 for c in contracts
        "page_obj": page_obj,             # 숫자 페이지네이션/검색건수
        "per_page_options": per_page_options,
        "per_page": per_page,
        "qs": qs_without_page,            # 엑셀/페이지 링크에 유지용
        "sales_people": sales_people,     # 작성자 셀렉트
        "page_title": "결재요청 목록",
        **block,
    })


@login_required
def contract_process_page(request):
    """
    결재처리중 목록 (status=processing)
    - 검색/작성자 필터/페이지네이션/엑셀 선택과 동일 정렬 적용
    """
    # 작성자 드롭다운용
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    # 기본 쿼리 (정렬: 세금계산서발행일 최신 → 작성일 최신 → id 최신)
    qs = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("items")
        .filter(status="processing")
        .order_by(
            "-created_at",
            "-id",
            F("collect_invoice_date").desc(nulls_last=True),
        )
    )

    # ===== 검색 파라미터 =====
    date_from   = (request.GET.get("date_from") or "").strip()
    date_to     = (request.GET.get("date_to") or "").strip()
    q_customer  = (request.GET.get("q_customer") or "").strip()
    q_vendor    = (request.GET.get("q_vendor") or "").strip()
    owner_id    = (request.GET.get("owner") or "").strip()
    q_item      = (request.GET.get("q_item") or "").strip()
    contract_no = (request.GET.get("contract_no") or "").strip()

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)
    if q_vendor:
        qs = qs.filter(items__vendor__icontains=q_vendor).distinct()
    if owner_id:
        try:
            qs = qs.filter(writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass
    if q_item:
        qs = qs.filter(items__name__icontains=q_item).distinct()
    if contract_no:
        qs = qs.filter(contract_no__icontains=contract_no)

    # ===== 페이지 사이즈 & 페이지네이션 =====
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
    block = _pagination_block(page_obj, paginator)

    # page 파라미터 제거한 쿼리스트링 (페이지 링크/엑셀 유지)
    qs_keep = request.GET.copy()
    qs_keep.pop("page", None)
    qs_without_page = qs_keep.urlencode()

    return render(request, "contract_process.html", {
        "contracts": page_obj,            # for c in contracts
        "page_obj": page_obj,             # 페이지네이션/검색건수
        "per_page_options": per_page_options,
        "per_page": per_page,
        "qs": qs_without_page,            # 엑셀/페이지 링크 유지
        "sales_people": sales_people,     # 작성자 셀렉트
        "page_title": "결재처리중 목록",
        **block,
    })


@login_required
def contract_approved_list(request):
    """
    결재완료 목록 (status=completed)
    - 검색/작성자 필터/페이지네이션
    - 정렬: 세금계산서발행일 최신 → 작성일 최신 → id 최신
    """
    # 작성자 드롭다운용
    sales_people = (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .order_by("first_name", "username")
    )

    qs = (
        Contract.objects
        .select_related("writer", "sales_owner")
        .prefetch_related("items")
        .filter(status="completed")
        .order_by(
            "-created_at",
            "-id",
            F("collect_invoice_date").desc(nulls_last=True),
        )
    )

    # ===== 검색 파라미터 =====
    date_from   = (request.GET.get("date_from") or "").strip()
    date_to     = (request.GET.get("date_to") or "").strip()
    q_customer  = (request.GET.get("q_customer") or "").strip()
    q_vendor    = (request.GET.get("q_vendor") or "").strip()
    owner_id    = (request.GET.get("owner") or "").strip()
    q_item      = (request.GET.get("q_item") or "").strip()
    contract_no = (request.GET.get("contract_no") or "").strip()

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)
    if q_vendor:
        qs = qs.filter(items__vendor__icontains=q_vendor).distinct()
    if owner_id:
        try:
            qs = qs.filter(writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass
    if q_item:
        qs = qs.filter(items__name__icontains=q_item).distinct()
    if contract_no:
        qs = qs.filter(contract_no__icontains=contract_no)

    # ===== 페이지 사이즈 & 페이지네이션 =====
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
    block = _pagination_block(page_obj, paginator)
    page_nums = range(block["start_page"], block["end_page"] + 1)

    # page 파라미터 제외한 쿼리스트링 (페이지 링크/엑셀에서 사용)
    qs_keep = request.GET.copy()
    qs_keep.pop("page", None)
    qs_without_page = qs_keep.urlencode()

    return render(request, "approved.html", {
        "contracts": page_obj,            # 템플릿에서 for c in contracts
        "page_obj": page_obj,
        "per_page_options": per_page_options,
        "per_page": per_page,
        "qs": qs_without_page,
        "sales_people": sales_people,     # 작성자 셀렉트 옵션
        "page_title": "결재완료 목록",
        **block,
        'page_nums': page_nums,
    })


# 상태 전환
@login_required
@require_POST
def contract_submit(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)

    if _is_employee(request.user) and contract.writer_id != request.user.id:
        messages.error(request, "직원모드는 본인이 작성한 계약만 결재요청할 수 있습니다.")
        return redirect("accounts:contract_temporary")

    if contract.status != "draft":
        messages.warning(request, "임시저장 상태에서만 결재요청이 가능합니다.")
        return redirect("accounts:contract_temporary")

    contract.status = "submitted"
    contract.save(update_fields=["status"])

    return redirect("accounts:contract_processing")


@login_required
@require_POST
def contract_process(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "결재요청 상태에서만 결재처리로 전환할 수 있습니다.")
        return redirect("accounts:contract_process")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    return redirect("accounts:contract_process")


@login_required
@require_POST
def contract_mark_processing(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "결재요청 상태에서만 결재처리로 전환 가능합니다.")
        return redirect("accounts:contract_processing")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    return redirect("accounts:contract_process")


def _can_approve(user) -> bool:
    if user.is_superuser:
        return True
    return _get_access(user) in ("실장모드", "사장모드")


def _can_complete(user) -> bool:
    if user.is_superuser:
        return True
    return _get_access(user) in ("사장모드",)


@login_required
@require_POST
def contract_approve(request, pk: int):
    if not _can_approve(request.user):
        messages.error(request, "실장/사장만 결재처리가 가능합니다.")
        return redirect("accounts:contract_processing")
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "결재요청 상태에서만 결재처리가 가능합니다.")
        return redirect("accounts:contract_processing")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    return redirect("accounts:contract_process")


@login_required
@require_POST
def contract_complete(request, pk: int):
    if not _can_complete(request.user):
        messages.error(request, "사장만 결재완료 처리가 가능합니다.")
        return redirect("accounts:contract_processing")
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "processing":
        messages.warning(request, "결재처리중 상태에서만 결재완료가 가능합니다.")
        return redirect("accounts:contract_processing")
    contract.status = "completed"
    contract.save(update_fields=["status"])
    return redirect("accounts:contract_approved")


@login_required
@require_POST
def contract_delete(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if _is_employee(request.user):
        if contract.status != "draft" or contract.writer_id != request.user.id:
            messages.error(request, "직원모드는 임시저장 상태의 본인 계약만 삭제할 수 있습니다.")
            return redirect("accounts:contract_temporary")
    contract.delete()
    return redirect("accounts:contract_temporary")


@login_required
def contract_edit(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    acc = _get_access(request.user)

    # ✅ 실장/사장/슈퍼는 어떤 상태든 수정 페이지 진입 허용
    if request.user.is_superuser or acc in ("실장모드", "사장모드"):
        return render(request, "contract_edit.html", {"contract": contract})

    # 직원모드만 제한
    if acc == "직원모드" and contract.status != "draft":
        messages.error(request, "직원모드는 임시저장 상태만 수정할 수 있습니다.")
        return redirect("accounts:contract_temporary")

    if _is_employee(request.user):
        if contract.writer_id != request.user.id or contract.status != "draft":
            messages.error(request, "직원모드는 본인이 작성한 '임시저장' 계약만 수정할 수 있습니다.")
            return redirect(_redirect_by_status(contract.status))

    return render(request, "contract_edit.html", {"contract": contract})


# ---------------------
# 품목(카탈로그) 리스트/등록/수정/삭제
# ---------------------
@login_required
def item_list(request):
    """
    품목정보 리스트: 이름/매입처 검색 + 페이지 사이즈 선택 + 페이지네이션
    기본은 '계약에 속하지 않은(카탈로그)' 항목만 최신순으로 노출.
    """
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return render(request, "item_list.html", {
            "items": [], "page_obj": None, "total": 0, "page_size": 10,
        })

    # 계약 필드가 있으면 카탈로그만, 없으면 전체
    qs = Item.objects.all()
    try:
        f = Item._meta.get_field("contract")
        # 카탈로그(일반 품목)만
        qs = qs.filter(contract__isnull=True)
    except FieldDoesNotExist:
        pass

    qs = qs.order_by("-id")

    q_name = (request.GET.get("q_name") or "").strip()
    q_vendor = (request.GET.get("q_vendor") or "").strip()

    if q_name:
        qs = qs.filter(name__icontains=q_name)

    if q_vendor:
        try:
            f = Item._meta.get_field("vendor")
            if getattr(f, "is_relation", False):
                # ✅ FK면 이름으로만 검색
                qs = qs.filter(vendor__name__icontains=q_vendor)
            else:
                qs = qs.filter(vendor__icontains=q_vendor)
        except FieldDoesNotExist:
            qs = qs.filter(vendor__icontains=q_vendor)

    per_page_options = [10, 20, 30, 50, 100]
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    block = _pagination_block(page_obj, paginator)

    # ⬇️ page 제외한 쿼리스트링
    qs_params = request.GET.copy()
    qs_params.pop('page', None)
    qs = qs_params.urlencode()

    page_nums = range(block["start_page"], block["end_page"] + 1)

    return render(request, "item_list.html", {
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "total": paginator.count,
        "per_page_options": per_page_options,  
        "per_page": per_page,            
        "qs": qs,
        **block,
        "page_nums": page_nums,
    })


@login_required
def item_add(request):
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return redirect("accounts:item_list")

    # datalist 후보
    vendor_names = []
    try:
        from partners.models import PurchasePartner
        vendor_names = list(
            PurchasePartner.objects.order_by("name").values_list("name", flat=True)
        )
    except Exception:
        pass

    if request.method == "POST":
        vendor_in = (request.POST.get("vendor") or "").strip()
        name = (request.POST.get("name") or "").strip()
        buy_unit = _to_decimal(request.POST.get("buy_unit"))
        sell_unit = _to_decimal(request.POST.get("sell_unit"))

        if not vendor_in or not name:
            messages.error(request, "매입처와 품목명은 필수입니다.")
            return render(request, "item_form.html", {
                "mode": "create",
                "vendor_names": vendor_names,
                "form": {
                    "vendor": vendor_in, "name": name,
                    "buy_unit": request.POST.get("buy_unit", ""),
                    "sell_unit": request.POST.get("sell_unit", ""),
                },
            })

        obj = Item()
        # vendor 세팅(FK/CharField 모두 처리)
        try:
            f = Item._meta.get_field("vendor")
            if getattr(f, "is_relation", False):
                from partners.models import PurchasePartner
                partner = (PurchasePartner.objects.filter(name__iexact=vendor_in).first()
                           or PurchasePartner.objects.filter(name__icontains=vendor_in).first())
                if partner is None:
                    messages.error(request, "매입처를 찾을 수 없습니다. 목록에서 선택해 주세요.")
                    return render(request, "item_form.html", {
                        "mode": "create",
                        "vendor_names": vendor_names,
                        "form": {
                            "vendor": vendor_in, "name": name,
                            "buy_unit": request.POST.get("buy_unit", ""),
                            "sell_unit": request.POST.get("sell_unit", ""),
                        },
                    })
                obj.vendor = partner
            else:
                obj.vendor = vendor_in
        except FieldDoesNotExist:
            obj.vendor = vendor_in

        obj.name = name
        if hasattr(obj, "buy_unit"):
            obj.buy_unit = buy_unit
        if hasattr(obj, "sell_unit"):
            obj.sell_unit = sell_unit

        # contract 필드가 있고 null 불가라면 모델 수정이 필요함(문구 안내)
        try:
            cfield = Item._meta.get_field("contract")
            if not getattr(cfield, "null", True):
                messages.error(
                    request,
                    "현재 품목 모델이 계약(FK)을 필수로 요구합니다. "
                    "카탈로그 품목을 쓰려면 expenses.ContractItem.contract 를 null=True 로 변경해주세요."
                )
                return render(request, "item_form.html", {
                    "mode": "create",
                    "vendor_names": vendor_names,
                    "form": {
                        "vendor": vendor_in, "name": name,
                        "buy_unit": request.POST.get("buy_unit", ""),
                        "sell_unit": request.POST.get("sell_unit", ""),
                    },
                })
        except FieldDoesNotExist:
            pass

        obj.save()
        return redirect("accounts:item_list")

    return render(request, "item_form.html", {
        "mode": "create",
        "vendor_names": vendor_names,
        "form": {"vendor": "", "name": "", "buy_unit": "", "sell_unit": ""},
    })


@login_required
def item_edit(request, pk: int):
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return redirect("accounts:item_list")

    obj = get_object_or_404(Item, pk=pk)

    # datalist 후보
    vendor_names = []
    try:
        from partners.models import PurchasePartner
        vendor_names = list(PurchasePartner.objects.order_by("name").values_list("name", flat=True))
    except Exception:
        pass

    if request.method == "POST":
        vendor_in = (request.POST.get("vendor") or "").strip()
        name = (request.POST.get("name") or "").strip()
        buy_unit = _to_decimal(request.POST.get("buy_unit"))
        sell_unit = _to_decimal(request.POST.get("sell_unit"))

        if not vendor_in or not name:
            messages.error(request, "매입처와 품목명은 필수입니다.")
        else:
            try:
                f = Item._meta.get_field("vendor")
                if getattr(f, "is_relation", False):
                    from partners.models import PurchasePartner
                    partner = (PurchasePartner.objects.filter(name__iexact=vendor_in).first()
                               or PurchasePartner.objects.filter(name__icontains=vendor_in).first())
                    if partner is None:
                        messages.error(request, "매입처를 찾을 수 없습니다. 목록에서 선택해 주세요.")
                    else:
                        obj.vendor = partner
                else:
                    obj.vendor = vendor_in
            except FieldDoesNotExist:
                obj.vendor = vendor_in

            obj.name = name
            if hasattr(obj, "buy_unit"):
                obj.buy_unit = buy_unit
            if hasattr(obj, "sell_unit"):
                obj.sell_unit = sell_unit

            try:
                obj.save()
                return redirect("accounts:item_list")
            except Exception as e:
                messages.error(request, f"저장 중 오류: {e}")

    # GET 또는 유효성 실패 시 현재 값 채워서 폼 렌더
    try:
        vfield = Item._meta.get_field("vendor")
        cur_vendor = obj.vendor.name if getattr(vfield, "is_relation", False) else (obj.vendor or "")
    except Exception:
        cur_vendor = getattr(obj, "vendor", "") or ""

    return render(request, "item_form.html", {
        "mode": "edit",
        "vendor_names": vendor_names,
        "form": {
            "vendor": cur_vendor,
            "name": getattr(obj, "name", ""),
            "buy_unit": getattr(obj, "buy_unit", ""),
            "sell_unit": getattr(obj, "sell_unit", ""),
        },
    })


@login_required
@require_POST
def item_delete(request, pk: int):
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return redirect("accounts:item_list")
    obj = get_object_or_404(Item, pk=pk)
    obj.delete()
    return redirect("accounts:item_list")

@login_required
@user_passes_test(can_manage_accounts)
@require_POST
def delete_account(request, user_id: int):
    """관리자/사장만 계정 삭제. 자기 자신 or (비슈퍼가 슈퍼유저) 삭제 불가."""
    target = get_object_or_404(User, pk=user_id)

    if target.id == request.user.id:
        messages.error(request, "본인 계정은 삭제할 수 없습니다.")
        return redirect("accounts:view_profile")

    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "슈퍼유저 계정은 슈퍼유저만 삭제할 수 있습니다.")
        return redirect("accounts:view_profile")

    username = target.username
    target.delete()  # Profile는 OneToOne(CASCADE)라면 함께 삭제됩니다.
    return redirect("accounts:view_profile")

