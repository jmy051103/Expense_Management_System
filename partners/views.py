from django.shortcuts import render

def sales_partner_list(request):
    return render(request, "sales_partner_list.html")

def purchase_partner_list(request):
    return render(request, "purchase_partner_list.html")