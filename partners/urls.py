from django.urls import path
from . import views

app_name = "partners"  

urlpatterns = [
    path("sales/", views.sales_partner_list, name="sales_partner_list"),
    path("sales/create/", views.sales_partner_create, name="sales_partner_create"),
    path("sales/<int:pk>/edit/", views.sales_partner_edit, name="sales_partner_edit"),
    path("sales/<int:pk>/delete/", views.sales_partner_delete, name="sales_partner_delete"),

    path("purchase/", views.purchase_partner_list, name="purchase_partner_list"),
    path("purchase/create/", views.purchase_partner_create, name="purchase_partner_create"),
    path("purchase/<int:pk>/edit/", views.purchase_partner_edit, name="purchase_partner_edit"),
    path("purchase/<int:pk>/delete/", views.purchase_partner_delete, name="purchase_partner_delete"),

    # API 엔드포인트
    path("api/partners/<int:pk>/", views.api_partner_detail, name="api_partner_detail"),
    path("api/partners/<int:pk>/contacts/", views.partner_contacts_api, name="partner_contacts_api"),
    path("api/purchase/<int:pk>/", views.api_purchase_detail, name="api_purchase_detail"),
    path("api/purchase/<int:pk>/contacts/", views.purchase_partner_contacts_api, name="purchase_partner_contacts_api"),
]