# accounts/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.views.generic import CreateView
from django.shortcuts import render
from django.urls import reverse_lazy

# 최근 정산서 표시를 위해 추가
from expenses.models import ExpenseReport


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


def create_profile(request):
    return render(request, "create_profile.html")