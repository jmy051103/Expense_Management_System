from django.urls import path
from . import views


urlpatterns = [
    path("reports/", views.report_list, name="report_list"),
    path("reports/new/", views.report_create, name="report_create"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/edit/", views.report_edit, name="report_edit"), 
    path("reports/<int:pk>/delete/", views.report_delete, name="report_delete"),

    path("contracts/add/", views.add_contract, name="add_contract"),
    path("contracts/list/", views.contract_list, name="contract_list"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/edit/", views.contract_edit, name="contract_edit"),
    path("contracts/<int:pk>/delete/", views.contract_delete, name="contract_delete"),
    path("contracts/export/", views.contract_export, name="contract_export"),
]
