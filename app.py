import json
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from lunar_python import Lunar, Solar
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

GAN_MAP = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무",
    "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}
ZHI_MAP = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}
WUXING_MAP = {"木": "목", "火": "화", "土": "토", "金": "금", "水": "수"}
GAN_ELEMENT = {
    "갑": "목", "을": "목", "병": "화", "정": "화", "무": "토",
    "기": "토", "경": "금", "신": "금", "임": "수", "계": "수",
}
ANIMAL_MAP = {
    "자": "쥐", "축": "소", "인": "호랑이", "묘": "토끼", "진": "용", "사": "뱀",
    "오": "말", "미": "양", "신": "원숭이", "유": "닭", "술": "개", "해": "돼지",
}

GENERATION_ORDER = ["목", "화", "토", "금", "수"]
CONTROL_ORDER = ["목", "토", "수", "화", "금"]

SHISHEN_MAP = {
    "比肩": "비견", "劫财": "겁재", "食神": "식신", "伤官": "상관",
    "偏财": "편재", "正财": "정재", "七杀": "편관", "正官": "정관",
    "偏印": "편인", "正印": "정인",
}
STAGE_MAP = {
    "长生": "장생", "沐浴": "목욕", "冠带": "관대", "临官": "건록",
    "帝旺": "제왕", "衰": "쇠", "病": "병", "死": "사",
    "墓": "묘", "绝": "절", "胎": "태", "养": "양",
}

PILLAR_LABELS = {"year": "년지", "month": "월지", "day": "일지", "time": "시지"}

LIUHE = {
    frozenset({"자", "축"}): "토", frozenset({"인", "해"}): "목",
    frozenset({"묘", "술"}): "화", frozenset({"진", "유"}): "금",
    frozenset({"사", "신"}): "수", frozenset({"오", "미"}): None,
}
CHONG = {
    frozenset({"자", "오"}), frozenset({"축", "미"}), frozenset({"인", "신"}),
    frozenset({"묘", "유"}), frozenset({"진", "술"}), frozenset({"사", "해"}),
}
PA = {
    frozenset({"자", "유"}), frozenset({"축", "진"}), frozenset({"인", "해"}),
    frozenset({"묘", "오"}), frozenset({"사", "신"}), frozenset({"술", "미"}),
}
HAE = {
    frozenset({"자", "미"}), frozenset({"축", "오"}), frozenset({"인", "사"}),
    frozenset({"묘", "진"}), frozenset({"신", "해"}), frozenset({"유", "술"}),
}
SANGHYEONG = frozenset({"자", "묘"})
JAHYEONG_ZHI = {"진", "오", "유", "해"}

SAMHAP_GROUPS = [
    (frozenset({"인", "오", "술"}), "화"), (frozenset({"신", "자", "진"}), "수"),
    (frozenset({"사", "유", "축"}), "금"), (frozenset({"해", "묘", "미"}), "목"),
]
BANGHAP_GROUPS = [
    (frozenset({"인", "묘", "진"}), "동방목"), (frozenset({"사", "오", "미"}), "남방화"),
    (frozenset({"신", "유", "술"}), "서방금"), (frozenset({"해", "자", "축"}), "북방수"),
]
SAMHYEONG_GROUPS = [
    (frozenset({"인", "사", "신"}), "인사신 삼형"),
    (frozenset({"축", "술", "미"}), "축술미 삼형"),
]


def analyze_zhi_relations(zhi_dict):
    items = list(zhi_dict.items())
    results = []

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            k1, z1 = items[i]
            k2, z2 = items[j]
            pair = frozenset({z1, z2})
            label = f"{PILLAR_LABELS[k1]}-{PILLAR_LABELS[k2]}"
            if pair in LIUHE:
                elem = LIUHE[pair]
                results.append(f"{label} {z1}{z2} 육합" + (f"(합화 {elem})" if elem else ""))
            if pair in CHONG:
                results.append(f"{label} {z1}{z2} 충")
            if pair in PA:
                results.append(f"{label} {z1}{z2} 파")
            if pair in HAE:
                results.append(f"{label} {z1}{z2} 해")
            if pair == SANGHYEONG:
                results.append(f"{label} {z1}{z2} 상형")
            if z1 == z2 and z1 in JAHYEONG_ZHI:
                results.append(f"{label} {z1}{z2} 자형")

    zhi_set = set(zhi_dict.values())
    for group, elem in SAMHAP_GROUPS:
        matched = zhi_set & group
        if len(matched) == 3:
            results.append(f"{''.join(sorted(group))} 삼합(化 {elem})")
        elif len(matched) == 2:
            results.append(f"{''.join(sorted(matched))} 반합(化 {elem} 기운)")
    for group, name in BANGHAP_GROUPS:
        if group <= zhi_set:
            results.append(f"{''.join(sorted(group))} 방합({name})")
    for group, name in SAMHYEONG_GROUPS:
        if group <= zhi_set:
            results.append(name)

    return results


YANG_GAN = {"갑", "병", "무", "경", "임"}


def ten_god_between(dm_element, dm_gan, target_gan, target_element):
    dm_yang = dm_gan in YANG_GAN
    target_yang = target_gan in YANG_GAN
    if target_element == dm_element:
        return "비견" if dm_yang == target_yang else "겁재"
    r = wuxing_relations(dm_element)
    if target_element == r["generates"]:
        return "식신" if dm_yang == target_yang else "상관"
    if target_element == r["controls"]:
        return "편재" if dm_yang == target_yang else "정재"
    if target_element == r["controlled_by"]:
        return "편관" if dm_yang == target_yang else "정관"
    return "편인" if dm_yang == target_yang else "정인"


def describe_pair_relation(z1, z2):
    if z1 == z2:
        return f"{z1}{z2} 동일(비화)"
    pair = frozenset({z1, z2})
    if pair in LIUHE:
        elem = LIUHE[pair]
        return f"{z1}{z2} 육합" + (f"(합화 {elem})" if elem else "")
    if pair in CHONG:
        return f"{z1}{z2} 충"
    if pair in PA:
        return f"{z1}{z2} 파"
    if pair in HAE:
        return f"{z1}{z2} 해"
    if pair == SANGHYEONG:
        return f"{z1}{z2} 상형"
    return "특이 관계 없음"


def estimate_strength(saju):
    dm = saju["day_master_wuxing"]
    w = saju["wuxing_counts"]
    r = saju["relations"]
    total = sum(w.values()) or 1

    supporting = w[dm] + w[r["generated_by"]]
    ratio = round(supporting / total * 100)

    if ratio >= 50:
        level = "신강"
        candidates = {r["generates"]: w[r["generates"]], r["controls"]: w[r["controls"]], r["controlled_by"]: w[r["controlled_by"]]}
        yongsin = min(candidates, key=candidates.get)
    elif ratio <= 30:
        level = "신약"
        yongsin = r["generated_by"]
    else:
        level = "중화"
        yongsin = min(w, key=w.get)

    return {"level": level, "ratio": ratio, "yongsin": yongsin}


def to_korean_pillar(ganzhi):
    return GAN_MAP[ganzhi[0]] + ZHI_MAP[ganzhi[1]]


def pillar_display(ganzhi):
    return f"{to_korean_pillar(ganzhi)}({ganzhi})"


def hide_gan_display(hanja_list):
    return "·".join(f"{GAN_MAP[g]}({g})" for g in hanja_list)


def wuxing_relations(element):
    gi = GENERATION_ORDER.index(element)
    ci = CONTROL_ORDER.index(element)
    return {
        "generates": GENERATION_ORDER[(gi + 1) % 5],
        "generated_by": GENERATION_ORDER[(gi - 1) % 5],
        "controls": CONTROL_ORDER[(ci + 1) % 5],
        "controlled_by": CONTROL_ORDER[(ci - 1) % 5],
    }


def compute_saju(calendar_type, year, month, day, hour, minute, time_known, is_male):
    if calendar_type == "lunar":
        lunar = Lunar.fromYmdHms(year, month, day, hour, minute, 0)
    else:
        lunar = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar()
    bazi = lunar.getEightChar()

    pillars = {
        "year": pillar_display(bazi.getYear()),
        "month": pillar_display(bazi.getMonth()),
        "day": pillar_display(bazi.getDay()),
    }
    hidden_gan = {
        "year": hide_gan_display(bazi.getYearHideGan()),
        "month": hide_gan_display(bazi.getMonthHideGan()),
        "day": hide_gan_display(bazi.getDayHideGan()),
    }
    wuxing_chars = list(bazi.getYearWuXing() + bazi.getMonthWuXing() + bazi.getDayWuXing())

    ten_gods = {
        "year": {"gan": SHISHEN_MAP[bazi.getYearShiShenGan()], "zhi": SHISHEN_MAP[bazi.getYearShiShenZhi()[0]]},
        "month": {"gan": SHISHEN_MAP[bazi.getMonthShiShenGan()], "zhi": SHISHEN_MAP[bazi.getMonthShiShenZhi()[0]]},
        "day": {"gan": "일간", "zhi": SHISHEN_MAP[bazi.getDayShiShenZhi()[0]]},
    }
    twelve_stages = {
        "year": STAGE_MAP[bazi.getYearDiShi()],
        "month": STAGE_MAP[bazi.getMonthDiShi()],
        "day": STAGE_MAP[bazi.getDayDiShi()],
    }
    zhi = {
        "year": ZHI_MAP[bazi.getYearZhi()],
        "month": ZHI_MAP[bazi.getMonthZhi()],
        "day": ZHI_MAP[bazi.getDayZhi()],
    }

    if time_known:
        pillars["time"] = pillar_display(bazi.getTime())
        hidden_gan["time"] = hide_gan_display(bazi.getTimeHideGan())
        wuxing_chars += list(bazi.getTimeWuXing())
        ten_gods["time"] = {"gan": SHISHEN_MAP[bazi.getTimeShiShenGan()], "zhi": SHISHEN_MAP[bazi.getTimeShiShenZhi()[0]]}
        twelve_stages["time"] = STAGE_MAP[bazi.getTimeDiShi()]
        zhi["time"] = ZHI_MAP[bazi.getTimeZhi()]

    wuxing_counts = {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0}
    for ch in wuxing_chars:
        wuxing_counts[WUXING_MAP[ch]] += 1

    day_master_wuxing = WUXING_MAP[bazi.getDayWuXing()[0]]

    void_zhi = {ZHI_MAP[c] for c in bazi.getDayXunKong()}
    void_pillars = [key for key, z in zhi.items() if z in void_zhi]

    da_yun = [
        {"age": d.getStartAge(), "ganzhi": to_korean_pillar(d.getGanZhi())}
        for d in bazi.getYun(1 if is_male else 0).getDaYun()
        if d.getGanZhi()
    ]

    saju = {
        "pillars": pillars,
        "hidden_gan": hidden_gan,
        "wuxing_counts": wuxing_counts,
        "day_master": GAN_MAP[bazi.getDayGan()],
        "day_master_hanja": bazi.getDayGan(),
        "day_master_wuxing": day_master_wuxing,
        "relations": wuxing_relations(day_master_wuxing),
        "time_known": time_known,
        "solar_date": lunar.getSolar().toYmd(),
        "animal": ANIMAL_MAP[ZHI_MAP[bazi.getYearZhi()]],
        "da_yun": da_yun,
        "ten_gods": ten_gods,
        "twelve_stages": twelve_stages,
        "void_pillars": void_pillars,
        "zhi_relations": analyze_zhi_relations(zhi),
        "zhi": zhi,
    }
    saju["strength"] = estimate_strength(saju)
    return saju


def generate_fortunes(saju, gender):
    p = saju["pillars"]
    w = saju["wuxing_counts"]
    r = saju["relations"]
    dm = saju["day_master_wuxing"]
    tg = saju["ten_gods"]
    ts = saju["twelve_stages"]
    st = saju["strength"]

    strongest = max(w, key=w.get)
    weakest = min(w, key=w.get)

    pillar_lines = []
    for key, label in [("year", "년주"), ("month", "월주"), ("day", "일주"), ("time", "시주")]:
        if key not in p:
            continue
        gan_sipseong = tg[key]["gan"]
        pillar_lines.append(
            f"  · {label} {p[key]} — 천간 십성: {gan_sipseong}, 지지 십성(정기 기준): {tg[key]['zhi']}, 12운성: {ts[key]}"
        )
    pillar_block = "\n".join(pillar_lines)

    void_text = ", ".join(saju["void_pillars"]) if saju["void_pillars"] else "없음"
    relation_text = ", ".join(saju["zhi_relations"]) if saju["zhi_relations"] else "특이 관계 없음"

    prompt = f"""당신은 사주명리학에 정통한 전문 상담가입니다. 아래는 실제로 계산된 사용자의 사주 원국 전체 데이터입니다.
이 데이터에 있는 사실만 근거로 삼고, 없는 사실은 지어내지 마세요. 각 항목을 쓸 때 아래 데이터 중 최소 2가지 이상의 구체적 근거(십성 이름, 12운성, 신강/신약, 공망, 지지 관계 등)를 직접 언급하며 설명하세요. 전문 용어는 피하지 말고 사용하되, 처음 등장할 때 한 번은 괄호나 짧은 설명으로 뜻을 풀어주세요.

[사주 원국]
{pillar_block}

[종합 정보]
- 일간(본인을 상징): {saju['day_master']}({saju['day_master_hanja']}, {dm})
- 오행 분포: 목 {w['목']} · 화 {w['화']} · 토 {w['토']} · 금 {w['금']} · 수 {w['수']} (가장 강한 오행: {strongest}, 가장 약한 오행: {weakest})
- 오행 상생상극 (일간 {dm} 기준): {dm}을(를) 생해주는 오행({dm}의 인성)은 {r['generated_by']}, {dm}이(가) 생해주는 오행({dm}의 식상)은 {r['generates']}, {dm}을(를) 극하는 오행({dm}의 관성)은 {r['controlled_by']}, {dm}이(가) 극하는 오행({dm}의 재성)은 {r['controls']}
- 신강/신약 판정: {st['level']} (일간을 돕는 오행 비율 {st['ratio']}%), 간단 추정 용신: {st['yongsin']}
- 공망(空亡, 기운이 비어있다고 보는 자리)에 해당하는 주: {void_text}
- 지지 관계(합·충·형·파·해): {relation_text}
- 띠: {saju['animal']}띠, 성별: {gender}

이 데이터를 근거로 분석해서, 반드시 아래 JSON 형식으로만 답하세요. 각 항목은 3~4문장 분량으로 충분히 구체적으로 작성하세요.
{{
  "personality": "일간·십성 구성·신강신약·오행 분포를 종합한 성격/기질 분석. 장점과 주의할 성향을 균형있게 포함",
  "fortune": "오늘의 전체 총운. 사주 원국(십성/공망/지지관계 등)과 오늘 하루를 연결지어 설명",
  "love": "오늘의 연애운. 일지(배우자 자리)나 관련 십성을 근거로 설명",
  "money": "오늘의 재물운. 재성(편재/정재) 관련 정보나 오행 분포를 근거로 설명",
  "advice": "신강/신약과 용신, 부족한 오행을 균형 있게 보완하기 위한 구체적 조언 (색깔, 방향, 음식, 활동 등)"
}}

같은 근거를 여러 항목에서 반복해도 되지만, 문장이 뻔한 일반론에 머물지 않도록 이번 사주 고유의 구체적 조합(예: 특정 십성과 특정 지지 관계가 겹치는 지점)을 짚어서 설명하세요.
신강/신약/중화 판정은 위에서 제시된 "{st['level']}" 결과를 모든 항목에서 정확히 그대로만 사용하고, 항목마다 다른 판정처럼 표현하지 마세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.choices[0].message.content)


def generate_daeyun_readings(saju, gender):
    dm = saju["day_master_wuxing"]
    r = saju["relations"]
    category_map = {
        dm: "비겁", r["generates"]: "식상", r["generated_by"]: "인성",
        r["controls"]: "재성", r["controlled_by"]: "관성",
    }

    lines = []
    for d in saju["da_yun"]:
        stem_element = GAN_ELEMENT[d["ganzhi"][0]]
        category = category_map[stem_element]
        lines.append(f"{d['age']}세~{d['age'] + 9}세: {d['ganzhi']} (십성 범주: {category})")
    joined = "\n".join(lines)

    prompt = f"""당신은 사주명리학에 능통하고 다정한 운세 상담가입니다.
아래는 실제로 계산된 사용자의 대운(10년 주기) 목록입니다. 각 대운 간지의 천간이 일간 대비 어떤 십성 범주에 해당하는지도 실제로 계산된 값입니다.

일간: {saju['day_master']}({dm}), 성별: {gender}

대운 목록:
{joined}

각 대운 시기별로 어떤 흐름의 시기인지 한 문장으로 해설해주세요. 반드시 아래 JSON 형식으로만 답하세요.
{{"readings": [{{"age": 8, "text": "..."}}, {{"age": 18, "text": "..."}}]}}
(age는 위 목록의 시작 나이와 정확히 같은 값을 사용하고, 목록에 있는 모든 나이에 대해 빠짐없이 작성하세요.)

십성 범주(비겁/식상/재성/관성/인성)가 상징하는 의미를 자연스럽게 반영하되,
전문 용어를 나열하지 말고 그 나이대에 맞는 현실적인 조언처럼 쉽게 작성하세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=900,
        temperature=1.0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    data = json.loads(response.choices[0].message.content)
    return {item["age"]: item["text"] for item in data.get("readings", [])}


def compute_compatibility(saju_a, saju_b):
    dm_a, dm_b = saju_a["day_master_wuxing"], saju_b["day_master_wuxing"]
    rel_a, rel_b = wuxing_relations(dm_a), wuxing_relations(dm_b)

    if dm_a == dm_b:
        relation, base = "비화", 60
    elif rel_a["generates"] == dm_b or rel_b["generates"] == dm_a:
        relation, base = "상생", 80
    else:
        relation, base = "상극", 40

    wa, wb = saju_a["wuxing_counts"], saju_b["wuxing_counts"]
    bonus = 0
    for el in GENERATION_ORDER:
        if wa[el] == 0 and wb[el] > 0:
            bonus += 4
        if wb[el] == 0 and wa[el] > 0:
            bonus += 4
        if wa[el] == 0 and wb[el] == 0:
            bonus -= 4
        if wa[el] >= 3 and wb[el] >= 3:
            bonus -= 4

    score = max(5, min(98, base + bonus))

    b_as_seen_by_a = ten_god_between(dm_a, saju_a["day_master"], saju_b["day_master"], dm_b)
    a_as_seen_by_b = ten_god_between(dm_b, saju_b["day_master"], saju_a["day_master"], dm_a)
    day_zhi_relation = describe_pair_relation(saju_a["zhi"]["day"], saju_b["zhi"]["day"])
    year_zhi_relation = describe_pair_relation(saju_a["zhi"]["year"], saju_b["zhi"]["year"])

    return {
        "score": score,
        "relation": relation,
        "day_master_a": dm_a,
        "day_master_b": dm_b,
        "b_as_seen_by_a": b_as_seen_by_a,
        "a_as_seen_by_b": a_as_seen_by_b,
        "day_zhi_relation": day_zhi_relation,
        "year_zhi_relation": year_zhi_relation,
    }


def generate_compatibility_reading(comp, saju_a, saju_b, name_a, name_b):
    wa, wb = saju_a["wuxing_counts"], saju_b["wuxing_counts"]
    wa_text = " ".join(f"{el}{wa[el]}" for el in GENERATION_ORDER)
    wb_text = " ".join(f"{el}{wb[el]}" for el in GENERATION_ORDER)

    prompt = f"""당신은 사주명리학에 정통한 전문 궁합 상담가입니다.
아래는 두 사람의 실제로 계산된 사주 데이터입니다. 이 데이터에 있는 사실만 근거로 삼고, 없는 사실은 지어내지 마세요.
전문 용어는 피하지 말고 사용하되, 처음 등장할 때 한 번은 짧게 뜻을 풀어주세요.

- {name_a}: 일간 {saju_a['day_master']}({saju_a['day_master_hanja']}, {saju_a['day_master_wuxing']}), 오행 분포 {wa_text}, 신강/신약: {saju_a['strength']['level']}
- {name_b}: 일간 {saju_b['day_master']}({saju_b['day_master_hanja']}, {saju_b['day_master_wuxing']}), 오행 분포 {wb_text}, 신강/신약: {saju_b['strength']['level']}
- 두 사람 일간의 오행 관계: {comp['relation']} ({comp['day_master_a']} - {comp['day_master_b']})
- 십성으로 본 서로의 역할: {name_b}의 일간은 {name_a}에게 십성상 '{comp['b_as_seen_by_a']}'에 해당하고, {name_a}의 일간은 {name_b}에게 '{comp['a_as_seen_by_b']}'에 해당함
- 일지(배우자궁) 관계: {comp['day_zhi_relation']}
- 년지 관계: {comp['year_zhi_relation']}
- 궁합 점수: {comp['score']}점 (100점 만점. 일간 상생상극 관계와 오행 보완 정도로 계산됨)

이 정보를 근거로 분석해서, 반드시 아래 JSON 형식으로만 답하세요. 각 항목은 3~4문장 분량으로 구체적으로 작성하세요.
{{
  "summary": "전체적인 궁합 총평. 두 일간의 관계와 십성 역할, 점수를 연결지어 설명",
  "strengths": "서로 잘 맞는 부분. 일지 관계나 오행 보완 등 구체적 근거를 들어 설명",
  "cautions": "주의하면 좋을 부분. 십성 역할이나 지지 관계(충/형/해 등)가 있다면 그 의미를 짚어 설명"
}}

점수·관계·십성 역할은 위에서 제시된 값을 그대로만 사용하고 다르게 표현하지 마세요.
일반론에 머물지 말고 이 두 사람 사주의 고유한 조합을 짚어서 설명하세요."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=900,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.choices[0].message.content)


@app.route("/")
def index():
    return render_template("index.html")


def parse_birth_payload(data):
    calendar_type = "lunar" if data.get("calendar_type") == "lunar" else "solar"

    if calendar_type == "lunar":
        year = int(data.get("lunar_year"))
        month = int(data.get("lunar_month"))
        day = int(data.get("lunar_day"))
        if not (1 <= month <= 12 and 1 <= day <= 30):
            raise ValueError
        if data.get("is_leap_month"):
            month = -month
    else:
        birth_date = datetime.strptime(data.get("birth_date", ""), "%Y-%m-%d").date()
        year, month, day = birth_date.year, birth_date.month, birth_date.day

    is_male = data.get("gender") == "male"

    birth_time = data.get("birth_time")
    time_known = bool(birth_time)
    if time_known:
        hour, minute = map(int, birth_time.split(":"))
    else:
        hour, minute = 12, 0

    return calendar_type, year, month, day, hour, minute, time_known, is_male


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    try:
        calendar_type, year, month, day, hour, minute, time_known, is_male = parse_birth_payload(data)
    except (TypeError, ValueError):
        return jsonify({"error": "생년월일을 올바르게 입력해주세요."}), 400

    gender = "남성" if is_male else "여성"

    try:
        saju = compute_saju(calendar_type, year, month, day, hour, minute, time_known, is_male)
    except Exception:
        return jsonify({"error": "생년월일을 올바르게 입력해주세요."}), 400

    try:
        fortunes = generate_fortunes(saju, gender)
    except Exception:
        return jsonify({"error": "운세를 생성하지 못했어요. 잠시 후 다시 시도해주세요."}), 502

    try:
        readings = generate_daeyun_readings(saju, gender)
        for d in saju["da_yun"]:
            d["reading"] = readings.get(d["age"], "")
    except Exception:
        for d in saju["da_yun"]:
            d["reading"] = ""

    return jsonify({"saju": saju, "fortunes": fortunes})


@app.route("/api/compatibility", methods=["POST"])
def compatibility():
    data = request.get_json(silent=True) or {}
    person_a = data.get("person_a", {})
    person_b = data.get("person_b", {})
    name_a = (person_a.get("name") or "상대방 A").strip()[:20]
    name_b = (person_b.get("name") or "상대방 B").strip()[:20]

    try:
        info_a = parse_birth_payload(person_a)
        info_b = parse_birth_payload(person_b)
    except (TypeError, ValueError):
        return jsonify({"error": "두 사람의 생년월일을 올바르게 입력해주세요."}), 400

    try:
        saju_a = compute_saju(*info_a)
        saju_b = compute_saju(*info_b)
    except Exception:
        return jsonify({"error": "생년월일을 올바르게 입력해주세요."}), 400

    comp = compute_compatibility(saju_a, saju_b)

    try:
        reading = generate_compatibility_reading(comp, saju_a, saju_b, name_a, name_b)
    except Exception:
        return jsonify({"error": "궁합 분석을 생성하지 못했어요. 잠시 후 다시 시도해주세요."}), 502

    return jsonify({
        "saju_a": saju_a,
        "saju_b": saju_b,
        "name_a": name_a,
        "name_b": name_b,
        "compatibility": comp,
        "reading": reading,
    })


if __name__ == "__main__":
    app.run(debug=True)
