# reports/views.py
import json
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model
from expenses.models import ContractItem

TEN   = Decimal("0.10")
ZERO  = Decimal("0")

def monthly_sales_contract(request):
    today = timezone.localdate()
    year  = int(request.GET.get("year")  or today.year)
    month = int(request.GET.get("month") or today.month)

    q_customer = (request.GET.get("q_customer") or "").strip()
    owner_id   = request.GET.get("owner") or None

    qs = (
        ContractItem.objects
        .select_related("contract")
        .filter(contract__created_at__year=year,
                contract__created_at__month=month)
    )
    if q_customer:
        qs = qs.filter(contract__customer_company__icontains=q_customer)
    if owner_id:
        qs = qs.filter(contract__sales_owner_id=owner_id)

    daily = defaultdict(lambda: {"total": ZERO, "supply": ZERO, "vat": ZERO})
    month_total  = ZERO
    month_supply = ZERO
    month_vat    = ZERO

    for it in qs:
        created_dt = it.contract.created_at
        key = (created_dt.date() if hasattr(created_dt, "date") else created_dt).isoformat()

        supply = (it.sell_total or ZERO)                              # = 매출금액
        vat    = (supply * TEN).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total  = supply + vat

        daily[key]["supply"] += supply
        daily[key]["vat"]    += vat
        daily[key]["total"]  += total

        month_supply += supply
        month_vat    += vat
        month_total  += total

    # 숫자는 정수로 내려주기
    daily_sorted = dict(sorted(
        (k, {
            "total":  int(v["total"]),
            "supply": int(v["supply"]),
            "vat":    int(v["vat"]),
        })
        for k, v in daily.items()
    ))

    context = {
        "year": year,
        "month": month,
        "daily_json": json.dumps(daily_sorted, ensure_ascii=False),
        "month_total":  int(month_total),
        "month_supply": int(month_supply),
        "month_vat":    int(month_vat),
        "sales_people": get_user_model().objects.filter(is_active=True)
                           .order_by("first_name", "username"),
    }
    return render(request, "monthly_sales_contract.html", context)

def monthly_purchase_contract(request):
    return render(request, "monthly_purchase_contract.html")

def margin_static(request):
    return render(request, "margin_static.html")

def monthly_purchase_voice(request):
    return render(request, "monthly_purchase_voice.html")