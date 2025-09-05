# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from accounts.views import dashboard, create_profile, view_profile, edit_account
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # 메인 페이지
    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    # 로그인/로그아웃
    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="home.html",          
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", LogoutView.as_view(next_page="home"), name="logout"),

    # 계정 관리
    path("dashboard/", dashboard, name="dashboard"),
    path("accounts/create/", create_profile, name="create_profile"),
    path("accounts/view/", view_profile, name="view_profile"),
    path("accounts/<int:user_id>/edit/", edit_account, name="edit_account"),


    # expenses 앱
    path("expenses/", include("expenses.urls")),
    ]

# 개발 환경에서 media 파일 제공
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)