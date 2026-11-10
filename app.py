''' Local run method:
1. right click personal side project
2. Open in Integrated Terminal
3. Enter py -m streamlit run app.py'''

import streamlit as st
from collections import Counter
from typing import List, Optional
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
    page_title="港式台牌計番神器 (新章複式版)",
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
# 2. 番種具體原因解說生成器 (對應最新番數表)
# ==========================================
def explain_fan_reason(fan_name: str, melds: List[Meld], pair: Optional[int], ctx: GameContext) -> str:
    if "無字花大平糊" in fan_name:
        return "全副 5 組皆為順子、無番子且無花牌（直接計 15 番）"
    if fan_name == "無字花":
        return "全副牌無番子且無花牌（直接計 5 番）"
    if fan_name == "無花":
        return "全副牌沒有摸到任何花牌或草牌（+1 番）"
    if fan_name == "無字":
        return "全副牌沒有任何番子（依備註：任何牌型如斷么、清一色等皆不走無字，照加 1 番）"
    if fan_name == "平糊":
        return "5 組面子全部皆由順子組成（+5 番）"
    if "象眼" in fan_name:
        return "以二、五或八作為對眼（每對 +2 番；嚦咕有幾多對計幾多，十六不搭亦可計）"
    if "正花" in fan_name:
        return f"花牌號碼與自己門風（{TILE_NAMES[ctx.seat_wind]}位）相符（2番/隻）"
    if "爛花" in fan_name:
        return "花牌號碼與自己門風不同（1番/隻）"
    if fan_name == "門清自摸":
        return "門前清且自摸（一摸八，合共計 8 番；嚦咕/不搭/十三么不計）"
    if fan_name == "門清":
        return "門前清（無上、碰、明槓）食人打出（+5 番；嚦咕/不搭/十三么不計）"
    if fan_name == "聽牌(門清)":
        return "門前清狀態下宣告聽牌（門清叮，合共計 10 番）"
    if fan_name == "聽牌":
        return "已宣告聽牌（叮，+5 番）"
    if fan_name == "天聽":
        return "起手未打牌即宣告聽牌（天叮，+50 番；莊家摸頭牌換牌亦可天叮）"
    if fan_name == "地聽":
        return "第一巡摸牌後即宣告聽牌（地叮，+45 番）"
    if fan_name == "對碰":
        return "手持兩對叫對碰食胡（+2 番）"
    if fan_name == "獨獨":
        return "單釣眼、邊張或卡張獨聽一隻牌（+2 番）"
    if fan_name == "假獨":
        return "多面聽牌型中可拆解為單釣或偏章（+1 番；若計暗龍則有大計大不計假獨）"
    if "花/槓上自摸" in fan_name:
        return "補花或開槓後連續自摸（1連=1番、2連=5番、3連=20番、4連=50番）"
    if fan_name == "搶槓":
        return "搶別人加槓的牌食胡（+5 番，當出沖計）"
    if "一炮" in fan_name:
        return "同一張出沖牌同時令兩家（雙響+5番）或三家（三響+15番）食胡"
    if "通天清龍" in fan_name:
        return "同一門花色 1~9 貫穿全副 17 張手牌，且頭(1)或尾(9)湊足至少三隻（+240 番）"
    if "通天雜龍" in fan_name:
        return "跨門花色 1~9 貫穿全副 17 張手牌，且頭(1)或尾(9)湊足至少三隻（+100 番）"
    if "清龍" in fan_name:
        return "同一門花色集齊 123 + 456 + 789 三組順子（明龍 10 番 / 門前暗龍 20 番）"
    if "雜龍" in fan_name:
        return "萬、筒、索三門各一組湊齊 123 + 456 + 789（明雜龍 8 番 / 暗雜龍 15 番）"
    if fan_name == "全步高":
        return "全副 5 組面子皆為順子，且起始數字依次遞增 1（+40 番）"
    if "單色步步高" in fan_name:
        return "同一門花色有 3 組順子起始數字依次遞增 1（明 10 番 / 暗 20 番）"
    if "三色步步高" in fan_name:
        return "萬、筒、索三門各有一組順子，且起始數字依次遞增 1（明 5 番 / 暗 10 番）"
    if fan_name == "全相逢":
        return "5 組順子呈「3組三相逢 + 2組相逢」3+2 結構（+30 番；依備註不重複計三暗刻/三姊妹）"
    if "三相逢" in fan_name:
        return "萬、筒、索三門各有一組相同數字的順子（明 10 番 / 暗 20 番）"
    if fan_name == "相逢":
        return "不同門花色有兩組相同數字的順子（+3 番）"
    if fan_name in ("一般高", "三般高", "四般高"):
        return "同一門花色有 2 組(5番) / 3 組(20番) / 4 組(40番) 完全相同的順子"
    if fan_name in ("兩姊妹", "小三姊妹", "大三姊妹"):
        return "同一門花色有相連數字的刻子（2連刻=5番、2連刻+相連眼=10番、3連刻=20番）"
    if fan_name in ("兩兄弟", "小三兄弟", "大三兄弟"):
        return "不同門花色有相同數字的刻子（2刻=5番、2刻+同數眼=10番、3刻=20番）"
    if "四歸" in fan_name:
        return "未開槓下用盡 4 張相同牌散落於順子/刻子/眼中（明 5/10/20 番，全暗翻倍為 10/20/40 番）"
    if fan_name == "坎坎糊":
        return "門前清 5 組暗刻（自摸或單吊食人打出，直接計 160 番，不再計對對糊 30 番）"
    if fan_name == "五暗刻":
        return "5 組暗刻/暗槓（直接計 100 番，不再計對對糊 30 番）"
    if fan_name == "大於5":
        return "全副 17 張牌全部由 6、7、8、9 數牌組成，無番子（+60 番）"
    if fan_name == "小於5":
        return "全副 17 張牌全部由 1、2、3、4 數牌組成，無番子（+60 番）"
    if fan_name == "缺5":
        return "全副牌沒有任何一張五萬、五筒或五索（+10 番）"
    if "滿庭芳" in fan_name:
        return "全帶X(60番) / 混帶X(20番)：每組數牌面子與數牌眼皆包含指定數字 X（混滿庭芳最多可疊計 3 次）"
    if fan_name == "七門齊":
        return "同時齊備「萬、筒、索、風牌、三元牌、四季(草)、四君子(花)」全部 7 門（+20 番）"
    if fan_name == "五門齊":
        return "同時齊備「萬、筒、索、風牌、三元牌」全部 5 門（+15 番）"
    if "大雞糊" in fan_name:
        return "17 隻手牌本身計唔到任何手牌番種，觸發大雞糊（+45 番，可照加自摸/叮/花/4-7-10隻內）"
    if "連對" in fan_name:
        return "嚦咕嚦咕手牌中含有同一門連續數字的對子（3/4/5/6/7連對分別加 5/10/20/30/60 番）"
    if "嚦咕減半" in fan_name:
        return "依備註：嚦咕嚦咕集齊三元、三風或四喜時，按原番數除一半計算"
    return "符合最新《港式台牌番數表》複式加番規則"


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
# 4. 標題與牌局基本設定區 (預設 1番 = $0.1)
# ==========================================
st.title("🀄 港式台牌計番神器 (新章複式版)")
st.caption("已全面更新最新番數表｜支援步步高、通天龍、混滿庭芳、七門齊、大雞糊及明暗雙軌計番")

with st.expander("⚙️ 牌局底價、風位與莊家設定 (預設 1番 = $0.1)", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        base_price = st.number_input(
            "一底金額 ($)",
            min_value=0.0,
            value=1.0,
            step=0.5,
            format="%.2f",
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
            min_value=0.01,
            value=0.10,
            step=0.10,
            format="%.2f",
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
# 5. 花牌、草牌與食胡狀態勾選區
# ==========================================
st.subheader("🌸 一、花草牌與食胡狀態")

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
        "特殊花胡直接食胡",
        options=[("none", "無 (正常手牌食胡)"), ("qiqiangyi", "七搶一 (50番)"), ("baxianguohai", "八仙過海 (100番)")],
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
        "叫胡方式 (對碰/獨獨/假獨)",
        options=[
            ("normal", "一般兩面/多面 (0番)"),
            ("duipeng", "對碰 (+2番)"),
            ("dudu", "獨獨：單釣/邊/卡張 (+2番)"),
            ("jiadu", "假獨 (+1番)"),
        ],
        format_func=lambda x: x[1],
    )[0]

with st.expander("⚡ 進階時機、槓上自摸(1/5/20/50) 與 8飛/13飛/16飛選項"):
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
        is_qianggang = st.checkbox("⚔️ 搶槓食胡 (+5番，當出沖)", value=False)
        multi_ron = st.selectbox(
            "一炮多響",
            options=[(1, "無 (單響)"), (2, "一炮雙響 (+5番)"), (3, "一炮三響 (+15番)")],
            format_func=lambda x: x[1],
        )[0]
        buda_dragon_is_concealed = st.checkbox("🐉 十六不搭若中不搭龍/三相逢，屬門前暗成 (+20番，否則+10番)", value=True)

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
# 8. 牌型組合拆解展示 & 番數具體計算方式
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
        st.success(f"🎉 食胡成功！系統已自動為你選出最高番數的拆牌組合：【{res.hand_pattern_name}】")

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
                eye_tag = "雀頭對眼 (二五八象眼 +2番)" if is_jiang else "雀頭對眼 (一般眼)"
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

        # (B) 番數的具體計算方式與原因明細表
        st.markdown("#### 🧮 (B) 「番」數的具體計算方式與觸發原因")
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
