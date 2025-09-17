# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create/", views.create_profile, name="create_profile"),
    path("view/", views.view_profile, name="view_profile"),
    path("<int:user_id>/edit/", views.edit_account, name="edit_account"),
    path("contracts/<int:pk>/start-processing/",
         views.contract_mark_processing,
         name="contract_mark_processing"),
    path("items/", views.item_list, name="item_list"),
    path("items/add/", views.item_add, name="item_add"),              # ⬅️ 신규
    path("items/<int:pk>/edit/", views.item_edit, name="item_edit"),  # ⬅️ 선택사항(수정)
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),
]