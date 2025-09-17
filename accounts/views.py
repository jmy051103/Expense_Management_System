# accounts/views.py
from decimal import Decimal, InvalidOperation
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
        "draft": "contract_temporary",
        "submitted": "contract_processing",
        "processing": "contract_process_list",
        "completed": "contract_approved",
    }.get(status, "dashboard")


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

    monthly_kpis["sales_total"] = int(sales_total)
    monthly_kpis["buy_total"] = int(buy_total)
    monthly_kpis["margin_rate"] = margin_rate
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
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        name = (request.POST.get("name") or "").strip()
        role = request.POST.get("position")
        department = request.POST.get("department")
        access = request.POST.get("access")

        if not username or not password:
            messages.error(request, "아이디와 패스워드는 필수입니다.")
            return render(request, "create_profile.html")

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, password=password)
                if name:
                    user.first_name = name
                    user.save(update_fields=["first_name"])
                Profile.objects.create(
                    user=user,
                    role=role,
                    department=department,
                    access=access,
                )
        except IntegrityError:
            messages.error(request, "이미 존재하는 아이디입니다. 다른 아이디를 입력하세요.")
            return render(request, "create_profile.html")

        messages.success(request, f"{username} 프로필이 성공적으로 생성되었습니다!")
        return redirect("dashboard")

    return render(request, "create_profile.html")


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
            messages.success(request, f"{target.username} 계정이 수정되었습니다.")
            return redirect("view_profile")
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
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="draft")
          .order_by("-created_at"))
    return render(request, "temporary.html", {
        "contracts": qs,
        "page_title": "임시저장 목록",
    })


@login_required
def contract_processing_list(request):
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="submitted")
          .order_by("-created_at"))
    return render(request, "processing.html", {
        "contracts": qs,
        "page_title": "품의요청 목록",
    })


@login_required
def contract_process_page(request):
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="processing")
          .order_by("-created_at"))
    return render(request, "contract_process.html", {
        "contracts": qs,
        "page_title": "결재처리중 목록",
    })


@login_required
def contract_approved_list(request):
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="completed")
          .order_by("-created_at"))
    return render(request, "approved.html", {
        "contracts": qs,
        "page_title": "결재완료 목록",
    })


# 상태 전환
@login_required
@require_POST
def contract_submit(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)

    if _is_employee(request.user) and contract.writer_id != request.user.id:
        messages.error(request, "직원모드는 본인이 작성한 계약만 품의요청할 수 있습니다.")
        return redirect("contract_temporary")

    if contract.status != "draft":
        messages.warning(request, "임시저장 상태에서만 품의요청이 가능합니다.")
        return redirect("contract_temporary")

    contract.status = "submitted"
    contract.save(update_fields=["status"])
    disp = getattr(contract, "contract_no", None) or contract.pk
    messages.success(request, f"[{disp}] 품의요청으로 전환했습니다.")
    return redirect("contract_processing")


@login_required
@require_POST
def contract_process(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "품의요청 상태에서만 결재처리로 전환할 수 있습니다.")
        return redirect("contract_processing")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    disp = getattr(contract, "contract_no", None) or contract.pk
    messages.success(request, f"[{disp}] 결재처리중으로 전환했습니다.")
    return redirect("contract_processing")


@login_required
@require_POST
def contract_mark_processing(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "품의요청 상태에서만 결재처리로 전환 가능합니다.")
        return redirect("contract_processing")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    disp = getattr(contract, "contract_no", None) or contract.pk
    messages.success(request, f"[{disp}] 결재처리중으로 이동했습니다.")
    return redirect("contract_process")


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
        return redirect("contract_processing")
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "submitted":
        messages.warning(request, "품의요청 상태에서만 결재처리가 가능합니다.")
        return redirect("contract_processing")
    contract.status = "processing"
    contract.save(update_fields=["status"])
    messages.success(request, f"[{contract.pk}] 결재처리중으로 변경했습니다.")
    return redirect("contract_processing")


@login_required
@require_POST
def contract_complete(request, pk: int):
    if not _can_complete(request.user):
        messages.error(request, "사장만 결재완료 처리가 가능합니다.")
        return redirect("contract_processing")
    contract = get_object_or_404(Contract, pk=pk)
    if contract.status != "processing":
        messages.warning(request, "결재처리중 상태에서만 결재완료가 가능합니다.")
        return redirect("contract_processing")
    contract.status = "completed"
    contract.save(update_fields=["status"])
    messages.success(request, f"[{contract.pk}] 결재완료로 변경했습니다.")
    return redirect("contract_approved")


@login_required
@require_POST
def contract_delete(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)
    if _is_employee(request.user):
        if contract.status != "draft" or contract.writer_id != request.user.id:
            messages.error(request, "직원모드는 임시저장 상태의 본인 계약만 삭제할 수 있습니다.")
            return redirect("contract_temporary")
    contract.delete()
    messages.success(request, "계약이 삭제되었습니다.")
    return redirect("contract_temporary")


@login_required
def contract_edit(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    acc = _get_access(request.user)
    if acc == "직원모드" and contract.status != "draft":
        messages.error(request, "직원모드는 임시저장 상태만 수정할 수 있습니다.")
        if contract.status == "submitted":
            return redirect("contract_processing")
        elif contract.status == "processing":
            return redirect("contract_process_list")
        elif contract.status == "completed":
            return redirect("contract_approved")
        return redirect("contract_temporary")

    if _is_employee(request.user):
        if contract.writer_id != request.user.id or contract.status != "draft":
            messages.error(request, "직원모드는 본인이 작성한 '임시저장' 계약만 수정할 수 있습니다.")
            return redirect(_redirect_by_status(contract.status))

    # (편집 폼 렌더/처리는 다른 파일에 있을 것으로 가정)
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

    try:
        page_size = int(request.GET.get("size", "10") or 10)
    except ValueError:
        page_size = 10
    page_size = max(5, min(page_size, 100))

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ⬇️ page 제외한 쿼리스트링
    qs_params = request.GET.copy()
    qs_params.pop('page', None)
    qs = qs_params.urlencode()

    return render(request, "item_list.html", {
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "total": paginator.count,
        "page_size": page_size,
        "qs": qs,  # ✅ 추가
    })


@login_required
def item_add(request):
    """
    새 카탈로그 품목 등록.
    - vendor: FK/CharField 모두 호환
    - contract: (있다면) None 저장을 가정 → 모델에서 null=True 필요
    """
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return redirect("item_list")

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
        messages.success(request, "품목이 저장되었습니다.")
        return redirect("item_list")

    return render(request, "item_form.html", {
        "mode": "create",
        "vendor_names": vendor_names,
        "form": {"vendor": "", "name": "", "buy_unit": "", "sell_unit": ""},
    })


@login_required
def item_edit(request, pk: int):
    if Item is None:
        messages.error(request, "ContractItem 모델을 찾을 수 없습니다.")
        return redirect("item_list")

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
                messages.success(request, "수정되었습니다.")
                return redirect("item_list")
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
        return redirect("item_list")
    obj = get_object_or_404(Item, pk=pk)
    obj.delete()
    messages.success(request, "삭제했습니다.")
    return redirect("item_list")
