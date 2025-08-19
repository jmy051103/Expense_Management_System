from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from accounts.views import dashboard, SignUpView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="home.html",          
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", LogoutView.as_view(next_page="home"), name="logout"),
    path("accounts/create_profile/", SignUpView.as_view(), name="signup"),

    path("dashboard/", dashboard, name="dashboard"),
    
    # expenses 앱
    path("expenses/", include("expenses.urls")),
]
