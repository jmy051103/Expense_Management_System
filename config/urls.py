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

    # ---- Contract lists ----
    path("contracts/temporary/",  accounts_views.contract_temporary_list, name="contract_temporary"),   # draft list
    path("contracts/processing/", accounts_views.contract_processing_list, name="contract_processing"),  # submitted list (품의요청)
    path("contracts/process/",    accounts_views.contract_process_page,   name="contract_process_list"), # processing list (결재처리중)
    path("contracts/approved/",   accounts_views.contract_approved_list,  name="contract_approved"),     # completed list

    # ---- Contract actions ----
    path("contracts/<int:pk>/submit/",   accounts_views.contract_submit,   name="contract_submit"),   # draft -> submitted
    path("contracts/<int:pk>/approve/",  accounts_views.contract_approve,  name="contract_approve"),  # submitted -> processing
    path("contracts/<int:pk>/complete/", accounts_views.contract_complete, name="contract_complete"), # processing -> completed
    path("contracts/<int:pk>/delete/",   accounts_views.contract_delete,   name="contract_delete"),   # optional, used by template

]

# 개발 환경에서 media 파일 제공
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)