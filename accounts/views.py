# accounts/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from expenses.models import ExpenseReport
from .models import Profile
from .forms import UserEditForm, ProfileEditForm
from django.db.models import Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from expenses.models import ExpenseReport

try:
    from expenses.models import Contract
except Exception:
    Contract = None

try:
    from partners.models import SalesPartner
except Exception:
    SalesPartner = None


def get_sales_people(only_sales: bool = False):
    """
    영업담당자 드롭다운에 넣을 사용자 목록을 반환.
    only_sales=True 이면 부서/직책에 '영업'이 들어간 계정만.
    """
    qs = User.objects.filter(is_active=True).select_related("profile")
    if only_sales:
        qs = qs.filter(Q(profile__department__icontains="영업") |
                       Q(profile__role__icontains="영업"))
    return qs.order_by("first_name", "username")


def can_manage_accounts(user):
    """'관리자모드' 또는 '사장모드'만 허용 (슈퍼유저는 항상 허용)"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        # user.profile이 없을 수도 있으니 안전하게 처리
        return getattr(user, "profile", None) and user.profile.access in ("관리자모드", "사장모드")
    except Profile.DoesNotExist:
        return False

@login_required
def dashboard(request):
    groups = list(request.user.groups.values_list('name', flat=True))
    role = getattr(getattr(request.user, "profile", None), "role", None)

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

    if Contract is not None:
        qs = Contract.objects.all()
        stats["temp"]          = qs.filter(status="draft").count()
        stats["request_count"] = qs.filter(status="submitted").count()
        stats["in_progress"]   = qs.filter(status="processing").count()
        stats["done"]          = qs.filter(status="completed").count()

    return render(
        request,
        "dashboard.html",
        {
            "groups": groups, 
            "role": role, 
            "recent_reports": recent_reports,
            "stats": stats,
        },
    )


@login_required
def create_profile(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        name = request.POST.get("name", "").strip()
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


# ---- 계정보기: 모든 계정(활성/비활성 포함) ----
@login_required
@user_passes_test(can_manage_accounts)
def view_profile(request):
    users = (
        User.objects.select_related("profile")
        .order_by("username")
    )
    return render(request, "view_profile.html", {"users": users})


# ---- 계정 수정 ----
@login_required
@user_passes_test(can_manage_accounts)
def edit_account(request, user_id):
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)

    # Profile 없으면 생성
    profile = getattr(target, "profile", None)
    if profile is None:
        profile = Profile.objects.create(user=target)

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


@login_required
def contract_temporary_list(request):
    # 임시저장만
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="draft")       # ✅ 임시저장만
          .order_by("-created_at"))
    return render(request, "temporary.html", {
        "contracts": qs,
        "page_title": "임시저장 목록",
    })


@login_required
def contract_processing_list(request):
    # 품의요청만
    qs = (Contract.objects
          .select_related("writer", "sales_owner")
          .prefetch_related("items")
          .filter(status="submitted")   # ✅ 품의요청만
          .order_by("-created_at"))
    return render(request, "processing.html", {
        "contracts": qs,
        "page_title": "품의요청 목록",
    })

@login_required
@require_POST
def contract_submit(request, pk: int):
    contract = get_object_or_404(Contract, pk=pk)

    if contract.status != "draft":
        messages.warning(request, "임시저장 상태에서만 품의요청이 가능합니다.")
        return redirect("contract_temporary")

    contract.status = "submitted"
    contract.save(update_fields=["status"])

    # ⬇️ contract_no가 없으면 pk(또는 id)로 대체
    display_no = getattr(contract, "contract_no", None) or getattr(contract, "id", contract.pk)
    messages.success(request, f"[{display_no}] 품의요청으로 전환했습니다.")

    return redirect("contract_processing")