from django.urls import path
from . import views

urlpatterns = [
    path("sales/", views.sales_partner_list, name="sales_partner_list"),
    path("purchase/", views.purchase_partner_list, name="purchase_partner_list"),
]