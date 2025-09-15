from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as accounts_views

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

    # accounts 앱 URL include
    path("accounts/", include("accounts.urls")),

    # expenses 앱
    path("expenses/", include("expenses.urls")),

    # partner 앱
    path("partners/", include("partners.urls")),

    path("contracts/temporary/",  accounts_views.contract_temporary_list, name="contract_temporary"),
    path("contracts/processing/", accounts_views.contract_processing_list, name="contract_processing"),
    path("contracts/<int:pk>/submit/", accounts_views.contract_submit, name="contract_submit"),
    path("contracts/<int:pk>/process/", accounts_views.contract_process, name="contract_process"),
    path("contracts/process/", accounts_views.contract_process_page, name="contract_process"),
]

# 개발 환경에서 media 파일 제공
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)