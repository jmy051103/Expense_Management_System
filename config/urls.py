# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
# from accounts import views as accounts_views  # ← 쓰지 않으면 지워도 됨

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

    # 앱 URL들 (네임스페이스 포함해서 한 번씩만!)
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("expenses/", include(("expenses.urls", "expenses"), namespace="expenses")),
    path("partners/", include(("partners.urls", "partners"), namespace="partners")),
    path("reports/",  include(("reports.urls", "reports"),   namespace="reports")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)