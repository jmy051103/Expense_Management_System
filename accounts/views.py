# accounts/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.urls import reverse_lazy

# 최근 정산서 표시를 위해 추가
from expenses.models import ExpenseReport
from .models import Profile

@login_required
def dashboard(request):
    groups = list(request.user.groups.values_list('name', flat=True))
    role = getattr(getattr(request.user, "profile", None), "role", None)

    # 최근 정산서 5건 (누가 작성했든)
    recent_reports = (
        ExpenseReport.objects
        .select_related("creator")
        .order_by("-created_at")[:5]
    )

    return render(
        request,
        "dashboard.html",
        {
            "groups": groups,
            "role": role,
            "recent_reports": recent_reports,
        },
    )

@login_required  # (optional) require login to create accounts
def create_profile(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        name = request.POST.get("name", "").strip()
        role = request.POST.get("position")        # select name is "position"
        department = request.POST.get("department")
        access = request.POST.get("access")

        # basic validation (show message and stay on the page)
        if not username or not password:
            messages.error(request, "아이디와 패스워드는 필수입니다.")
            return render(request, "create_profile.html")

        try:
            with transaction.atomic():
                # create_user hashes the password
                user = User.objects.create_user(username=username, password=password)
                # store display name in first_name (or split if you prefer)
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

        # success -> redirect to home with a flash message
        messages.success(request, f"{username} 프로필이 성공적으로 생성되었습니다!")
        return redirect("dashboard")   # make sure you have a url named 'home'

    # GET
    return render(request, "create_profile.html")