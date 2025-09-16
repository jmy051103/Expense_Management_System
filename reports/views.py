# contracts/views.py
import json
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model

# ✅ 프로젝트의 실제 모델 경로/이름로 교체
from expenses.models import ContractItem  # 품목 모델(매출금액/과세구분/계약FK 보유)

VAT_RATE = Decimal("0.10")
NINETY   = Decimal("0.90")
ZERO     = Decimal("0")

def monthly_sales_contract(request):
    """
    add_contract.html에서 저장된 계약/품목 정보를 바탕으로
    '계약 등록 날짜' 기준 일별 합계를 계산해 템플릿에 daily_json으로 내려준다.
    규칙:
      - VAT별도(separate): 공급가액 = 매출금액×0.9(반올림), 부가세 = 매출금액×0.1(반올림)
      - 면세(exempt):      공급가액 = 매출금액,        부가세 = 0
    """
    today = timezone.localdate()
    year  = int(request.GET.get("year")  or today.year)
    month = int(request.GET.get("month") or today.month)

    q_customer = (request.GET.get("q_customer") or "").strip()
    owner_id   = request.GET.get("owner") or None

    # ---------- 집계 대상 쿼리 ----------
    items = (ContractItem.objects
             .select_related("contract"))  # ✅ contract FK 이름 확인(일반적으로 "contract")

    # ✅ '계약 등록 날짜' 필드 지정: created_at 또는 저장 시점 필드명으로 교체
    #   created_at이 DateTimeField라면 .date()로 날짜만 사용
    #   아래 where 필터에서도 같은 필드 사용
    created_field = "contract__created_at"   # <-- 필요하면 "contract__created" 등으로 변경

    # 필터: 고객사/담당자
    if q_customer:
        # ✅ 고객사(매출처) 텍스트 필드명 교체
        items = items.filter(contract__customer_company__icontains=q_customer)
    if owner_id:
        # ✅ 영업담당자 FK 필드명 교체(sales_owner 등)
        items = items.filter(contract__sales_owner_id=owner_id)

    # 년/월 범위 필터 (등록일 기준)
    items = items.filter(**{f"{created_field}__year": year,
                            f"{created_field}__month": month})

    # ---------- 파이썬에서 정밀 집계(원단위 반올림) ----------
    daily = defaultdict(lambda: {"total": ZERO, "supply": ZERO, "vat": ZERO})

    # ✅ 매출금액/과세구분 필드명 교체:
    #   - 매출금액: item.sell_total (Decimal)
    #   - 과세구분: item.vat_mode  ('separate' 또는 'exempt')
    for it in items:
        # 날짜 키(등록일 date)
        created_dt = getattr(it.contract, created_field.split("__")[1])
        day = (created_dt.date() if hasattr(created_dt, "date") else created_dt)
        key = day.isoformat()

        amt = (it.sell_total or ZERO)  # 매출금액
        mode = (it.vat_mode or "").lower()

        if mode == "separate":
            supply = (amt * NINETY).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            vat    = (amt - supply).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:  # 면세 또는 기타
            supply = amt.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            vat    = ZERO

        daily[key]["total"]  += amt
        daily[key]["supply"] += supply
        daily[key]["vat"]    += vat

    # 정렬 + JSON 직렬화(숫자는 정수로 내려주기)
    daily_sorted = dict(sorted(
        ((k, {"total": int(v["total"]),
              "supply": int(v["supply"]),
              "vat": int(v["vat"])})
         for k, v in daily.items()),
        key=lambda x: x[0]
    ))

    context = {
        "year": year,
        "month": month,
        "daily_json": json.dumps(daily_sorted, ensure_ascii=False),
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