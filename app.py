''' Local run method:
1. right click personal side project
2. Open in Integrated Terminal
3. Enter py -m streamlit run app.py'''

import streamlit as st
from collections import Counter
from typing import List, Tuple, Optional
from hk_tw_mahjong_engine import (
    TILE_NAMES,
    UNICODE_TILES,
    Meld,
    GameContext,
    calculate_hk_tw_mahjong,
    calculate_lazhuang_settlement,
)

# ==========================================
# 1. 頁面初始化與手機版 CSS 樣式優化
# ==========================================
st.set_page_config(
    page_title="港式台牌計番神器",
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
# 2. 番種具體原因解說生成器 (Explanation Helper)
# ==========================================
def explain_fan_reason(fan_name: str, melds: List[Meld], pair: Optional[int], ctx: GameContext) -> str:
    """根據番種名稱與當前拆牌組合，自動生成清楚的中文計番原因說明"""
    if "無字花平胡" in fan_name:
        return "全副 5 組皆為順子、無番子且 0 隻花（已自動合併取代：平胡3番 + 無字1番 + 無花1番）"
    if fan_name == "無字花":
        return "全副牌沒有任何番子（風牌/三元牌）且 0 隻花（已自動合併取代：無字1番 + 無花1番）"
    if fan_name == "無花":
        return "全副牌沒有摸到任何花牌（0 正花、0 爛花）"
    if fan_name == "無字":
        return "全副牌只有萬、筒、索三門，沒有任何東南西北中發白"
    if fan_name == "平胡":
        return "5 組面子全部皆由順子（Chow）組成，沒有任何刻子或槓"
    if fan_name == "將眼":
        p_name = TILE_NAMES.get(pair, "") if pair else ""
        return f"以二、五或八（本局為【{p_name}對】）作為雀頭對眼"
    if "正花" in fan_name:
        return f"花牌號碼與自己門風（{TILE_NAMES[ctx.seat_wind]}位）相符，每隻計 2 番"
    if "爛花" in fan_name:
        return "花牌號碼與自己門風不同，每隻計 1 番"
    if "一台花" in fan_name:
        return "集齊同一系列（春夏秋冬 或 梅蘭菊竹）全部 4 隻花牌"
    if "兩台花" in fan_name:
        return "集齊春夏秋冬 + 梅蘭菊竹全部 8 隻花牌直接食胡"
    if fan_name == "門清自摸":
        return "門前清（無上、無碰、無明槓）且自己摸入食胡牌（合併計 5 番，不重複計門清3+自摸1）"
    if fan_name == "門清":
        return "全副牌沒有上、碰或明槓（全部面子皆為自己手牌或暗槓），食人打出胡牌"
    if fan_name == "自摸":
        return "已有副露落地的情況下，自己摸入第 17 張食胡牌"
    if "聽牌" in fan_name:
        return "已向各家宣告「聽牌（叮）」，期間無轉章、無暗槓"
    if fan_name == "對碰":
        return "手牌手持兩對對子叫胡，食胡其中一對成為刻子"
    if fan_name == "假獨":
        return "多面聽牌型中，可拆解視為單釣眼、邊張或卡張叫胡"
    if fan_name == "獨獨":
        return "單釣一隻眼、邊張（12胡3 / 89胡7）或卡張（嵌張，如24胡3），只叫單一隻牌"
    if fan_name == "清一色":
        return "全副 17 張牌皆為同一門花色（萬、筒或索），且無任何字牌（不再重複計無字）"
    if fan_name == "混一色":
        return "全副牌由單一門序數牌（萬、筒或索）加上番子字牌組成"
    if fan_name == "五門齊":
        return "全副牌同時齊備「萬、筒、索、風牌（東南西北）、三元牌（中發白）」全部五門"
    if fan_name == "缺一門":
        return "萬、筒、索三門之中缺少了其中一門（依規則不重複計無字）"
    if fan_name == "斷么":
        return "全副牌沒有任何么九牌（1、9）及番子字牌（全部為 2～8 的序數牌）"
    if fan_name == "全帶混么":
        return "5 組面子及對眼，每一組都帶有么九牌（1、9）或番子字牌"
    if fan_name == "全帶么":
        return "5 組面子及對眼，每一組都帶有 1 或 9 的序數牌（且無番子）"
    if fan_name == "混么":
        return "全副牌全部由么九牌（1、9）及番子字牌組成（無順子）"
    if fan_name == "清么":
        return "全副牌全部由 1 及 9 的序數牌刻子與對眼組成（無字牌、無順子）"
    if fan_name == "間間胡":
        return "門前清 + 自摸 + 對對胡（即手牌 5 組暗刻自摸，直接計最高 100 番）"
    if fan_name == "對對胡":
        return "5 組面子全部皆為刻子（三隻相同）或槓子，沒有任何順子"
    if "暗刻" in fan_name:
        return "手牌中未碰出的刻子（含明槓、暗槓）達到對應組數"
    if fan_name == "全求人":
        return "全副牌 5 組面子全部已上/碰/明槓落地，餘下單釣一隻食人打出"
    if fan_name == "半求人":
        return "全副牌 5 組面子全部已上/碰/明槓落地，餘下單釣一隻自己摸入"
    if fan_name == "大三元":
        return "集齊「中、發、白」全部 3 組三元牌刻子/槓子"
    if fan_name == "小三元":
        return "集齊「中、發、白」其中 2 組刻子/槓子，並以第 3 種三元牌作對眼"
    if fan_name == "大四喜":
        return "集齊「東、南、西、北」全部 4 組風牌刻子/槓子"
    if fan_name == "小四喜":
        return "集齊「東、南、西、北」其中 3 組刻子/槓子，並以第 4 種風牌作對眼"
    if fan_name == "大三風":
        return "集齊「東、南、西、北」其中 3 組風牌刻子/槓子"
    if fan_name == "小三風":
        return "集齊「東、南、西、北」其中 2 組風牌刻子/槓子，並以另一種風牌作對眼"
    if "正風" in fan_name:
        return f"刻子/槓子與自己的門風（{TILE_NAMES[ctx.seat_wind]}位）相同"
    if "非正風" in fan_name:
        return "刻子/槓子為非自己門風的風牌"
    if "碰出" in fan_name:
        return "持有三元牌（中、發或白）刻子或槓子"
    if fan_name == "暗龍":
        return "門前手牌中集齊同一門花色的「123 + 456 + 789」三組暗順子"
    if fan_name == "明龍":
        return "集齊同一門花色的「123 + 456 + 789」三組順子（其中包含已上牌落地的順子）"
    if fan_name == "暗雜龍":
        return "門前手牌中集齊萬、筒、索三種不同花色各一組的「123 + 456 + 789」暗順子"
    if fan_name == "明雜龍":
        return "集齊萬、筒、索三種不同花色各一組的「123 + 456 + 789」順子（含已落地順子）"
    if "老少" in fan_name:
        return "同一門花色同時集齊「123 + 789」順子，或「111 + 999」刻子"
    if fan_name == "五同順":
        return "5 組面子全部為相同數字的順子（依規則不再重複計三相逢/一般高/三般高）"
    if fan_name == "四般高":
        return "4 組同一門花色且相同數字的順子（已同時構成四歸四）"
    if fan_name == "四同順":
        return "4 組不同花色但相同數字的順子（依規則不再重複計三相逢/一般高/三般高）"
    if fan_name == "三般高":
        return "3 組同一門花色且完全相同的順子"
    if fan_name == "一般高":
        return "2 組同一門花色且完全相同的順子"
    if "三相逢" in fan_name:
        return "萬、筒、索三門各有一組相同數字的順子"
    if "二相逢" in fan_name:
        return "不同門花色有兩組相同數字的順子"
    if "大三兄弟" in fan_name:
        return "萬、筒、索三門各有一組相同數字的刻子"
    if "小三兄弟" in fan_name:
        return "不同門花色有兩組相同數字的刻子，加上第三門相同數字的對眼"
    if "二兄弟" in fan_name:
        return "不同門花色有兩組相同數字的刻子"
    if fan_name == "大三姊妹":
        return "同一門花色有 3 組序數相連的刻子（例如一萬刻、二萬刻、三萬刻）"
    if fan_name == "小三姊妹":
        return "同一門花色有 2 組序數相連的刻子，加上同門相連序數的對眼"
    if "四歸四" in fan_name:
        return "未開槓的情況下用盡 4 張相同牌，且分別散落在 4 組順子中"
    if "四歸二" in fan_name:
        return "未開槓的情況下用盡 4 張相同牌，其中 2 張作對眼、另外 2 張在兩組順子中"
    if "四歸一" in fan_name:
        return "未開槓的情況下用盡 4 張相同牌，其中 3 張作刻子、另外 1 張在順子中"
    if "明槓" in fan_name:
        return "已落地的明槓（每組計 1 番）"
    if "暗槓" in fan_name:
        return "自己摸齊 4 張開出的暗槓（每組計 2 番，且仍保持門前清）"
    if "十三么" in fan_name:
        return "集齊 13 種么九番子（其中一種成對眼），外加手牌自己摸入的一組順子或暗刻"
    if "十六不搭" in fan_name:
        return "齊備東南西北中發白，且萬、筒、索每門各 3 隻互不相連（差值≥3），再加一對眼"
    if "嚦咕嚦咕" in fan_name:
        return "門前手牌由 8 對子組成（即 7 對子 + 1 組三隻相同的暗刻，不可碰出）"
    if "雞胡" in fan_name:
        return "胡出時（不計莊前）手牌只得 1 番，且非自摸、非聽牌，依港式台牌牌例升級為 10 番"
    if fan_name == "莊家":
        return "本局身為莊家，基本額外加 1 番"
    if "拉莊" in fan_name or "連" in fan_name:
        return f"莊家連莊加番：按公式（連莊數 {ctx.dealer_streak} × 2 + 1）額外加 {ctx.dealer_streak * 2 + 1} 番"
    return "符合港式十六張台牌特殊時機或牌型加番規則"


# ==========================================
# 3. Session State 狀態管理
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
# 4. 標題與牌局基本設定區
# ==========================================
st.title("🀄 港式台牌計番神器")
st.caption("支援 16 張港式新章｜自動拆牌找最高番｜詳細展示牌型拆解與番數推導算式")

with st.expander("⚙️ 牌局底價、風位與莊家設定", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        base_price = st.number_input(
            "一底金額 ($)",
            min_value=0.0,
            value=1.0,      # 預設 $1 底 (可自由改為 0.5 或 10)
            step=0.5,       # 每次加減 $0.5
            format="%.2f"
        )
        seat_wind_label = st.selectbox(
            "自己門風 (正風)",
            options=[(41, "東 (1號花)"), (42, "南 (2號花)"), (43, "西 (3號花)"), (44, "北 (4號花)")],
            format_func=lambda x: x[1],
        )
        seat_wind = seat_wind_label[0]
    with c2:
        fan_price = st.number_input(
            "每番金額 ($)",
            min_value=0.01, # 允許低至 $0.01 (一仙)
            value=0.10,     # 預設 1番 = $0.1 (一毫子)
            step=0.10,      # 每次加減 $0.1
            format="%.2f"
        )
        is_dealer = st.checkbox("我是莊家 (+1番)", value=False)
        dealer_streak = st.number_input(
            "連莊數 (連N加 2N+1 番)",
            min_value=0,
            max_value=20,
            value=0,
            step=1,
            disabled=not is_dealer,
        )


st.markdown("---")

# ==========================================
# 5. 花牌與胡牌狀態勾選區
# ==========================================
st.subheader("🌸 一、花牌與食胡狀態")

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    good_flowers = st.number_input("正花 (2番/隻)", min_value=0, max_value=4, value=0)
with col_f2:
    bad_flowers = st.number_input("爛花 (1番/隻)", min_value=0, max_value=4, value=0)
with col_f3:
    flower_sets = st.selectbox(
        "一台花 / 花胡",
        options=[(0, "無"), (1, "一台花 (10番)"), (2, "兩台花胡 (30番)")],
        format_func=lambda x: x[1],
    )[0]

is_flower_hu_only = st.checkbox("🌺 集齊 8 隻花直接食胡（兩台花胡 30 番，不計手牌）", value=(flower_sets == 2))

col_s1, col_s2 = st.columns(2)
with col_s1:
    is_zimo = st.checkbox("🙌 自摸 (連門清計5番)", value=False)
    is_riichi = st.checkbox("📢 聽牌 / 叮 (+5番)", value=False)
with col_s2:
    wait_type = st.selectbox(
        "叫胡牌型 (對碰/假獨/獨獨)",
        options=[
            ("normal", "一般兩面/多面 (0番)"),
            ("duipeng", "對碰 (+1番)"),
            ("jiadu", "假獨 (+1番)"),
            ("dudu", "獨獨：單釣/邊張/卡張 (+2番)"),
        ],
        format_func=lambda x: x[1],
    )[0]

with st.expander("⚡ 特殊時機與槓上/搶槓選項（天地人胡、海底、七只內等）"):
    sp1, sp2 = st.columns(2)
    with sp1:
        timing_special = st.selectbox(
            "起手 / 巡數特殊番",
            options=[
                ("none", "無"),
                ("tianhu", "天胡 (+100番)"),
                ("dihu", "地胡 (+80番)"),
                ("renhu", "人胡 (+80番)"),
                ("7tiles", "七只內食胡 (+20番)"),
                ("10tiles", "十只內食胡 (+10番)"),
            ],
            format_func=lambda x: x[1],
        )[0]
        is_haidi = st.checkbox("🌕 海底撈月 (最後一隻自摸 +20番)", value=False)
    with sp2:
        is_huashang = st.checkbox("🌼 花上食胡 (摸花自摸 +1番)", value=False)
        kong_special = st.selectbox(
            "槓上 / 搶槓狀態",
            options=[
                ("none", "無"),
                ("gangshang", "槓上自摸 (+1番)"),
                ("qianggang", "搶槓食胡 (+1番，當出沖)"),
                ("gang_on_gang", "槓上槓自摸 (+30番)"),
                ("qiang_gang_on_gang", "搶槓上槓食胡 (+30番)"),
            ],
            format_func=lambda x: x[1],
        )[0]

st.markdown("---")

# ==========================================
# 6. 已落地面子（副露：上/碰/明槓/暗槓）輸入區
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
# 7. 視覺化手牌點選鍵盤 (Visual Tile Picker)
# ==========================================
expected_hand_len = 17 - 3 * len(st.session_state.fixed_melds)
current_hand_len = len(st.session_state.hand_tiles)

st.subheader(f"🀇 三、點選門前手牌（含食胡牌：{current_hand_len} / {expected_hand_len} 張）")

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
    st.info("請點擊下方麻雀鍵盤輸入手牌（包括最後食胡的第 17 張牌）。")

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
# 8. 【全新升級】牌型組合拆解展示 & 番數具體計算方式
# ==========================================
st.subheader("🏆 四、所湊成的牌型組合與「番」數計算方式")

all_selected_tiles = list(st.session_state.hand_tiles) + [
    t for m in st.session_state.fixed_melds for t in m.tiles
]
over_four = [TILE_NAMES[t] for t, cnt in Counter(all_selected_tiles).items() if cnt > 4]
if over_four:
    st.error(f"⚠️ 防呆提醒：以下牌張輸入超過 4 隻，請檢查是否按錯：{', '.join(over_four)}")

ctx = GameContext(
    seat_wind=seat_wind,
    good_flowers=good_flowers,
    bad_flowers=bad_flowers,
    flower_sets=flower_sets,
    is_flower_hu_only=is_flower_hu_only,
    is_zimo=is_zimo,
    is_riichi=is_riichi,
    wait_type=wait_type,
    is_tianhu=(timing_special == "tianhu"),
    is_dihu=(timing_special == "dihu"),
    is_renhu=(timing_special == "renhu"),
    within_tiles=7 if timing_special == "7tiles" else (10 if timing_special == "10tiles" else 0),
    is_haidi=is_haidi,
    is_huashang=is_huashang,
    is_gangshang=(kong_special == "gangshang"),
    is_qianggang=(kong_special == "qianggang"),
    is_gang_on_gang=(kong_special == "gang_on_gang"),
    is_qiang_gang_on_gang=(kong_special == "qiang_gang_on_gang"),
    is_dealer=is_dealer,
    dealer_streak=dealer_streak if is_dealer else 0,
    base_price=base_price,
    fan_price=fan_price,
)

if is_flower_hu_only or current_hand_len == expected_hand_len:
    res = calculate_hk_tw_mahjong(st.session_state.hand_tiles, st.session_state.fixed_melds, ctx)

    if res.is_valid_hu:
        st.success(f"🎉 食胡成功！系統已自動為你選出最高番數的拆牌組合：【{res.hand_pattern_name}】")

        # 1. 頂部三大總結指標
        m1, m2, m3 = st.columns(3)
        m1.metric("最終總番數", f"{res.total_fan} 番")
        m2.metric("單家應付 (基本)", f"${res.base_payout:.1f}")
        if ctx.is_zimo and not (ctx.is_qianggang or ctx.is_qiang_gang_on_gang):
            m3.metric("自摸三家總收", f"${res.base_payout * 3:.1f}")
        else:
            m3.metric("出沖應收", f"${res.base_payout:.1f}")

        # 2. 視覺化展示所湊成的牌型組合 (5組面子 + 1對眼 卡片)
        st.markdown("#### 🧩 (A) 你所湊成的牌型組合拆解")
        if res.hand_pattern_name == "標準牌型(5面子+1眼)" and res.best_melds:
            st.caption("系統將你的 17 張牌拆解為以下 **5 組面子（順子/刻子/槓）＋ 1 對雀頭眼**，以取得最高番數：")
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
                eye_tag = "雀頭對眼 (二五八將眼 +1番)" if is_jiang else "雀頭對眼 (一般眼)"
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
            # 特殊牌型（十三么 / 十六不搭 / 嚦咕嚦咕 / 兩台花）展示
            all_icons = " ".join(f"{UNICODE_TILES[t]}({TILE_NAMES[t]})" for t in st.session_state.hand_tiles)
            st.info(f"**特殊牌型結構【{res.hand_pattern_name}】**：\n\n{all_icons}")

        # 3. 番數的具體計算方式與原因明細表
        st.markdown("#### 🧮 (B) 「番」數的具體計算方式與觸發原因")
        st.caption("以下逐項列出本局成立的番種、所加番數，以及為何這樣計算（已自動排除重複計算的小番）：")

        detailed_rows = []
        for fan_name, score in res.fan_breakdown:
            reason_text = explain_fan_reason(fan_name, res.best_melds, res.best_pair, ctx)
            detailed_rows.append(
                {
                    "成立番種": fan_name,
                    "番數": f"+{score} 番",
                    "具體計算原因與牌例依據": reason_text,
                }
            )
        st.table(detailed_rows)

        # 4. 最終番數與金額完整算式推導盒
        st.markdown("#### 📐 (C) 最終總番數與金額算式推導")
        fan_terms_str = " ＋ ".join(f"{score}番({name})" for name, score in res.fan_breakdown)
        effective_zimo = ctx.is_zimo and not (ctx.is_qianggang or ctx.is_qiang_gang_on_gang)
        if effective_zimo:
            payout_explain = (
                f"單家應付：<code>{res.total_fan} 番 × ${fan_price:.1f} (每番) ＋ ${base_price:.1f} (一底) ＝ ${res.base_payout:.1f}</code><br>"
                f"🙌 <b>自摸三家總收</b>：<code>${res.base_payout:.1f} × 3 家 ＝ ${res.base_payout * 3:.1f}</code>"
            )
        else:
            payout_explain = (
                f"🎯 <b>出沖單家應付</b>：<code>{res.total_fan} 番 × ${fan_price:.1f} (每番) ＋ ${base_price:.1f} (一底) ＝ ${res.base_payout:.1f}</code>"
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
        # 9. 拉莊（乘倍半 1.5x / 扣一半）互動記帳區
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
            st.info(f"📌 **今鋪起拉金額**：`${res.base_payout:.1f}`（公式：{res.total_fan}番 × ${fan_price} + ${base_price}底）")
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
                st.warning(
                    f"🔥 **拉莊算式**：`(${prev_debt:.1f} × 1.5) ＋ ${res.base_payout:.1f} ＝ ${latest_total:.1f}`"
                )
                if st.button("📥 更新累積拉莊欠款至下一鋪"):
                    st.session_state.lazhuang_debt = latest_total
                    st.rerun()
    else:
        st.error(f"❌ {res.hand_pattern_name}：{res.message}")
else:
    st.warning(f"⏳ 尚欠 **{expected_hand_len - current_hand_len} 張** 手牌才能進行自動拆牌與計番。")
