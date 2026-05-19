"""
양도소득세 실무 케이스 샘플 — 랜덤 뽑기용.
자주 만나는 케이스 위주로 구성.
"""
from __future__ import annotations

SAMPLE_CASES: list[dict] = [

    # ── 1주택 비과세 기본 ──────────────────────────────────────────────────────
    {
        "label": "1주택 비과세 — 조정지역 보유·거주 2년 이상",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20240601",
            "acquisition_date": "20200301",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 900000000,
            "acquisition_price": 600000000,
            "holding_years": 4.25,
            "residence_years": 2.5,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "1주택 비과세 — 비조정지역 보유 2년 (거주 불필요)",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20210801",
            "property_type": "단독주택",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 700000000,
            "holding_years": 3.2,
            "residence_years": 0.0,
            "is_adjustment_area_at_acquisition": False,
            "is_adjustment_area_at_transfer": False,
        },
    },
    {
        "label": "1주택 비과세 — 보유 2년, 거주 2년 (경계값)",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20240915",
            "acquisition_date": "20220901",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 850000000,
            "holding_years": 2.04,
            "residence_years": 2.0,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 고가주택 ──────────────────────────────────────────────────────────────
    {
        "label": "고가주택 — 12억 초과, 초과분만 과세",
        "category": "고가주택",
        "fact_json": {
            "transfer_date": "20240801",
            "acquisition_date": "20190501",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 1800000000,
            "acquisition_price": 900000000,
            "holding_years": 5.25,
            "residence_years": 3.0,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "고가주택 — 13억, 장기보유특별공제 적용",
        "category": "고가주택",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20140301",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 1300000000,
            "acquisition_price": 500000000,
            "holding_years": 10.75,
            "residence_years": 10.0,
            "is_adjustment_area_at_acquisition": False,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 단기 양도 ─────────────────────────────────────────────────────────────
    {
        "label": "단기세율 — 보유 1년 미만 (세율 70%)",
        "category": "단기세율",
        "fact_json": {
            "transfer_date": "20240901",
            "acquisition_date": "20240101",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 700000000,
            "acquisition_price": 620000000,
            "holding_years": 0.67,
            "residence_years": 0.0,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "단기세율 — 보유 1~2년 (세율 60%)",
        "category": "단기세율",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20230301",
            "property_type": "연립다세대",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 400000000,
            "acquisition_price": 350000000,
            "holding_years": 1.58,
            "residence_years": 0.0,
            "is_adjustment_area_at_transfer": False,
        },
    },

    # ── 다주택자 중과 ──────────────────────────────────────────────────────────
    {
        "label": "2주택 중과 — 조정지역 (기본세율 +20%p)",
        "category": "중과",
        "fact_json": {
            "transfer_date": "20240701",
            "acquisition_date": "20180601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 800000000,
            "acquisition_price": 450000000,
            "holding_years": 6.08,
            "residence_years": 0.5,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "3주택 중과 — 조정지역 (기본세율 +30%p)",
        "category": "중과",
        "fact_json": {
            "transfer_date": "20241101",
            "acquisition_date": "20170401",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 3,
            "transfer_price": 1100000000,
            "acquisition_price": 500000000,
            "holding_years": 7.58,
            "residence_years": 1.0,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "2주택 — 비조정지역 (중과 아닌 일반세율)",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20240901",
            "acquisition_date": "20190301",
            "property_type": "단독주택",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 500000000,
            "acquisition_price": 280000000,
            "holding_years": 5.5,
            "residence_years": 0.0,
            "is_adjustment_area_at_acquisition": False,
            "is_adjustment_area_at_transfer": False,
        },
    },

    # ── 일시적 2주택 ──────────────────────────────────────────────────────────
    {
        "label": "일시적 2주택 비과세 — 3년 내 종전주택 양도",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20240801",
            "acquisition_date": "20190601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 950000000,
            "holding_years": 5.17,
            "residence_years": 2.5,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "temp_two_house": {
                    "new_acquisition_date": "20220601",
                    "old_house_must_sell_by": "20250601",
                    "new_is_adjustment_area": True,
                }
            },
        },
    },
    {
        "label": "일시적 2주택 — 기한 초과로 비과세 미적용",
        "category": "중과",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20180301",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 900000000,
            "holding_years": 6.75,
            "residence_years": 2.0,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "temp_two_house": {
                    "new_acquisition_date": "20210601",
                    "old_house_must_sell_by": "20240601",
                    "new_is_adjustment_area": True,
                }
            },
        },
    },

    # ── 상속주택 ──────────────────────────────────────────────────────────────
    {
        "label": "상속주택 경로A — 일반주택 양도 시 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20170501",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 800000000,
            "holding_years": 7.4,
            "residence_years": 2.5,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "inheritance": {
                    "death_date": "20210301",
                    "same_household_at_death": False,
                    "inherited_as_only_house": True,
                    "selling_inherited_house": False,
                }
            },
        },
    },
    {
        "label": "상속주택 경로B — 상속받은 주택 직접 양도",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20241101",
            "acquisition_date": "20210601",
            "property_type": "단독주택",
            "acquisition_reason": "상속",
            "household_house_count": 1,
            "transfer_price": 600000000,
            "holding_years": 3.4,
            "residence_years": 0.0,
            "is_adjustment_area_at_transfer": False,
            "special_cases": {
                "inheritance": {
                    "death_date": "20210601",
                    "same_household_at_death": True,
                    "inherited_as_only_house": True,
                    "selling_inherited_house": True,
                    "donor_acquisition_date": "19950301",
                }
            },
        },
    },

    # ── 증여 이월과세 ─────────────────────────────────────────────────────────
    {
        "label": "배우자 증여 이월과세 — 5년 이내 양도",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20220301",
            "property_type": "아파트",
            "acquisition_reason": "증여",
            "household_house_count": 1,
            "transfer_price": 900000000,
            "acquisition_price": 750000000,
            "holding_years": 2.58,
            "residence_years": 2.0,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "gift": {
                    "is_gift_from_spouse_or_lineal": True,
                    "donor_acquisition_date": "20150601",
                    "donor_acquisition_price": 400000000,
                }
            },
        },
    },
    {
        "label": "직계존비속 증여 이월과세 — 10년 이내 양도",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20240601",
            "acquisition_date": "20180901",
            "property_type": "아파트",
            "acquisition_reason": "증여",
            "household_house_count": 1,
            "transfer_price": 1100000000,
            "acquisition_price": 850000000,
            "holding_years": 5.75,
            "residence_years": 3.0,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "gift": {
                    "is_gift_from_spouse_or_lineal": True,
                    "donor_acquisition_date": "20100301",
                    "donor_acquisition_price": 350000000,
                }
            },
        },
    },
    {
        "label": "타인 증여 — 이월과세 미적용 (일반 양도)",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20200601",
            "property_type": "연립다세대",
            "acquisition_reason": "증여",
            "household_house_count": 1,
            "transfer_price": 450000000,
            "acquisition_price": 380000000,
            "holding_years": 4.5,
            "residence_years": 1.0,
            "special_cases": {
                "gift": {
                    "is_gift_from_spouse_or_lineal": False,
                }
            },
        },
    },

    # ── 혼인합가 / 동거봉양 ───────────────────────────────────────────────────
    {
        "label": "혼인합가 일시적 2주택 — 5년 내 양도 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20160301",
            "property_type": "아파트",
            "acquisition_reason": "혼인합가",
            "household_house_count": 2,
            "transfer_price": 750000000,
            "holding_years": 8.58,
            "residence_years": 3.0,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "marriage_merge": {
                    "marriage_date": "20200901",
                    "spouse_house_count_before_marriage": 1,
                    "own_house_count_before_marriage": 1,
                }
            },
        },
    },

    # ── 분양권 ────────────────────────────────────────────────────────────────
    {
        "label": "분양권 양도 — 2021년 이후 취득 (주택 수 산입, 단기세율)",
        "category": "단기세율",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20220601",
            "property_type": "분양권",
            "acquisition_reason": "분양",
            "household_house_count": 1,
            "transfer_price": 600000000,
            "acquisition_price": 500000000,
            "holding_years": 2.33,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "분양권 양도 — 2021년 이전 취득 (주택 수 미산입)",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20240601",
            "acquisition_date": "20191001",
            "property_type": "분양권",
            "acquisition_reason": "분양",
            "household_house_count": 0,
            "transfer_price": 550000000,
            "acquisition_price": 400000000,
            "holding_years": 4.67,
            "is_adjustment_area_at_transfer": False,
        },
    },

    # ── 입주권 / 재건축 ──────────────────────────────────────────────────────
    {
        "label": "조합원입주권 — 원조합원 1주택 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20050601",
            "property_type": "입주권",
            "acquisition_reason": "재건축",
            "household_house_count": 1,
            "transfer_price": 1000000000,
            "holding_years": 19.5,
            "residence_years": 5.0,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 상생임대 ──────────────────────────────────────────────────────────────
    {
        "label": "상생임대 — 거주요건 2년 면제 (조정지역 1주택)",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20210301",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 950000000,
            "holding_years": 3.58,
            "residence_years": 0.5,
            "is_adjustment_area_at_acquisition": True,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "sangsaeng_rental": {
                    "contract_date": "20220301",
                    "contract_period_months": 24,
                    "previous_monthly_rent": 1500000,
                    "new_monthly_rent": 1550000,
                    "has_prior_contract": True,
                }
            },
        },
    },

    # ── 장기임대 감면 ─────────────────────────────────────────────────────────
    {
        "label": "장기임대 — 8년 의무임대 완료, 감면 적용",
        "category": "감면",
        "fact_json": {
            "transfer_date": "20241101",
            "acquisition_date": "20140601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 700000000,
            "acquisition_price": 300000000,
            "holding_years": 10.4,
            "residence_years": 0.0,
            "is_adjustment_area_at_transfer": False,
            "special_cases": {
                "long_term_rental": {
                    "registration_date": "20140801",
                    "mandatory_period_years": 8,
                    "mandatory_period_fulfilled": True,
                    "rent_increase_limit_complied": True,
                }
            },
        },
    },

    # ── 겸용주택 ──────────────────────────────────────────────────────────────
    {
        "label": "겸용주택 — 주거비율 60% (주택으로 전체 과세)",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20150301",
            "property_type": "겸용주택",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 800000000,
            "holding_years": 9.58,
            "residence_years": 4.0,
            "residential_area_ratio": 0.6,
            "is_adjustment_area_at_transfer": False,
        },
    },
    {
        "label": "겸용주택 — 주거비율 40% (상가 부분 일반과세)",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20100601",
            "property_type": "겸용주택",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 1200000000,
            "acquisition_price": 400000000,
            "holding_years": 14.5,
            "residence_years": 8.0,
            "residential_area_ratio": 0.4,
        },
    },

    # ── 다가구주택 ────────────────────────────────────────────────────────────
    {
        "label": "다가구주택 — 1동 전체 단독소유, 1주택 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20170801",
            "property_type": "다가구",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 900000000,
            "holding_years": 7.17,
            "residence_years": 3.0,
            "is_adjustment_area_at_transfer": False,
        },
    },

    # ── 비거주자 ──────────────────────────────────────────────────────────────
    {
        "label": "비거주자 — 단기보유 양도 (거주요건 무관, 일반세율)",
        "category": "일반과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20200601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 800000000,
            "acquisition_price": 600000000,
            "holding_years": 4.33,
            "residence_years": 0.0,
            "is_non_resident": True,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 해외이주 / 수용 ───────────────────────────────────────────────────────
    {
        "label": "해외이주 — 거주요건 면제, 1주택 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20190601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "transfer_price": 850000000,
            "holding_years": 5.5,
            "residence_years": 1.0,
            "is_adjustment_area_at_transfer": True,
            "special_cases": {
                "residence_exemption_reason": "해외이주",
            },
        },
    },
    {
        "label": "공익사업 수용 — 거주요건 면제 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20180301",
            "property_type": "단독주택",
            "acquisition_reason": "수용",
            "household_house_count": 1,
            "transfer_price": 650000000,
            "holding_years": 6.58,
            "residence_years": 0.5,
            "is_adjustment_area_at_transfer": False,
            "special_cases": {
                "residence_exemption_reason": "수용",
            },
        },
    },

    # ── 농어촌주택 ────────────────────────────────────────────────────────────
    {
        "label": "농어촌주택 + 일반주택 — 일반주택 양도 시 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241101",
            "acquisition_date": "20180601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 2,
            "transfer_price": 800000000,
            "holding_years": 6.42,
            "residence_years": 2.5,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 경매 취득 ─────────────────────────────────────────────────────────────
    {
        "label": "경매 취득 — 1주택 장기보유 비과세",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241201",
            "acquisition_date": "20160901",
            "property_type": "아파트",
            "acquisition_reason": "경매",
            "household_house_count": 1,
            "transfer_price": 950000000,
            "acquisition_price": 450000000,
            "holding_years": 8.25,
            "residence_years": 5.0,
            "is_adjustment_area_at_transfer": False,
        },
    },

    # ── 이혼재산분할 ──────────────────────────────────────────────────────────
    {
        "label": "이혼재산분할 — 취득 후 1주택 양도",
        "category": "비과세",
        "fact_json": {
            "transfer_date": "20241001",
            "acquisition_date": "20210301",
            "property_type": "아파트",
            "acquisition_reason": "이혼재산분할",
            "household_house_count": 1,
            "transfer_price": 700000000,
            "holding_years": 3.58,
            "residence_years": 2.0,
            "is_adjustment_area_at_transfer": True,
        },
    },

    # ── 사실관계 부족 시나리오 ─────────────────────────────────────────────────
    {
        "label": "사실관계 부족 — 양도가액 미입력 (고가주택 판단 불가)",
        "category": "사실관계부족",
        "fact_json": {
            "transfer_date": "20240901",
            "acquisition_date": "20190601",
            "property_type": "아파트",
            "acquisition_reason": "매매",
            "household_house_count": 1,
            "holding_years": 5.25,
            "residence_years": 3.0,
            "is_adjustment_area_at_transfer": True,
        },
    },
    {
        "label": "사실관계 부족 — 상속 취득일 미입력",
        "category": "사실관계부족",
        "fact_json": {
            "transfer_date": "20241101",
            "acquisition_date": "20210801",
            "property_type": "단독주택",
            "acquisition_reason": "상속",
            "household_house_count": 2,
            "transfer_price": 650000000,
            "holding_years": 3.25,
            "is_adjustment_area_at_transfer": False,
        },
    },
]

CATEGORY_LABELS = {
    "비과세": "🟢 비과세",
    "감면": "🔵 감면",
    "중과": "🔴 중과",
    "일반과세": "🟡 일반과세",
    "단기세율": "🔴 단기세율",
    "고가주택": "🟠 고가주택",
    "사실관계부족": "⚪ 사실관계부족",
}
