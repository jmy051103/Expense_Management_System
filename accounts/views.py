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


class SignUpView(CreateView):
    """
    /accounts/signup/ 에서 회원가입 처리.
    가입 성공하면 자동 로그인 + employee 그룹 자동 배정 후 대시보드로 이동.
    """
    form_class = UserCreationForm
    template_name = "registration/create_profile.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)  # self.object = 새 User
        auth_login(self.request, self.object)
        employee_group, _ = Group.objects.get_or_create(name="employee")
        self.object.groups.add(employee_group)

        # 프로필(role)도 employee 보장 (UserProfile을 쓰는 경우)
        if hasattr(self.object, "profile"):
            self.object.profile.role = "employee"
            self.object.profile.save()

        return response
