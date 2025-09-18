# reports/urls.py
from django.urls import path
from . import views

app_name = "reports"  

urlpatterns = [
    path("monthly-purchase-contract/", views.monthly_purchase_contract, name="monthly_purchase_contract"),
    path("monthly-sales-contract/", views.monthly_sales_contract, name="monthly_sales_contract"),
    path("margin-static/", views.margin_static, name="margin_static"),
    path("monthly-purchase-invoice/", views.monthly_purchase_invoice, name="monthly_purchase_invoice"),
]