from django.urls import path
from . import views

urlpatterns = [
    path("sales/", views.sales_partner_list, name="sales_partner_list"),
    path("partners/sales/create/", views.sales_partner_create, name="sales_partner_create"),
    path("partners/sales/<int:pk>/edit/", views.sales_partner_edit, name="sales_partner_edit"),
    path("partners/sales/<int:pk>/delete/", views.sales_partner_delete, name="sales_partner_delete"),
    path("purchase/", views.purchase_partner_list, name="purchase_partner_list"),
]