# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create/", views.create_profile, name="create_profile"),
    path("view/", views.view_profile, name="view_profile"),
    path("<int:user_id>/edit/", views.edit_account, name="edit_account"),
]