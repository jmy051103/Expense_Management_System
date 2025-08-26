from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from accounts.views import dashboard, create_profile, view_profile, edit_account

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

    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("accounts/create/", create_profile, name="create_profile"),
    path("accounts/view/", view_profile, name="view_profile"),
    path("accounts/<int:user_id>/edit/", edit_account, name="edit_account"),
    
    

    # expenses 앱
    path("expenses/", include("expenses.urls")),
]
