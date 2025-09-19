# reports/views.py
import json
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from datetime import date

from django.db.models import Sum, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model

from expenses.models import ContractItem, Contract


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

    # ✅ 담당자=작성자 기준으로 필터
    if owner_id:
        try:
            owner_id_int = int(owner_id)
            qs = qs.filter(contract__writer_id=owner_id_int)
        except (TypeError, ValueError):
            pass

    daily = defaultdict(lambda: {"total": ZERO, "supply": ZERO, "vat": ZERO})
    month_total  = ZERO
    month_supply = ZERO
    month_vat    = ZERO

    for it in qs:
        created_dt = it.contract.created_at
        key = (created_dt.date() if hasattr(created_dt, "date") else created_dt).isoformat()

        supply = (it.sell_total or ZERO)  # 세전 매출금액
        if (it.vat_mode or "").lower() == "separate":
            vat = supply * TEN
            total = supply + vat
        else:
            vat   = ZERO
            total = supply

        daily[key]["supply"] += supply
        daily[key]["vat"]    += vat
        daily[key]["total"]  += total

        month_supply += supply
        month_vat    += vat
        month_total  += total

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
    """
    월별 매입계약통계
    - 기준일: 계약 등록일(contract.created_at)
    - 공급가액 = 매입금액(buy_total)
    - 부가세액 = 공급가액 * 10% (반올림)
    - 합계     = 공급가액 + 부가세액
    """
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
        qs = qs.filter(
            Q(contract__customer_company__icontains=q_customer) |
            Q(vendor__icontains=q_customer)
        )

    # ✅ 담당자=작성자 기준으로 변경
    if owner_id:
        try:
            qs = qs.filter(contract__writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass

    daily = defaultdict(lambda: {"total": ZERO, "supply": ZERO, "vat": ZERO})
    month_total = month_supply = month_vat = ZERO

    for it in qs:
        day_key = it.contract.created_at.date().isoformat()

        supply = (it.buy_total or ZERO)  # 세전 매입금액
        if (it.vat_mode or "").lower() == "separate":
            vat = supply * TEN
            total = supply + vat
        else:
            vat   = ZERO
            total = supply

        daily[day_key]["supply"] += supply
        daily[day_key]["vat"]    += vat
        daily[day_key]["total"]  += total

        month_supply += supply
        month_vat    += vat
        month_total  += total

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
    return render(request, "monthly_purchase_contract.html", context)


def margin_static(request):
    """
    기간 내 등록된 계약 건별 매출/매입/마진/마진율 표 + 합계
    - 기준일: contract.created_at.date()
    - 매출금액: sum(items.sell_total)
    - 매입금액: sum(items.buy_total)
    - 마진금액/마진율: 계약에 저장된 값(있으면) 사용, 없으면 즉석 계산
    """
    today = timezone.localdate()

    date_from = (request.GET.get("date_from") or "").strip()
    date_to   = (request.GET.get("date_to") or "").strip()
    if not date_from:
        date_from = today.replace(day=1).isoformat()
    if not date_to:
        date_to = today.isoformat()

    q_customer = (request.GET.get("q_customer") or "").strip()
    owner_id   = request.GET.get("owner") or None

    qs = (
        Contract.objects
        .filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        .select_related("writer", "sales_owner")
        .annotate(
            sales_amount    = Coalesce(
                Sum("items__sell_total"),
                Value(0, output_field=DecimalField(max_digits=18, decimal_places=2))
            ),
            purchase_amount = Coalesce(
                Sum("items__buy_total"),
                Value(0, output_field=DecimalField(max_digits=18, decimal_places=2))
            ),
        )
        .order_by("created_at", "id")
    )

    if q_customer:
        qs = qs.filter(customer_company__icontains=q_customer)

    # ✅ 담당자=작성자 기준으로 변경
    if owner_id:
        try:
            qs = qs.filter(writer_id=int(owner_id))
        except (TypeError, ValueError):
            pass

    rows = []
    total_sales = total_buy = total_margin = ZERO

    rate_sum = ZERO
    rate_cnt = 0

    has_profit_field = hasattr(Contract, "profit")
    has_margin_field = hasattr(Contract, "margin_rate")

    for c in qs:
        sales = c.sales_amount or ZERO
        buy   = c.purchase_amount or ZERO

        if has_profit_field and c.profit is not None:
            margin_amt = Decimal(c.profit)
        else:
            margin_amt = (sales - buy)

        if has_margin_field and c.margin_rate is not None:
            margin_rate = Decimal(c.margin_rate)
        else:
            margin_rate = (margin_amt / sales * Decimal("100")) if sales else ZERO

        rows.append({
            "day":    c.created_at.date(),
            "sales":  sales,
            "buy":    buy,
            "margin": margin_amt,
            "rate":   margin_rate,
        })

        total_sales  += sales
        total_buy    += buy
        total_margin += margin_amt

        rate_sum += margin_rate
        rate_cnt += 1

    avg_rate = (rate_sum / rate_cnt) if rate_cnt else ZERO

    context = {
        "date_from": date_from,
        "date_to":   date_to,
        "rows": rows,
        "sum_sales":  int(total_sales),
        "sum_buy":    int(total_buy),
        "sum_margin": int(total_margin),
        "sum_rate":   float(avg_rate),
        "sales_people": get_user_model().objects.filter(is_active=True)
                         .order_by("first_name", "username"),
    }
    return render(request, "margin_static.html", context)


def monthly_purchase_invoice(request):
    """
    매입처 월별 보고서
    - 필터: year/month (연도 2019~2025로 한정)
    - 집계: 매입품목 단위로 (매입처→품목) 묶고, 매입처별 소계 + 전체 합계
    - VAT별도(separate): 공급가액 = 합계/1.1, 부가세 = 차액
      면세(exempt): 공급가액 = 합계, 부가세 = 0
    """
    today = timezone.localdate()
    year  = int(request.GET.get("year")  or today.year)
    month = int(request.GET.get("month") or today.month)

    # 연도 범위 고정
    if year < 2019:
        year = 2019
    if year > 2025:
        year = 2025

    start = date(year, month, 1)
    end   = date(year + (1 if month == 12 else 0), (month % 12) + 1, 1)

    items = (
        ContractItem.objects
        .select_related("contract")
        .filter(contract__created_at__date__gte=start,
                contract__created_at__date__lt=end)
    )

    def split_supply_vat(total, vat_mode):
        total = Decimal(total or 0)
        if (vat_mode or "").lower() == "separate":
            supply = total / Decimal("1.1")
            vat    = total - supply
        else:
            supply = total
            vat    = ZERO
        return supply, vat

    groups = defaultdict(lambda: {
        "rows": [],
        "subtotal": {"qty": 0, "total": ZERO, "supply": ZERO, "vat": ZERO},
    })
    sum_total  = ZERO
    sum_supply = ZERO
    sum_vat    = ZERO

    for it in items:
        vendor = (it.vendor or "").strip() or "(미지정)"
        qty    = it.qty or 0
        total  = Decimal(it.buy_total or 0)
        supply, vat = split_supply_vat(total, it.vat_mode)

        g = groups[vendor]
        g["rows"].append({
            "name":   it.name or "",
            "qty":    qty,
            "total":  total,
            "supply": supply,
            "vat":    vat,
        })
        g["subtotal"]["qty"]    += qty
        g["subtotal"]["total"]  += total
        g["subtotal"]["supply"] += supply
        g["subtotal"]["vat"]    += vat

        sum_total  += total
        sum_supply += supply
        sum_vat    += vat

    # 출력용 리스트 (매입처명 정렬 + 번호)
    groups_out = []
    for i, vendor in enumerate(sorted(groups.keys()), start=1):
        g = groups[vendor]
        groups_out.append({
            "no": i,
            "vendor": vendor,
            "rows": g["rows"],
            "subtotal": g["subtotal"],
        })

    context = {
        "year": year,
        "month": month,
        "groups": groups_out,
        "sum_total":  int(sum_total),
        "sum_supply": int(sum_supply),
        "sum_vat":    int(sum_vat),
        "YEARS": list(range(2019, 2026)),
    }
    return render(request, "monthly_purchase_invoice.html", context)