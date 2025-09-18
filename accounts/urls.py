# accounts/urls.py
from django.urls import path
from . import views

app_name = "accounts" 

urlpatterns = [
    # 대시보드/계정
    path("dashboard/", views.dashboard, name="dashboard"),
    path("create/", views.create_profile, name="create_profile"),
    path("view/", views.view_profile, name="view_profile"),
    path("<int:user_id>/edit/", views.edit_account, name="edit_account"),
    path("accounts/<int:user_id>/delete/", views.delete_account, name="delete_account"),

    # --- 계약 목록들 ---
    # 임시저장
    path("contracts/temporary/", views.contract_temporary_list, name="contract_temporary"),
    # 결재요청 목록
    path("contracts/processing/", views.contract_processing_list, name="contract_processing"),
    # 결재처리중 목록 (두 이름 모두 지원: 템플릿/리다이렉트 혼용 대비)
    path("contracts/in-progress/", views.contract_process_page, name="contract_process"),
    path("contracts/in-progress/list/", views.contract_process_page, name="contract_process_list"),

    # 결재완료 목록
    path("contracts/approved/", views.contract_approved_list, name="contract_approved"),

    # --- 계약 단건 액션/편집 ---
    path("contracts/<int:pk>/edit/", views.contract_edit, name="contract_edit"),
    path("contracts/<int:pk>/delete/", views.contract_delete, name="contract_delete"),
    path("contracts/<int:pk>/submit/", views.contract_submit, name="contract_submit"),
    path("contracts/<int:pk>/approve/", views.contract_approve, name="contract_approve"),
    path("contracts/<int:pk>/complete/", views.contract_complete, name="contract_complete"),
    path("contracts/<int:pk>/start-processing/", views.contract_mark_processing, name="contract_mark_processing"),

    # --- 품목 ---
    path("items/", views.item_list, name="item_list"),
    path("items/add/", views.item_add, name="item_add"),
    path("items/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),
]