from django.urls import path
from . import views

urlpatterns = [
    path("sales/", views.sales_partner_list, name="sales_partner_list"),
    path("partners/sales/create/", views.sales_partner_create, name="sales_partner_create"),
    path("partners/sales/<int:pk>/edit/", views.sales_partner_edit, name="sales_partner_edit"),
    path("partners/sales/<int:pk>/delete/", views.sales_partner_delete, name="sales_partner_delete"),
    path("purchase/", views.purchase_partner_list, name="purchase_partner_list"),
    path("partners/purchase/create/", views.purchase_partner_create, name="purchase_partner_create"),
    path("partners/purchase/<int:pk>/edit/", views.purchase_partner_edit, name="purchase_partner_edit"),
    path("partners/purchase/<int:pk>/delete/", views.purchase_partner_delete, name="purchase_partner_delete"),

    # API 엔드포인트
    path("api/partners/<int:pk>/", views.api_partner_detail, name="api_partner_detail"),
    path("api/partners/<int:pk>/contacts/", views.partner_contacts_api, name="partner_contacts_api"),
    path("api/purchases/<int:pk>/", views.api_purchase_detail, name="api_purchase_detail"),
    path("api/purchases/<int:pk>/contacts/", views.purchase_partner_contacts_api, name="purchase_partner_contacts_api"),
]