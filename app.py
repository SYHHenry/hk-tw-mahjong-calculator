''' Local run method:
1. right click personal side project
2. Open in Integrated Terminal
3. Enter py -m streamlit run app.py'''

# ==========================================
# 港式台牌計番神器 - 手機觸控網頁介面
# Version: PTV1.0
# ==========================================

import streamlit as st
from collections import Counter
from hk_tw_mahjong_engine import (
    VERSION,
    TILE_NAMES,
    UNICODE_TILES,
    Meld,
    GameContext,
    calculate_hk_tw_mahjong,
    calculate_lazhuang_settlement,
    get_detailed_fan_reason,
)

# ==========================================
# 1. 頁面初始化與手機版 CSS 樣式優化
# ==========================================
st.set_page_config(
    page_title=f"港式台牌計番神器 {VERSION}",
    page_icon="🀄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    div.stButton > button {
        width: 100%;
        padding: 0.35rem 0.1rem;
        font-size: 1.25rem;
        font-weight: 600;
        border-radius: 8px;
    }
    .version-badge {
        display: inline-block;
        background-color: #0d6efd;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
        vertical-align: middle;
        margin-left: 8px;
    }
    .meld-box {
        display: inline-block;
        padding: 6px 12px;
        margin: 4px;
        background-color: #e9ecef;
        border: 2px solid #adb5bd;
        border-radius: 8px;
        font-size: 1.15rem;
        font-weight: bold;
        color: #198754;
    }
    .decomp-card {
        background-color: #f8f9fa;
        border: 2px solid #ced4da;
        border-radius: 10px;
        padding: 10px 8px;
        margin: 4px 0px;
        text-align: center;
    }
    .decomp-tag {
        font-size: 0.8rem;
        font-weight: 700;
        color: #495057;
        background-color: #e2e3e5;
        padding: 2px 8px;
        border-radius: 12px;
        display: inline-block;
        margin-bottom: 4px;
    }
    .decomp-eye-card {
        background-color: #fff3cd;
        border: 2px solid #ffecb5;
        border-radius: 10px;
        padding: 10px 8px;
        margin: 4px 0px;
        text-align: center;
    }
    .decomp-tiles {
        font-size: 1.75rem;
        line-height: 1.2;
        margin: 4px 0;
    }
    .decomp-names {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 600;
    }
    .formula-box {
        background-color: #e8f4f8;
        border-left: 5px solid #0d6efd;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 1.05rem;
        margin: 10px 0;
        color: #084298;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# 2. Session State 狀態管理
# ==========================================
if "hand_tiles" not in st.session_state:
    st.session_state.hand_tiles = []
if "fixed_melds" not in st.session_state:
    st.session_state.fixed_melds = []
if "lazhuang_debt" not in st.session_state:
    st.session_state.lazhuang_debt = 0.0


def add_hand_tile(tile_code: int):
    expected_len = 17 - 3 * len(st.session_state.fixed_melds)
    if len(st.session_state.hand_tiles) < expected_len:
        st.session_state.hand_tiles.append(tile_code)
        st.session_state.hand_tiles.sort()


def remove_hand_tile(index: int):
    if 0 <= index < len(st.session_state.hand_tiles):
        st.session_state.hand_tiles.pop(index)


def clear_all_tiles():
    st.session_state.hand_tiles = []
    st.session_state.fixed_melds = []


# ==========================================
# 3. 標題與牌局基本設定區 (含場風與門風雙設定)
# ==========================================
st.markdown(
    f"<h1>🀄 港式台牌計番神器 <span class='version-badge'>{VERSION}</span></h1>",
    unsafe_allow_html=True,
)
st.caption(f"版本 {VERSION}｜支援場風+門風雙正風計算｜完整第一至第五欄番種詳細解說")

with st.expander("⚙️ 牌局底價、場風（圈風）、自己門風與莊家設定", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        base_price = st.number_input(
            "一底金額 ($)",
            min_value=0.0,
            value=1.0,
            step=0.5,
            format="%.2f",
        )
        round_wind_label = st.selectbox(
            "🌍 當局場風 (圈風)",
            options=[(41, "東風圈"), (42, "南風圈"), (43, "西風圈"), (44, "北風圈")],
            format_func=lambda x: x[1],
            help="碰出場風刻子計正風 (+2番)；若場風與自己門風相同，碰出該風刻會計兩次正風 (+4番)！",
        )
        round_wind = round_wind_label[0]

        seat_wind_label = st.selectbox(
            "🪑 自己門風 (座向，決定正花號碼)",
            options=[(41, "東位 (1號正花)"), (42, "南位 (2號正花)"), (43, "西位 (3號正花)"), (44, "北位 (4號正花)")],
            format_func=lambda x: x[1],
            help="碰出自己門風刻子計正風 (+2番)；花牌正爛只看自己門風，不受場風影響。",
        )
        seat_wind = seat_wind_label[0]

    with c2:
        fan_price = st.number_input(
            "每番金額 ($)",
            min_value=0.01,
            value=0.10,
            step=0.10,
            format="%.2f",
        )
        is_dealer = st.checkbox("👑 我是莊家 (+1番)", value=False)
        dealer_streak = st.number_input(
            "連莊數 (連N加 2N+1 番)",
            min_value=0,
            max_value=20,
            value=0,
            step=1,
            disabled=not is_dealer,
        )

    if round_wind == seat_wind:
        st.info(f"💡 目前 **場風** 與 **自己門風** 皆為 **【{TILE_NAMES[round_wind]}】**：若持有【{TILE_NAMES[round_wind]}】刻子/槓，將自動計 **兩次正風（共 +4 番）**；正花仍按【{TILE_NAMES[seat_wind]}位】計算。")
    else:
        st.caption(f"💡 目前場風為【{TILE_NAMES[round_wind]}】、門風為【{TILE_NAMES[seat_wind]}】：碰【{TILE_NAMES[round_wind]}】或【{TILE_NAMES[seat_wind]}】皆算正風 (+2番)；正花按【{TILE_NAMES[seat_wind]}位】計算。")

st.markdown("---")

# ==========================================
# 4. 花牌、草牌與食胡狀態勾選區
# ==========================================
st.subheader("🌸 一、花草牌與食糊狀態")

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    good_flowers = st.number_input("正花 (2番/隻)", min_value=0, max_value=4, value=0)
with col_f2:
    bad_flowers = st.number_input("爛花 (1番/隻)", min_value=0, max_value=8, value=0)
with col_f3:
    flower_sets = st.selectbox(
        "一台花加番",
        options=[(0, "無"), (1, "一台花 (+10番)"), (2, "兩台花 (+30番)")],
        format_func=lambda x: x[1],
    )[0]

fg_col1, fg_col2, fg_col3 = st.columns(3)
with fg_col1:
    has_season_grass = st.checkbox("🌱 有四季草(春夏秋冬)", value=False, help="用於判定【七門齊 (20番)】")
with fg_col2:
    has_plant_flower = st.checkbox("🌺 有四君子花(梅蘭菊竹)", value=False, help="用於判定【七門齊 (20番)】")
with fg_col3:
    special_flower_hu = st.selectbox(
        "特殊花胡直接食糊",
        options=[("none", "無 (正常手牌食糊)"), ("qiqiangyi", "七搶一 (50番)"), ("baxianguohai", "八仙過海 (100番)")],
        format_func=lambda x: x[1],
    )[0]

col_s1, col_s2, col_s3 = st.columns(3)
with col_s1:
    is_zimo = st.checkbox("🙌 自摸 (門清自摸8番)", value=False)
with col_s2:
    riichi_type = st.selectbox(
        "聽牌 (叮) 狀態",
        options=[
            ("none", "無聽牌"),
            ("riichi", "聽牌(叮) (+5番 / 門清+10番)"),
            ("diting", "地聽 (+45番)"),
            ("tianting", "天聽 (+50番)"),
        ],
        format_func=lambda x: x[1],
    )[0]
with col_s3:
    wait_type = st.selectbox(
        "叫糊方式 (對碰/獨獨/假獨)",
        options=[
            ("normal", "一般兩面/多面 (0番)"),
            ("duipeng", "對碰 (+2番)"),
            ("dudu", "獨獨：單吊/卡窿/邊張 (+2番)"),
            ("jiadu", "假獨 (+1番)"),
        ],
        format_func=lambda x: x[1],
    )[0]

with st.expander("⚡ 進階時機、花/槓上自摸(1/5/20/50) 與 8飛/13飛/16飛選項"):
    sp1, sp2 = st.columns(2)
    with sp1:
        timing_hu = st.selectbox(
            "起手 / 檯面隻數特殊番 (4/7/10隻內)",
            options=[
                ("none", "無"),
                ("tianhu", "天糊 (+100番)"),
                ("dihu", "地糊 (+90番)"),
                ("renhu", "人糊 (+80番)"),
                ("4tiles", "四隻內 (+40番)"),
                ("7tiles", "七隻內 (+20番)"),
                ("10tiles", "十隻內 (+10番)"),
            ],
            format_func=lambda x: x[1],
        )[0]
        last_tile_hu = st.selectbox(
            "最後一隻牌 (海底 / 河底)",
            options=[("none", "無"), ("haidi", "海底撈月 (自摸 +40番)"), ("hedi", "河底撈月 (出沖 +20番)")],
            format_func=lambda x: x[1],
        )[0]
        special_wait_variant = st.selectbox(
            "特殊牌型聽牌升級 (8飛嚦咕 / 16飛不搭 / 13-14飛十三么)",
            options=[
                ("none", "一般聽牌"),
                ("8fei_ligu", "8飛嚦咕嚦咕 (55番)"),
                ("16fei_buda", "16飛十六不搭 (60番)"),
                ("13fei_13yao", "13飛十三么 (130番)"),
                ("14fei_13yao", "14飛十三么 (140番)"),
            ],
            format_func=lambda x: x[1],
        )[0]
    with sp2:
        consecutive_fk = st.selectbox(
            "花/槓上自摸累進 (1/5/20/50番)",
            options=[
                (0, "無"),
                (1, "1隻花 或 1槓自摸 (+1番)"),
                (2, "連續 2 花/槓自摸 (+5番)"),
                (3, "連續 3 花/槓自摸 (+20番)"),
                (4, "連續 4 花/槓自摸 (+50番)"),
            ],
            format_func=lambda x: x[1],
        )[0]
        is_qianggang = st.checkbox("⚔️ 搶槓食糊 (+5番，當出沖)", value=False)
        multi_ron = st.selectbox(
            "一炮多響",
            options=[(1, "無 (單響)"), (2, "一炮雙響 (+5番)"), (3, "一炮三響 (+15番)")],
            format_func=lambda x: x[1],
        )[0]
        buda_dragon_is_concealed = st.checkbox("🐉 十六不搭若中不搭龍/三相逢，屬門前暗成 (+20番，否則+10番)", value=True)

st.markdown("---")

# ==========================================
# 5. 已落地面子（副露：上/碰/明槓/暗槓）輸入區
# ==========================================
st.subheader("🧱 二、已落地面子（上 / 碰 / 槓）")
st.caption("若全副牌皆在手牌（門前清），可略過此步直接點選下方手牌。")

with st.expander("➕ 新增一組已落地牌（上、碰、明槓、暗槓）", expanded=False):
    m_col1, m_col2, m_col3 = st.columns([1.2, 1.5, 1])
    with m_col1:
        meld_action = st.selectbox(
            "動作類型",
            options=[
                ("chow_open", "上 (明順子)"),
                ("pong_open", "碰 (明刻子)"),
                ("kong_open", "明槓 (+1番)"),
                ("kong_concealed", "暗槓 (+2番，仍算門清)"),
            ],
            format_func=lambda x: x[1],
        )[0]
    with m_col2:
        if meld_action == "chow_open":
            valid_starts = [s * 10 + n for s in (1, 2, 3) for n in range(1, 8)]
            chosen_tile = st.selectbox(
                "選擇順子頭一張牌",
                options=valid_starts,
                format_func=lambda t: f"{UNICODE_TILES[t]}{TILE_NAMES[t]} ~ {TILE_NAMES[t+2]}",
            )
        else:
            all_valid_tiles = list(TILE_NAMES.keys())
            chosen_tile = st.selectbox(
                "選擇刻子/槓子牌張",
                options=all_valid_tiles,
                format_func=lambda t: f"{UNICODE_TILES[t]} {TILE_NAMES[t]}",
            )
    with m_col3:
        st.write("")
        st.write("")
        if st.button("✅ 加入此組", use_container_width=True):
            if len(st.session_state.fixed_melds) >= 5:
                st.warning("最多只能有 5 組面子！")
            else:
                if meld_action == "chow_open":
                    new_m = Meld("chow", (chosen_tile, chosen_tile + 1, chosen_tile + 2), is_open=True)
                elif meld_action == "pong_open":
                    new_m = Meld("pong", (chosen_tile,) * 3, is_open=True)
                elif meld_action == "kong_open":
                    new_m = Meld("kong", (chosen_tile,) * 4, is_open=True)
                else:
                    new_m = Meld("kong", (chosen_tile,) * 4, is_open=False)
                st.session_state.fixed_melds.append(new_m)
                st.rerun()

if st.session_state.fixed_melds:
    meld_html = ""
    for m in st.session_state.fixed_melds:
        tag = "暗槓" if (m.type == "kong" and not m.is_open) else ("明槓" if m.type == "kong" else ("上" if m.type == "chow" else "碰"))
        t_icons = "".join(f"{UNICODE_TILES[t]}" for t in m.tiles)
        t_names = "".join(f"{TILE_NAMES[t]}" for t in m.tiles)
        meld_html += f"<span class='meld-box'>{tag}: {t_icons} ({t_names})</span>"
    st.markdown(meld_html, unsafe_allow_html=True)
    if st.button("🗑️ 清空已落地面子"):
        st.session_state.fixed_melds = []
        st.rerun()

st.markdown("---")

# ==========================================
# 6. 視覺化手牌點選鍵盤 (Visual Tile Picker)
# ==========================================
expected_hand_len = 17 - 3 * len(st.session_state.fixed_melds)
current_hand_len = len(st.session_state.hand_tiles)

st.subheader(f"🀇 三、點選門前手牌（含食糊牌：{current_hand_len} / {expected_hand_len} 張）")

if st.session_state.hand_tiles:
    st.caption("👇 點擊已選的手牌按鈕可單張移除：")
    hand_cols = st.columns(min(len(st.session_state.hand_tiles), 9))
    for i, t in enumerate(st.session_state.hand_tiles):
        col_idx = i % 9
        with hand_cols[col_idx]:
            if st.button(f"{UNICODE_TILES[t]}\n{TILE_NAMES[t]}", key=f"hand_{i}"):
                remove_hand_tile(i)
                st.rerun()
else:
    st.info("請點擊下方麻雀鍵盤輸入手牌（包括最後食糊的第 17 張牌）。")

act_c1, act_c2 = st.columns(2)
with act_c1:
    if st.button("⬅️ 退格 (刪除最後一張)", use_container_width=True, disabled=not st.session_state.hand_tiles):
        st.session_state.hand_tiles.pop()
        st.rerun()
with act_c2:
    if st.button("🧹 全部重設清空", use_container_width=True):
        clear_all_tiles()
        st.rerun()

tab_wan, tab_tong, tab_suo, tab_honor = st.tabs(["萬子 (1-9萬)", "筒子 (1-9筒)", "索子 (1-9索)", "番子 (東南西北中發白)"])

with tab_wan:
    cols = st.columns(9)
    for i in range(1, 10):
        t = 10 + i
        with cols[i - 1]:
            if st.button(f"{UNICODE_TILES[t]}\n{i}萬", key=f"pick_{t}"):
                add_hand_tile(t)
                st.rerun()

with tab_tong:
    cols = st.columns(9)
    for i in range(1, 10):
        t = 20 + i
        with cols[i - 1]:
            if st.button(f"{UNICODE_TILES[t]}\n{i}筒", key=f"pick_{t}"):
                add_hand_tile(t)
                st.rerun()

with tab_suo:
    cols = st.columns(9)
    for i in range(1, 10):
        t = 30 + i
        with cols[i - 1]:
            if st.button(f"{UNICODE_TILES[t]}\n{i}索", key=f"pick_{t}"):
                add_hand_tile(t)
                st.rerun()

with tab_honor:
    honor_list = [41, 42, 43, 44, 51, 52, 53]
    cols = st.columns(7)
    for idx, t in enumerate(honor_list):
        with cols[idx]:
            if st.button(f"{UNICODE_TILES[t]}\n{TILE_NAMES[t]}", key=f"pick_{t}"):
                add_hand_tile(t)
                st.rerun()

st.markdown("---")

# ==========================================
# 7. 牌型組合拆解展示 & 番數具體計算方式
# ==========================================
st.subheader("🏆 四、所湊成的牌型組合與「番」數計算方式")

all_selected_tiles = list(st.session_state.hand_tiles) + [
    t for m in st.session_state.fixed_melds for t in m.tiles
]
over_four = [TILE_NAMES[t] for t, cnt in Counter(all_selected_tiles).items() if cnt > 4]
if over_four:
    st.error(f"⚠️ 防呆提醒：以下牌張輸入超過 4 隻，請檢查是否按錯：{', '.join(over_four)}")

ctx = GameContext(
    round_wind=round_wind,
    seat_wind=seat_wind,
    good_flowers=good_flowers,
    bad_flowers=bad_flowers,
    flower_sets=flower_sets,
    has_season_grass=has_season_grass or (flower_sets > 0),
    has_plant_flower=has_plant_flower or (flower_sets == 2),
    special_flower_hu=special_flower_hu,
    is_zimo=is_zimo,
    riichi_type=riichi_type,
    wait_type=wait_type,
    special_wait_variant=special_wait_variant,
    buda_dragon_is_concealed=buda_dragon_is_concealed,
    timing_hu=timing_hu,
    last_tile_hu=last_tile_hu,
    consecutive_flower_kong_zimo=consecutive_fk,
    is_qianggang=is_qianggang,
    multi_ron=multi_ron,
    is_dealer=is_dealer,
    dealer_streak=dealer_streak if is_dealer else 0,
    base_price=base_price,
    fan_price=fan_price,
)

if special_flower_hu != "none" or current_hand_len == expected_hand_len:
    res = calculate_hk_tw_mahjong(st.session_state.hand_tiles, st.session_state.fixed_melds, ctx)

    if res.is_valid_hu:
        st.success(f"🎉 食糊成功！系統（{VERSION}）已為你選出最高番數拆牌：【{res.hand_pattern_name}】")

        m1, m2, m3 = st.columns(3)
        m1.metric("最終總番數", f"{res.total_fan} 番")
        m2.metric("單家應付 (基本)", f"${res.base_payout:.2f}")
        if ctx.is_zimo and not ctx.is_qianggang:
            m3.metric("自摸三家總收", f"${res.base_payout * 3:.2f}")
        else:
            m3.metric("出沖應收", f"${res.base_payout:.2f}")

        # (A) 視覺化展示所湊成的牌型組合
        st.markdown("#### 🧩 (A) 你所湊成的牌型組合拆解")
        if res.hand_pattern_name == "標準牌型(5面子+1眼)" and res.best_melds:
            st.caption("系統將你的 17 張牌拆解為以下 **5 組面子（順子/刻子/槓）＋ 1 對將眼**，以取得最高番數：")
            card_cols = st.columns(3)
            for idx, m in enumerate(res.best_melds):
                if m.type == "chow":
                    type_label = f"第 {idx+1} 組｜{'明順 (上)' if m.is_open else '門前暗順'}"
                elif m.type == "pong":
                    type_label = f"第 {idx+1} 組｜{'明刻 (碰)' if m.is_open else '手牌暗刻'}"
                else:
                    type_label = f"第 {idx+1} 組｜{'明槓' if m.is_open else '暗槓'}"

                icons_str = "".join(UNICODE_TILES[t] for t in m.tiles)
                names_str = " ".join(TILE_NAMES[t] for t in m.tiles)
                with card_cols[idx % 3]:
                    st.markdown(
                        f"""
                        <div class="decomp-card">
                            <div class="decomp-tag">{type_label}</div>
                            <div class="decomp-tiles">{icons_str}</div>
                            <div class="decomp-names">{names_str}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            if res.best_pair is not None:
                p_icon = UNICODE_TILES[res.best_pair] * 2
                p_name = f"{TILE_NAMES[res.best_pair]} 對眼"
                is_jiang = (res.best_pair < 40 and (res.best_pair % 10) in (2, 5, 8))
                eye_tag = "雀頭將眼 (二五八象眼 +2番)" if is_jiang else "雀頭將眼 (一般眼)"
                with card_cols[5 % 3]:
                    st.markdown(
                        f"""
                        <div class="decomp-eye-card">
                            <div class="decomp-tag">{eye_tag}</div>
                            <div class="decomp-tiles">{p_icon}</div>
                            <div class="decomp-names">{p_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            all_icons = " ".join(f"{UNICODE_TILES[t]}({TILE_NAMES[t]})" for t in st.session_state.hand_tiles)
            st.info(f"**特殊牌型結構【{res.hand_pattern_name}】**：\n\n{all_icons}")

        # (B) 番數的具體計算方式與原因明細表 (使用 get_detailed_fan_reason 100% 精準解釋)
        st.markdown("#### 🧮 (B) 「番」數的具體計算方式與觸發原因")
        detailed_rows = []
        for fan_name, score in res.fan_breakdown:
            reason_text = get_detailed_fan_reason(fan_name, res.best_melds, res.best_pair, ctx)
            detailed_rows.append(
                {
                    "成立番種": fan_name,
                    "番數": f"+{score} 番",
                    "具體計算原因與牌例依據": reason_text,
                }
            )
        st.table(detailed_rows)

        # (C) 最終總番數與金額算式推導
        st.markdown("#### 📐 (C) 最終總番數與金額算式推導")
        fan_terms_str = " ＋ ".join(f"{score}番({name})" for name, score in res.fan_breakdown)
        effective_zimo = ctx.is_zimo and not ctx.is_qianggang
        if effective_zimo:
            payout_explain = (
                f"單家應付：<code>{res.total_fan} 番 × ${fan_price:.2f} (每番) ＋ ${base_price:.2f} (一底) ＝ ${res.base_payout:.2f}</code><br>"
                f"🙌 <b>自摸三家總收</b>：<code>${res.base_payout:.2f} × 3 家 ＝ ${res.base_payout * 3:.2f}</code>"
            )
        else:
            payout_explain = (
                f"🎯 <b>出沖單家應付</b>：<code>{res.total_fan} 番 × ${fan_price:.2f} (每番) ＋ ${base_price:.2f} (一底) ＝ ${res.base_payout:.2f}</code>"
            )

        st.markdown(
            f"""
            <div class="formula-box">
                <b>1️⃣ 總番數加總算式：</b><br>
                <code>{fan_terms_str} ＝ <b>{res.total_fan} 番</b></code>
                <hr style="margin: 8px 0; border-top: 1px solid #9ec5fe;">
                <b>2️⃣ 金額換算公式（番數 × 每番價 ＋ 底）：</b><br>
                {payout_explain}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ==========================================
        # 8. 拉莊（乘倍半 1.5x / 扣一半）互動記帳區
        # ==========================================
        st.markdown("---")
        st.subheader("💰 五、拉莊（乘倍半 1.5x / 扣一半）計算機")

        lz_col1, lz_col2 = st.columns(2)
        with lz_col1:
            prev_debt = st.number_input(
                "上一鋪累積拉莊欠款 ($)",
                min_value=0.0,
                value=float(st.session_state.lazhuang_debt),
                step=0.5,
                format="%.2f",
            )
        with lz_col2:
            lz_mode = st.selectbox(
                "今鋪拉莊狀態",
                options=[
                    ("first_win", "第一鋪起拉 (無上鋪欠款)"),
                    ("continue_win", "連贏繼續拉！(上鋪 × 1.5 + 今鋪)"),
                    ("counter_win_or_zimo", "輸家反食 / 自摸 (上鋪欠款扣一半)"),
                ],
                format_func=lambda x: x[1],
            )[0]

        if lz_mode == "first_win":
            st.info(f"📌 **今鋪起拉金額**：`${res.base_payout:.2f}`（公式：{res.total_fan}番 × ${fan_price:.2f} + ${base_price:.2f}底）")
            if st.button("📥 記下此筆金額作為下一鋪「上鋪欠款」"):
                st.session_state.lazhuang_debt = res.base_payout
                st.rerun()
        else:
            settlement = calculate_lazhuang_settlement(
                previous_debt=prev_debt,
                current_fan=res.total_fan,
                base_price=base_price,
                fan_price=fan_price,
                event_type=lz_mode,
            )
            st.json(settlement)
            if lz_mode == "continue_win":
                latest_total = settlement["拉莊後最新累積金額 (x1.5 + 今鋪)"]
                st.warning(f"🔥 **拉莊算式**：`(${prev_debt:.2f} × 1.5) ＋ ${res.base_payout:.2f} ＝ ${latest_total:.2f}`")
                if st.button("📥 更新累積拉莊欠款至下一鋪"):
                    st.session_state.lazhuang_debt = latest_total
                    st.rerun()
    else:
        st.error(f"❌ {res.hand_pattern_name}：{res.message}")
else:
    st.warning(f"⏳ 尚欠 **{expected_hand_len - current_hand_len} 張** 手牌才能進行自動拆牌與計番。")

# ==========================================
# 9. 第五欄：即時獎懲速查表（不計入食糊番數）
# ==========================================
with st.expander("📋 附錄：第五欄【即時獎懲項目】速查表（收/賠每門「底」數）"):
    st.markdown(
        f"""
        | 項目 | 獎懲標準（以目前 1底 = `${base_price:.2f}` 換算） | 觸發條件說明 |
        |:---|:---|:---|
        | **一台草** | 收每門半底（每家收 `${base_price * 0.5:.2f}`） | 集齊「春、夏、秋、冬」4 隻四季牌，即向其餘三家各收半底（花草可同時收）。 |
        | **一台花** | 收每門一底（每家收 `${base_price:.2f}`） | 集齊「梅、蘭、菊、竹」4 隻四君子牌，即向其餘三家各收一底。 |
        | **追 (番子)** | 賠每門半底（賠每家 `${base_price * 0.5:.2f}`） | 四家連續打出同一隻番子（如跟風打四隻西），最後打出第 4 隻的人賠三家各半底。 |
        | **追 (不是番子)** | 賠每門一底（賠每家 `${base_price:.2f}`） | 四家連續打出同一隻數牌（如四隻五萬），最後打出第 4 隻的人賠三家各一底。 |
        | **暗槓** | 收每門一底（每家收 `${base_price:.2f}`） | 開暗槓時，除了食糊計 2 番外，亦可即時向三家各收一底。 |
        | **123** | 賠每門一底（賠每家 `${base_price:.2f}`） | 連續打出同花色的「1、2、3」順子牌，觸發者需賠每門一底。 |
        | **圍骰** | 收每門一底（每家收 `${base_price:.2f}`） | 莊家開局擲骰時 3 粒骰子點數完全相同（如三個 4），莊家即收三家各一底。 |
        | **詐糊** | 賠每門 `$100` | 未符食糊條件而誤食糊，直接罰款賠給其餘三家每人 `$100`。 |
        """
    )
