from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations, permutations
from typing import List, Tuple, Dict, Optional, Set

# ==========================================
# 1. 牌張編碼定義與輔助轉換函數
# ==========================================
TILE_NAMES: Dict[int, str] = {
    **{10 + i: f"{i}萬" for i in range(1, 10)},
    **{20 + i: f"{i}筒" for i in range(1, 10)},
    **{30 + i: f"{i}索" for i in range(1, 10)},
    41: "東", 42: "南", 43: "西", 44: "北",
    51: "中", 52: "發", 53: "白"
}

UNICODE_TILES: Dict[int, str] = {
    **{10 + i: chr(0x1F007 + i - 1) for i in range(1, 10)},
    **{20 + i: chr(0x1F019 + i - 1) for i in range(1, 10)},
    **{30 + i: chr(0x1F010 + i - 1) for i in range(1, 10)},
    41: "🀀", 42: "🀁", 43: "🀂", 44: "🀃",
    51: "🀄", 52: "🀅", 53: "🀆"
}

WINDS = {41, 42, 43, 44}
DRAGONS = {51, 52, 53}
HONORS = WINDS | DRAGONS
TERMINALS = {11, 19, 21, 29, 31, 39}
YAOJIU = TERMINALS | HONORS


def is_suit(tile: int) -> bool:
    return 11 <= tile <= 39


def get_suit(tile: int) -> int:
    """1=萬, 2=筒, 3=索, 4=風, 5=三元"""
    return tile // 10


def get_num(tile: int) -> int:
    """序數 1~9，字牌回傳 0"""
    return tile % 10 if is_suit(tile) else 0


@dataclass(frozen=True)
class Meld:
    """
    面子結構:
    - type: 'chow' (順子), 'pong' (刻子), 'kong' (槓子)
    - tiles: 例如 (11, 12, 13) 或 (41, 41, 41)
    - is_open: True=已落地(上/碰/明槓), False=門前手牌(暗順/暗刻/暗槓)
    """
    type: str
    tiles: Tuple[int, ...]
    is_open: bool = False


@dataclass
class GameContext:
    """對應新番數表的所有環境與狀態參數"""
    seat_wind: int = 41                     # 正風 (41=東, 42=南, 43=西, 44=北)
    winning_tile: Optional[int] = None      # 食胡的那張牌 (可選，用於精確判別暗番與坎坎糊單吊)

    # 花牌與草牌狀態
    good_flowers: int = 0                   # 正花數量 (+2番/隻)
    bad_flowers: int = 0                    # 爛花數量 (+1番/隻)
    flower_sets: int = 0                    # 一台花加番 (0=無, 1=一台花10番, 2=兩台花30番)
    has_season_grass: bool = False          # 持有四季草(春夏秋冬)至少1隻 (用於七門齊)
    has_plant_flower: bool = False          # 持有四君子花(梅蘭菊竹)至少1隻 (用於七門齊)
    special_flower_hu: str = "none"         # 'none', 'qiqiangyi'(七搶一 50番), 'baxianguohai'(八仙過海 100番)

    # 食胡與聽牌(叮)狀態
    is_zimo: bool = False                   # 自摸 (+1番；門清自摸合共 8番)
    riichi_type: str = "none"               # 'none', 'riichi'(聽牌 5 / 門清聽牌 10), 'tianting'(天聽 50), 'diting'(地聽 45)
    wait_type: str = "normal"               # 'normal'(兩面/多面), 'duipeng'(對碰 2番), 'jiadu'(假獨 1番), 'dudu'(獨獨 2番)
    special_wait_variant: str = "none"      # 'none', '8fei_ligu'(8飛嚦咕 55), '16fei_buda'(16飛不搭 60), '13fei_13yao'(13飛十三么 130), '14fei_13yao'(14飛十三么 140)
    buda_dragon_is_concealed: bool = True   # 十六不搭若中不搭龍/三相逢，是否為暗(20番)而非食胡第9隻(明10番)

    # 特殊時機番 (天地人胡、4/7/10隻內、海底/河底)
    timing_hu: str = "none"                 # 'none', 'tianhu'(天糊 100), 'dihu'(地糊 90), 'renhu'(人糊 80), '4tiles'(四隻內 40), '7tiles'(七隻內 20), '10tiles'(十隻內 10)
    last_tile_hu: str = "none"              # 'none', 'haidi'(海底撈月 40), 'hedi'(河底撈月 20)

    # 花/槓上自摸 & 搶槓 & 一炮多響
    consecutive_flower_kong_zimo: int = 0   # 0=無, 1=1番, 2=5番, 3=20番, 4=50番 (花/槓上自摸 1/5/20/50)
    is_qianggang: bool = False              # 搶槓 (+5番，當出沖)
    multi_ron: int = 1                      # 1=單響, 2=一炮雙響(+5番), 3=一炮三響(+15番)

    # 莊家與連莊設定
    is_dealer: bool = False                 # 莊家 (+1番)
    dealer_streak: int = 0                  # 連莊數 (連N加 2N+1 番)

    # 計錢設定
    base_price: float = 1.0                 # 一底金額 (預設 $1.0)
    fan_price: float = 0.1                  # 每番金額 (預設 $0.1)


# ==========================================
# 2. 特殊牌型判別器 (十三么 / 十六不搭 / 嚦咕嚦咕 / 通天龍)
# ==========================================

def check_shisanyao(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[Tuple[int, List[Meld]]]:
    """檢查【十三么 (120番) / 13飛 (130番) / 14飛 (140番)】"""
    if any(m.is_open for m in fixed_melds):
        return None
    if len(fixed_melds) > 1 or (len(fixed_melds) == 1 and fixed_melds[0].type == 'kong'):
        return None
    counts = Counter(hand_tiles)
    if len(fixed_melds) == 1:
        if not all(counts[y] >= 1 for y in YAOJIU):
            return None
        pair_candidates = [y for y in YAOJIU if counts[y] == 2]
        if len(pair_candidates) == 1 and sum(counts.values()) == 14:
            return pair_candidates[0], [fixed_melds[0]]
        return None
    if sum(counts.values()) != 17 or not all(counts[y] >= 1 for y in YAOJIU):
        return None
    rem = counts.copy()
    for y in YAOJIU:
        rem[y] -= 1
        if rem[y] == 0:
            del rem[y]
    for pair_tile in list(rem.keys()):
        if pair_tile in YAOJIU:
            rem[pair_tile] -= 1
            leftover = sorted(t for t, c in rem.items() for _ in range(c))
            rem[pair_tile] += 1
            if len(leftover) == 3:
                if leftover[0] == leftover[1] == leftover[2]:
                    return pair_tile, [Meld('pong', tuple(leftover), is_open=False)]
                if is_suit(leftover[0]) and leftover[1] == leftover[0] + 1 and leftover[2] == leftover[0] + 2:
                    return pair_tile, [Meld('chow', tuple(leftover), is_open=False)]
    return None


def check_shiliubuda(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[Tuple[int, Dict[int, Tuple[int, int, int]]]]:
    """檢查【十六不搭 (50番) / 16飛十六不搭 (60番)】並回傳對眼與三門不搭組合"""
    if fixed_melds or len(hand_tiles) != 17:
        return None
    counts = Counter(hand_tiles)
    if not all(counts[h] >= 1 for h in HONORS):
        return None
    if len(counts) != 16 or max(counts.values()) != 2:
        return None
    pair_tile = next(t for t, c in counts.items() if c == 2)
    suit_sets: Dict[int, Tuple[int, int, int]] = {}
    for suit in (1, 2, 3):
        suit_tiles = tuple(sorted(t % 10 for t in counts.keys() if t // 10 == suit))
        if len(suit_tiles) != 3:
            return None
        if (suit_tiles[1] - suit_tiles[0] < 3) or (suit_tiles[2] - suit_tiles[1] < 3):
            return None
        suit_sets[suit] = suit_tiles
    return pair_tile, suit_sets


def check_liguligu(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[Tuple[List[int], int]]:
    """檢查【嚦咕嚦咕 (45番) / 8飛嚦咕嚦咕 (55番)】，回傳 (8個對子的牌代碼列表, 刻子牌代碼)"""
    if fixed_melds or len(hand_tiles) != 17:
        return None
    counts = Counter(hand_tiles)
    odd_tiles = [t for t, c in counts.items() if c % 2 == 1]
    if len(odd_tiles) != 1 or counts[odd_tiles[0]] != 3:
        return None
    triplet_tile = odd_tiles[0]
    eight_pairs: List[int] = [triplet_tile]
    for t, c in sorted(counts.items()):
        if t == triplet_tile:
            continue
        if c == 2:
            eight_pairs.append(t)
        elif c == 4:
            eight_pairs.extend([t, t])
        else:
            return None
    if len(eight_pairs) == 8:
        return sorted(eight_pairs), triplet_tile
    return None


def check_tongtian_dragon(melds: List[Meld], pair: int) -> Optional[str]:
    """
    檢查【通天清龍 (240番) / 通天雜龍 (100番)】：
    - 17 張全為數牌 (無番子、無槓子)，包含 123 + 456 + 789 貫穿 1~9。
    - 備註規定：「通天龍必須頭/尾三隻 i.e 11223334455667788 則不是」
      即數字 1 (頭) 或數字 9 (尾) 在全副牌中必須至少有 3 張，且不可有非頭尾(2~8)的刻子破壞巨龍連貫。
    """
    all_tiles = [t for m in melds for t in m.tiles] + [pair, pair]
    if any(not is_suit(t) for t in all_tiles) or any(m.type == 'kong' for m in melds):
        return None
    chows = [m for m in melds if m.type == 'chow']
    pongs = [m for m in melds if m.type == 'pong']
    if len(pongs) > 1:
        return None
    if len(pongs) == 1 and get_num(pongs[0].tiles[0]) not in (1, 9):
        return None

    has_123 = any(get_num(m.tiles[0]) == 1 for m in chows)
    has_456 = any(get_num(m.tiles[0]) == 4 for m in chows)
    has_789 = any(get_num(m.tiles[0]) == 7 for m in chows)
    if not (has_123 and has_456 and has_789):
        return None

    num_counts = Counter(get_num(t) for t in all_tiles)
    if not all(num_counts[n] >= 1 for n in range(1, 10)):
        return None

    # 必須頭(1)或尾(9)至少三隻，且對眼或刻子必須鎮住頭(1)或尾(9)
    has_head_three = (num_counts[1] >= 3) and (get_num(pair) == 1 or any(get_num(p.tiles[0]) == 1 for p in pongs))
    has_tail_three = (num_counts[9] >= 3) and (get_num(pair) == 9 or any(get_num(p.tiles[0]) == 9 for p in pongs))
    if not (has_head_three or has_tail_three):
        return None

    suits = {get_suit(t) for t in all_tiles}
    return "通天清龍" if len(suits) == 1 else "通天雜龍"


# ==========================================
# 3. 標準牌型拆解器 (5組面子 + 1對眼)
# ==========================================

def find_standard_decompositions(
    hand_tiles: List[int],
    fixed_melds: List[Meld]
) -> List[Tuple[List[Meld], int]]:
    counts = Counter(hand_tiles)
    needed_melds = 5 - len(fixed_melds)
    if needed_melds < 0:
        return []
    raw_decomps: List[Tuple[List[Meld], int]] = []

    def backtrack(current_counts: Counter, current_melds: List[Meld], current_pair: int):
        if len(current_melds) == needed_melds:
            raw_decomps.append((list(current_melds), current_pair))
            return
        first_tile = min(t for t, c in current_counts.items() if c > 0)
        if current_counts[first_tile] >= 3:
            current_counts[first_tile] -= 3
            current_melds.append(Meld('pong', (first_tile,) * 3, is_open=False))
            backtrack(current_counts, current_melds, current_pair)
            current_melds.pop()
            current_counts[first_tile] += 3
        if is_suit(first_tile) and get_num(first_tile) <= 7:
            t2, t3 = first_tile + 1, first_tile + 2
            if current_counts[t2] > 0 and current_counts[t3] > 0:
                current_counts[first_tile] -= 1
                current_counts[t2] -= 1
                current_counts[t3] -= 1
                current_melds.append(Meld('chow', (first_tile, t2, t3), is_open=False))
                backtrack(current_counts, current_melds, current_pair)
                current_melds.pop()
                current_counts[first_tile] += 1
                current_counts[t2] += 1
                current_counts[t3] += 1

    for pair_t in sorted(counts.keys()):
        if counts[pair_t] >= 2:
            counts[pair_t] -= 2
            backtrack(counts, [], pair_t)
            counts[pair_t] += 2

    unique_results: List[Tuple[List[Meld], int]] = []
    seen = set()
    for hand_melds, pair in raw_decomps:
        sig = (tuple(sorted((m.type, m.tiles, m.is_open) for m in hand_melds)), pair)
        if sig not in seen:
            seen.add(sig)
            unique_results.append((list(fixed_melds) + hand_melds, pair))
    return unique_results


# ==========================================
# 4. 共通狀態番與大雞糊/莊家結算器
# ==========================================

def evaluate_context_and_flower_fans(
    ctx: GameContext,
    is_menqing: bool,
    is_special_non_menqing_hand: bool = False,
    skip_no_flower: bool = False
) -> List[Tuple[str, int]]:
    """
    計算花牌、門清、自摸、聽牌(叮)、叫胡型態、時機與槓上番。
    備註規定：「嚦咕, 不搭, 十三么不計門清一摸八, 門清叮」(由 is_special_non_menqing_hand 控制)
    """
    fans: List[Tuple[str, int]] = []
    total_flowers = ctx.good_flowers + ctx.bad_flowers + (ctx.flower_sets * 4)

    # 1. 花牌番
    if ctx.flower_sets == 2 and ctx.special_flower_hu == "none":
        fans.append(("兩台花", 30))
    elif ctx.flower_sets == 1:
        fans.append(("一台花", 10))

    if ctx.good_flowers > 0:
        fans.append((f"正花 x{ctx.good_flowers}", 2 * ctx.good_flowers))
    if ctx.bad_flowers > 0:
        fans.append((f"爛花 x{ctx.bad_flowers}", 1 * ctx.bad_flowers))

    if not skip_no_flower and total_flowers == 0 and ctx.flower_sets == 0 and not ctx.has_season_grass and not ctx.has_plant_flower:
        fans.append(("無花", 1))

    # 2. 門清 / 門清自摸(8) / 自摸(1)
    effective_zimo = ctx.is_zimo and not ctx.is_qianggang
    if is_special_non_menqing_hand:
        # 嚦咕、不搭、十三么不計門清、不計一摸八(8)，若自摸只計自摸(1)
        if effective_zimo:
            fans.append(("自摸", 1))
    else:
        if is_menqing and effective_zimo:
            fans.append(("門清自摸", 8))
        else:
            if is_menqing:
                fans.append(("門清", 5))
            if effective_zimo:
                fans.append(("自摸", 1))

    # 3. 聽牌(叮) / 聽牌(門清) / 天聽 / 地聽
    if ctx.riichi_type == "tianting":
        fans.append(("天聽", 50))
    elif ctx.riichi_type == "diting":
        fans.append(("地聽", 45))
    elif ctx.riichi_type == "riichi":
        if is_menqing and not is_special_non_menqing_hand:
            fans.append(("聽牌(門清)", 10))
        else:
            fans.append(("聽牌", 5))

    # 4. 對碰(2) / 獨獨(2) / 假獨(1)
    if ctx.wait_type == "duipeng":
        fans.append(("對碰", 2))
    elif ctx.wait_type == "dudu":
        fans.append(("獨獨", 2))
    elif ctx.wait_type == "jiadu":
        fans.append(("假獨", 1))

    # 5. 天地人糊 & 4/7/10隻內 & 海底/河底
    timing_map = {
        "tianhu": ("天糊", 100),
        "dihu": ("地糊", 90),
        "renhu": ("人糊", 80),
        "4tiles": ("四隻內", 40),
        "7tiles": ("七隻內", 20),
        "10tiles": ("十隻內", 10),
    }
    if ctx.timing_hu in timing_map:
        fans.append(timing_map[ctx.timing_hu])

    if ctx.last_tile_hu == "haidi":
        fans.append(("海底撈月", 40))
    elif ctx.last_tile_hu == "hedi":
        fans.append(("河底撈月", 20))

    # 6. 花/槓上自摸 (1/5/20/50) & 搶槓(5) & 一炮雙響(5)/三響(15)
    fk_map = {1: 1, 2: 5, 3: 20, 4: 50}
    if ctx.consecutive_flower_kong_zimo in fk_map:
        cnt = ctx.consecutive_flower_kong_zimo
        fans.append((f"花/槓上自摸 ({cnt}連)", fk_map[cnt]))

    if ctx.is_qianggang:
        fans.append(("搶槓", 5))

    if ctx.multi_ron == 2:
        fans.append(("一炮雙響", 5))
    elif ctx.multi_ron == 3:
        fans.append(("一炮三響", 15))

    return fans


def finalize_with_dealer(
    fans: List[Tuple[str, int]],
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """加上莊家與連莊番數"""
    if ctx.is_dealer:
        fans.append(("莊家", 1))
        if ctx.dealer_streak > 0:
            streak_bonus = ctx.dealer_streak * 2 + 1
            fans.append((f"連{ctx.dealer_streak} (拉莊)", streak_bonus))
    return sum(s for _, s in fans), fans


# ==========================================
# 5. 標準牌型 (5面子+1眼) 完整計番引擎
# ==========================================

def evaluate_standard_decomposition(
    melds: List[Meld],
    pair: int,
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """
    根據新番數表與 14 條備註，評估標準 5組面子+1對眼 的所有番種。
    """
    hand_pattern_fans: List[Tuple[str, int]] = []

    all_tiles = [t for m in melds for t in m.tiles] + [pair, pair]
    non_kong_tiles = [t for m in melds if m.type != 'kong' for t in m.tiles] + [pair, pair]
    tile_counts_non_kong = Counter(non_kong_tiles)

    suits_present = {get_suit(t) for t in all_tiles if is_suit(t)}
    has_winds = any(t in WINDS for t in all_tiles)
    has_dragons = any(t in DRAGONS for t in all_tiles)
    has_honors = has_winds or has_dragons

    total_flowers = ctx.good_flowers + ctx.bad_flowers + (ctx.flower_sets * 4)
    has_any_flower = (total_flowers > 0) or ctx.has_season_grass or ctx.has_plant_flower

    chows = [m for m in melds if m.type == 'chow']
    pongs = [m for m in melds if m.type in ('pong', 'kong')]
    kongs = [m for m in melds if m.type == 'kong']

    is_pinghu = (len(chows) == 5)
    is_menqing = all(not m.is_open for m in melds)
    effective_zimo = ctx.is_zimo and not ctx.is_qianggang

    # --------------------------------------------------
    # A. 無字 / 無花 / 無字花 / 平糊 / 無字花大平糊
    # 備註規定：「任何牌型都不會走無字 e.g. 斷么, 清一色 etc」
    # --------------------------------------------------
    skip_no_flower = False
    if not has_any_flower and not has_honors and is_pinghu:
        hand_pattern_fans.append(("無字花大平糊", 15))
        skip_no_flower = True
    elif not has_any_flower and not has_honors:
        hand_pattern_fans.append(("無字花", 5))
        skip_no_flower = True
        if is_pinghu:
            hand_pattern_fans.append(("平糊", 5))
    else:
        if is_pinghu:
            hand_pattern_fans.append(("平糊", 5))
        if not has_honors:
            hand_pattern_fans.append(("無字", 1))

    # --------------------------------------------------
    # B. 象眼 (2番)：以一對 2、5 或 8 做眼
    # --------------------------------------------------
    if is_suit(pair) and get_num(pair) in (2, 5, 8):
        hand_pattern_fans.append(("象眼", 2))

    # --------------------------------------------------
    # C. 明槓 (1番) / 暗槓 (2番)
    # --------------------------------------------------
    open_kongs = sum(1 for m in kongs if m.is_open)
    concealed_kongs = sum(1 for m in kongs if not m.is_open)
    if open_kongs > 0:
        hand_pattern_fans.append((f"明槓 x{open_kongs}", 1 * open_kongs))
    if concealed_kongs > 0:
        hand_pattern_fans.append((f"暗槓 x{concealed_kongs}", 2 * concealed_kongs))

    # --------------------------------------------------
    # D. 正風(2) / 爛風(1) / 三元牌(2) & 小/大三風、小/大四喜、小/大三元
    # --------------------------------------------------
    dragon_pongs = [m for m in pongs if m.tiles[0] in DRAGONS]
    wind_pongs = [m for m in pongs if m.tiles[0] in WINDS]

    if len(dragon_pongs) == 3:
        hand_pattern_fans.append(("大三元", 60))
    elif len(dragon_pongs) == 2 and pair in DRAGONS:
        hand_pattern_fans.append(("小三元", 30))
    else:
        for m in dragon_pongs:
            hand_pattern_fans.append((f"三元牌({TILE_NAMES[m.tiles[0]]})", 2))

    if len(wind_pongs) == 4:
        hand_pattern_fans.append(("大四喜", 100))
    elif len(wind_pongs) == 3 and pair in WINDS:
        hand_pattern_fans.append(("小四喜", 80))
    elif len(wind_pongs) == 3:
        hand_pattern_fans.append(("大三風", 40))
    elif len(wind_pongs) == 2 and pair in WINDS:
        hand_pattern_fans.append(("小三風", 20))
    else:
        for m in wind_pongs:
            w = m.tiles[0]
            if w == ctx.seat_wind:
                hand_pattern_fans.append((f"正風({TILE_NAMES[w]})", 2))
            else:
                hand_pattern_fans.append((f"爛風({TILE_NAMES[w]})", 1))

    # --------------------------------------------------
    # E. 全相逢 (30番) 預先檢查 (備註：全相逢必須3+2, if 555666777則不計三暗刻三姊妹)
    # --------------------------------------------------
    chow_by_num: Dict[int, List[Meld]] = {}
    for m in chows:
        chow_by_num.setdefault(get_num(m.tiles[0]), []).append(m)

    is_quanxiangfeng = False
    if len(chows) == 5 and len(chow_by_num) == 2:
        counts_per_num = sorted(len(v) for v in chow_by_num.values())
        # 必須為 3 組同數順子 (跨門相逢) + 2 組同數順子 (跨門相逢)
        suits_per_num = [len({get_suit(m.tiles[0]) for m in v}) for v in chow_by_num.values()]
        if counts_per_num == [2, 3] and sorted(suits_per_num) == [2, 3]:
            is_quanxiangfeng = True
            hand_pattern_fans.append(("全相逢", 30))

    # --------------------------------------------------
    # F. 對對糊(30) / 兩~五暗刻(5/10/30/100) / 坎坎糊(160) / 全求人(20) / 半求人(10)
    # 備註規定：「五暗刻, 坎坎糊不再計算對對糊, 坎坎糊可以食單吊打出」
    # --------------------------------------------------
    concealed_pongs = [m for m in pongs if not m.is_open]
    # 若全為刻子且門前清：自摸 或 單吊(獨獨)食人打出 -> 坎坎糊 (160番)
    is_kankanhu = (len(pongs) == 5 and is_menqing and (effective_zimo or ctx.wait_type == "dudu"))

    if is_kankanhu:
        hand_pattern_fans.append(("坎坎糊", 160))
    elif len(concealed_pongs) == 5:
        hand_pattern_fans.append(("五暗刻", 100))
    else:
        if len(pongs) == 5:
            hand_pattern_fans.append(("對對糊", 30))
        if not is_quanxiangfeng:
            if len(concealed_pongs) == 4:
                hand_pattern_fans.append(("四暗刻", 30))
            elif len(concealed_pongs) == 3:
                hand_pattern_fans.append(("三暗刻", 10))
            elif len(concealed_pongs) == 2:
                hand_pattern_fans.append(("兩暗刻", 5))

    if all(m.is_open and m.type != 'kong' or (m.type == 'kong' and m.is_open) for m in melds):
        if effective_zimo:
            hand_pattern_fans.append(("半求人", 10))
        else:
            hand_pattern_fans.append(("全求人", 20))

    # --------------------------------------------------
    # G. 通天清龍(240) / 通天雜龍(100) / 清龍 10(20) / 雜龍 8(15) / 老少上(3) / 老少碰(5)
    # 備註規定：「任何牌型都係有大計大 i.e. 12344556789食3, 計暗龍不計假獨, 因為假獨沒有暗龍只有明龍」
    # --------------------------------------------------
    tongtian_type = check_tongtian_dragon(melds, pair)
    if tongtian_type == "通天清龍":
        hand_pattern_fans.append(("通天清龍", 240))
    elif tongtian_type == "通天雜龍":
        hand_pattern_fans.append(("通天雜龍", 100))
    else:
        # 檢查清龍 10(20) 與 雜龍 8(15)
        has_pure_dragon = False
        for suit in (1, 2, 3):
            s_123 = [m for m in chows if m.tiles[0] == suit * 10 + 1]
            s_456 = [m for m in chows if m.tiles[0] == suit * 10 + 4]
            s_789 = [m for m in chows if m.tiles[0] == suit * 10 + 7]
            if s_123 and s_456 and s_789:
                has_pure_dragon = True
                is_dark = any(not m.is_open for m in s_123) and \
                          any(not m.is_open for m in s_456) and \
                          any(not m.is_open for m in s_789)
                if is_dark:
                    hand_pattern_fans.append(("清龍(暗)", 20))
                else:
                    hand_pattern_fans.append(("清龍", 10))
                break

        if not has_pure_dragon:
            for p_suits in permutations((1, 2, 3)):
                c_123 = [m for m in chows if m.tiles[0] == p_suits[0] * 10 + 1]
                c_456 = [m for m in chows if m.tiles[0] == p_suits[1] * 10 + 4]
                c_789 = [m for m in chows if m.tiles[0] == p_suits[2] * 10 + 7]
                if c_123 and c_456 and c_789:
                    is_dark = any(not m.is_open for m in c_123) and \
                              any(not m.is_open for m in c_456) and \
                              any(not m.is_open for m in c_789)
                    if is_dark:
                        hand_pattern_fans.append(("雜龍(暗)", 15))
                    else:
                        hand_pattern_fans.append(("雜龍", 8))
                    break

    # 老少上 (3番) / 老少碰 (5番)
    for suit in (1, 2, 3):
        c123 = sum(1 for m in chows if m.tiles[0] == suit * 10 + 1)
        c789 = sum(1 for m in chows if m.tiles[0] == suit * 10 + 7)
        # 若已成同門清龍/通天清龍則不重複計老少上，否則有幾多對計幾多
        has_suit_dragon = any(m.tiles[0] == suit * 10 + 1 for m in chows) and \
                          any(m.tiles[0] == suit * 10 + 4 for m in chows) and \
                          any(m.tiles[0] == suit * 10 + 7 for m in chows)
        if not has_suit_dragon:
            for _ in range(min(c123, c789)):
                hand_pattern_fans.append(("老少上", 3))

        p111 = any(m.tiles[0] == suit * 10 + 1 for m in pongs)
        p999 = any(m.tiles[0] == suit * 10 + 9 for m in pongs)
        if p111 and p999:
            hand_pattern_fans.append(("老少碰", 5))

    # --------------------------------------------------
    # H. 一般高(5)/三般高(20)/四般高(40) & 相逢(3)/三相逢 10(20)
    # --------------------------------------------------
    for num, m_list in chow_by_num.items():
        suit_groups: Dict[int, List[Meld]] = {}
        for m in m_list:
            suit_groups.setdefault(get_suit(m.tiles[0]), []).append(m)

        # 同門同數字順子：一般高(5) / 三般高(20) / 四般高(40)
        for s, sm_list in suit_groups.items():
            scnt = len(sm_list)
            if scnt == 4:
                hand_pattern_fans.append(("四般高", 40))
            elif scnt == 3:
                hand_pattern_fans.append(("三般高", 20))
            elif scnt == 2:
                hand_pattern_fans.append(("一般高", 5))

        # 跨門同數字順子：相逢(3) / 三相逢 10(20) (若已計全相逢 30 則不重複計單項相逢)
        if not is_quanxiangfeng:
            distinct_suits = len(suit_groups)
            if distinct_suits == 3:
                is_dark_3xf = all(any(not m.is_open for m in sm_list) for sm_list in suit_groups.values())
                if is_dark_3xf:
                    hand_pattern_fans.append(("三相逢(暗)", 20))
                else:
                    hand_pattern_fans.append(("三相逢", 10))
            elif distinct_suits == 2:
                # 若其中一門有2組(例如萬123x2 + 筒123x1)，按複式計算可組成相逢
                suits_list = list(suit_groups.values())
                pair_combinations = len(suits_list[0]) * len(suits_list[1])
                for _ in range(pair_combinations):
                    hand_pattern_fans.append(("相逢", 3))

    # --------------------------------------------------
    # I. 步步高系列：全步高(40) / 單色步步高 10(20) / 三色步步高 5(10)
    # --------------------------------------------------
    if len(chows) == 5:
        sorted_start_nums = sorted(get_num(m.tiles[0]) for m in chows)
        if all(sorted_start_nums[i+1] == sorted_start_nums[i] + 1 for i in range(4)):
            hand_pattern_fans.append(("全步高", 40))
        else:
            hand_pattern_fans.extend(_eval_3_step_bubugao(chows))
    elif len(chows) >= 3:
        hand_pattern_fans.extend(_eval_3_step_bubugao(chows))

    # --------------------------------------------------
    # J. 刻子系列：兩姊妹(5)/小三姊妹(10)/大三姊妹(20) & 兩兄弟(5)/小三兄弟(10)/大三兄弟(20)
    # --------------------------------------------------
    suit_pongs = [m for m in pongs if is_suit(m.tiles[0])]

    # 1. 兄弟 (不同門但同數字的刻子)
    pongs_by_num: Dict[int, Set[int]] = {}
    for m in suit_pongs:
        pongs_by_num.setdefault(get_num(m.tiles[0]), set()).add(get_suit(m.tiles[0]))

    for num, suits_set in pongs_by_num.items():
        if len(suits_set) == 3:
            hand_pattern_fans.append(("大三兄弟", 20))
        elif len(suits_set) == 2:
            if is_suit(pair) and get_num(pair) == num and get_suit(pair) not in suits_set:
                hand_pattern_fans.append(("小三兄弟", 10))
            else:
                hand_pattern_fans.append(("兩兄弟", 5))

    # 2. 姊妹 (同門且數字相連的刻子)
    if not is_quanxiangfeng:
        for suit in (1, 2, 3):
            nums_in_suit = sorted(get_num(m.tiles[0]) for m in suit_pongs if get_suit(m.tiles[0]) == suit)
            if not nums_in_suit:
                continue
            # 檢查是否有 3 連刻 (大三姊妹 20)
            used_in_3_sisters: Set[int] = set()
            for i in range(len(nums_in_suit) - 2):
                if nums_in_suit[i+1] == nums_in_suit[i] + 1 and nums_in_suit[i+2] == nums_in_suit[i] + 2:
                    hand_pattern_fans.append(("大三姊妹", 20))
                    used_in_3_sisters.update([nums_in_suit[i], nums_in_suit[i+1], nums_in_suit[i+2]])

            # 檢查未參與大三姊妹的相連刻子：小三姊妹(10) 或 兩姊妹(5)
            rem_nums = [n for n in nums_in_suit if n not in used_in_3_sisters]
            pair_matches_suit = is_suit(pair) and get_suit(pair) == suit
            pair_num = get_num(pair) if pair_matches_suit else -99

            matched_small_sisters = False
            if pair_matches_suit and len(rem_nums) >= 2:
                for c_pair in combinations(rem_nums, 2):
                    trio = sorted([c_pair[0], c_pair[1], pair_num])
                    if trio[1] == trio[0] + 1 and trio[2] == trio[1] + 1:
                        hand_pattern_fans.append(("小三姊妹", 10))
                        matched_small_sisters = True
                        break
            if not matched_small_sisters and len(rem_nums) >= 2:
                for i in range(len(rem_nums) - 1):
                    if rem_nums[i+1] == rem_nums[i] + 1:
                        hand_pattern_fans.append(("兩姊妹", 5))

    # --------------------------------------------------
    # K. 四歸系列：四歸一 5(10) / 四歸二 10(20) / 四歸四 20(40)
    # --------------------------------------------------
    for tile, cnt in tile_counts_non_kong.items():
        if cnt == 4:
            in_pair = (pair == tile)
            matching_pongs = [m for m in melds if m.type == 'pong' and m.tiles[0] == tile]
            matching_chows = [m for m in chows if tile in m.tiles]

            if len(matching_chows) == 4:
                is_dark = all(not m.is_open for m in matching_chows)
                hand_pattern_fans.append((f"四歸四{'(暗)' if is_dark else ''}({TILE_NAMES[tile]})", 40 if is_dark else 20))
            elif in_pair and len(matching_chows) == 2:
                is_dark = all(not m.is_open for m in matching_chows)
                hand_pattern_fans.append((f"四歸二{'(暗)' if is_dark else ''}({TILE_NAMES[tile]})", 20 if is_dark else 10))
            elif len(matching_pongs) == 1 and len(matching_chows) == 1:
                is_dark = (not matching_pongs[0].is_open) and (not matching_chows[0].is_open)
                hand_pattern_fans.append((f"四歸一{'(暗)' if is_dark else ''}({TILE_NAMES[tile]})", 10 if is_dark else 5))

    # --------------------------------------------------
    # L. 門類與色系：字一色(120) / 清一色(80) / 混一色(30) / 七門齊(20) / 五門齊(15) / 缺一門(5)
    # --------------------------------------------------
    if len(suits_present) == 0 and has_honors:
        hand_pattern_fans.append(("字一色", 120))
    elif len(suits_present) == 1 and not has_honors:
        hand_pattern_fans.append(("清一色", 80))
    elif len(suits_present) == 1 and has_honors:
        hand_pattern_fans.append(("混一色", 30))
    elif len(suits_present) == 3 and has_winds and has_dragons:
        if ctx.has_season_grass and ctx.has_plant_flower:
            hand_pattern_fans.append(("七門齊", 20))
        else:
            hand_pattern_fans.append(("五門齊", 15))
    elif len(suits_present) == 2:
        hand_pattern_fans.append(("缺一門", 5))

    # --------------------------------------------------
    # M. 數字範圍與么九系列：
    # 大於5(60) / 小於5(60) / 缺5(10) / 斷么(5) / 混帶么(20) / 全帶么(50) / 混么(80) / 清么(100) / 混帶X(20) / 全帶X(60)
    # --------------------------------------------------
    # 1. 大於5 (60番) / 小於5 (60番) - 備註：大於5/小於5不可以有番子
    if not has_honors:
        all_nums = [get_num(t) for t in all_tiles]
        if all(n > 5 for n in all_nums):
            hand_pattern_fans.append(("大於5", 60))
        elif all(1 <= n < 5 for n in all_nums):
            hand_pattern_fans.append(("小於5", 60))

    # 2. 缺5 (10番) - 全副牌沒有任何 5萬/5筒/5索
    if all(get_num(t) != 5 for t in all_tiles):
        hand_pattern_fans.append(("缺5", 10))

    # 3. 斷么(5) / 清么(100) / 混么(80) / 全帶么(50) / 混帶么(20)
    if all(t not in YAOJIU for t in all_tiles):
        hand_pattern_fans.append(("斷么", 5))
    elif all(t in TERMINALS for t in all_tiles):
        hand_pattern_fans.append(("清么", 100))
    elif all(t in YAOJIU for t in all_tiles) and len(suits_present) > 0:
        hand_pattern_fans.append(("混么", 80))
    else:
        every_meld_has_yaojiu = all(any(t in YAOJIU for t in m.tiles) for m in melds) and (pair in YAOJIU)
        if every_meld_has_yaojiu:
            if has_honors:
                hand_pattern_fans.append(("混帶么", 20))
            else:
                hand_pattern_fans.append(("全帶么", 50))

    # 4. 全帶X (60番) / 混帶X (20番，備註：混滿庭芳可以計3次)
    suit_meld_num_sets = [{get_num(t) for t in m.tiles} for m in melds if is_suit(m.tiles[0])]
    if is_suit(pair):
        suit_meld_num_sets.append({get_num(pair)})

    if suit_meld_num_sets:
        common_x_nums = sorted(set.intersection(*suit_meld_num_sets))
        for x_num in common_x_nums:
            if not has_honors:
                # 若為 1 或 9 且無順子，可能已計清么；但若有順子(如全123+111+11眼)，計全帶一(60)
                hand_pattern_fans.append((f"全帶{x_num} (滿庭芳)", 60))
            else:
                hand_pattern_fans.append((f"混帶{x_num} (混滿庭芳)", 20))

    # --------------------------------------------------
    # N. 檢查是否觸發【大雞糊 (45番)】
    # 備註規定：「大雞糊可以自摸, 叮, 爛花, 無花, 4/7/10子, 只要17隻牌計唔到番就得」
    # 「任何牌型都係有大計大 i.e. 12344556789食3, 計暗龍不計假獨」
    # --------------------------------------------------
    # 若已計清龍(暗)或雜龍(暗)，且玩家誤勾了假獨，依備註自動拿掉假獨
    effective_ctx_wait = ctx.wait_type
    if any(name in ("清龍(暗)", "雜龍(暗)") for name, _ in hand_pattern_fans) and effective_ctx_wait == "jiadu":
        effective_ctx_wait = "normal"

    # 判斷 17 隻牌本身是否計唔到任何番 (即 hand_pattern_fans 為空，且叫胡方式不是對碰/獨獨/假獨，亦無門清5番)
    # 注意：無花(1)、爛花(1)、自摸(1)、叮(5)、4/7/10隻內 屬於牌局外在狀態，大雞糊可照計並疊加！
    if len(hand_pattern_fans) == 0 and not is_menqing and effective_ctx_wait == "normal":
        hand_pattern_fans.append(("大雞糊 (17隻牌計唔到番)", 45))

    # 加上共通花牌與狀態番
    modified_ctx = GameContext(**{**ctx.__dict__, "wait_type": effective_ctx_wait})
    context_fans = evaluate_context_and_flower_fans(
        modified_ctx,
        is_menqing=is_menqing,
        is_special_non_menqing_hand=False,
        skip_no_flower=skip_no_flower
    )

    all_fans = hand_pattern_fans + context_fans
    return finalize_with_dealer(all_fans, ctx)


def _eval_3_step_bubugao(chows: List[Meld]) -> List[Tuple[str, int]]:
    """輔助計算【單色步步高 10(20)】與【三色步步高 5(10)】（順子遞增 1）"""
    res: List[Tuple[str, int]] = []
    # 1. 單色步步高 (同門 3 組順子遞增 1)
    for suit in (1, 2, 3):
        s_chows = [m for m in chows if get_suit(m.tiles[0]) == suit]
        if len(s_chows) >= 3:
            for comb in combinations(s_chows, 3):
                nums = sorted(get_num(m.tiles[0]) for m in comb)
                if nums[1] == nums[0] + 1 and nums[2] == nums[1] + 1:
                    is_dark = all(not m.is_open for m in comb)
                    res.append(("單色步步高(暗)" if is_dark else "單色步步高", 20 if is_dark else 10))
    # 2. 三色步步高 (三門各 1 組順子遞增 1)
    for comb in combinations(chows, 3):
        suits = {get_suit(m.tiles[0]) for m in comb}
        if len(suits) == 3:
            nums = sorted(get_num(m.tiles[0]) for m in comb)
            if nums[1] == nums[0] + 1 and nums[2] == nums[1] + 1:
                is_dark = all(not m.is_open for m in comb)
                res.append(("三色步步高(暗)" if is_dark else "三色步步高", 10 if is_dark else 5))
    return res


# ==========================================
# 6. 特殊牌型專屬評估器 (嚦咕 / 十六不搭 / 十三么)
# ==========================================

def evaluate_liguligu_hand(
    eight_pairs: List[int],
    triplet_tile: int,
    all_tiles: List[int],
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """
    評估【嚦咕嚦咕 (45番) / 8飛嚦咕嚦咕 (55番)】及其專屬備註規則：
    - 嚦咕不計門清、一摸八、門清叮
    - 嚦咕可以計三元、三風、四喜，番數除一半
    - 嚦咕 3/4/5/6/7 連對 -> 5/10/20/30/60 番
    - 嚦咕有幾多象眼(2/5/8對)計幾多 (每對 2 番)
    """
    fans: List[Tuple[str, int]] = []
    if ctx.special_wait_variant == "8fei_ligu":
        fans.append(("8飛嚦咕嚦咕", 55))
    else:
        fans.append(("嚦咕嚦咕", 45))

    suits_present = {get_suit(t) for t in all_tiles if is_suit(t)}
    has_winds = any(t in WINDS for t in all_tiles)
    has_dragons = any(t in DRAGONS for t in all_tiles)
    has_honors = has_winds or has_dragons
    total_flowers = ctx.good_flowers + ctx.bad_flowers + (ctx.flower_sets * 4)
    has_any_flower = (total_flowers > 0) or ctx.has_season_grass or ctx.has_plant_flower

    # 無字 / 無花 / 無字花
    skip_no_flower = False
    if not has_any_flower and not has_honors:
        fans.append(("無字花", 5))
        skip_no_flower = True
    elif not has_honors:
        fans.append(("無字", 1))

    # 1. 象眼：有幾多對 2/5/8 計幾多 (每對 2 番)
    xiangyan_cnt = sum(1 for t in eight_pairs if is_suit(t) and get_num(t) in (2, 5, 8))
    if xiangyan_cnt > 0:
        fans.append((f"象眼 x{xiangyan_cnt}對", 2 * xiangyan_cnt))

    # 2. 嚦咕 3/4/5/6/7 連對 (5/10/20/30/60番)
    streak_score_map = {3: 5, 4: 10, 5: 20, 6: 30, 7: 60, 8: 60}
    for suit in (1, 2, 3):
        suit_nums = sorted(get_num(t) for t in set(eight_pairs) if get_suit(t) == suit)
        cur_len = 0
        for i, n in enumerate(suit_nums):
            if i == 0 or n == suit_nums[i - 1] + 1:
                cur_len += 1
            else:
                if cur_len >= 3:
                    fans.append((f"嚦咕{cur_len}連對", streak_score_map[min(cur_len, 7)]))
                cur_len = 1
        if cur_len >= 3:
            fans.append((f"嚦咕{cur_len}連對", streak_score_map[min(cur_len, 7)]))

    # 3. 嚦咕計三元/三風/四喜，番數除一半 (刻子那隻視為刻，對子視為眼/對)
    distinct_dragons = {t for t in eight_pairs if t in DRAGONS}
    distinct_winds = {t for t in eight_pairs if t in WINDS}
    if len(distinct_dragons) == 3:
        if triplet_tile in DRAGONS:
            fans.append(("大三元(嚦咕減半)", 30))
        else:
            fans.append(("小三元(嚦咕減半)", 15))
    if len(distinct_winds) == 4:
        if triplet_tile in WINDS:
            fans.append(("大四喜(嚦咕減半)", 50))
        else:
            fans.append(("小四喜(嚦咕減半)", 40))
    elif len(distinct_winds) == 3:
        if triplet_tile in WINDS:
            fans.append(("大三風(嚦咕減半)", 20))
        else:
            fans.append(("小三風(嚦咕減半)", 10))

    # 4. 門類與數字範圍番種
    if len(suits_present) == 0 and has_honors:
        fans.append(("字一色", 120))
    elif len(suits_present) == 1 and not has_honors:
        fans.append(("清一色", 80))
    elif len(suits_present) == 1 and has_honors:
        fans.append(("混一色", 30))
    elif len(suits_present) == 3 and has_winds and has_dragons:
        if ctx.has_season_grass and ctx.has_plant_flower:
            fans.append(("七門齊", 20))
        else:
            fans.append(("五門齊", 15))
    elif len(suits_present) == 2:
        fans.append(("缺一門", 5))

    if not has_honors:
        all_nums = [get_num(t) for t in all_tiles]
        if all(n > 5 for n in all_nums):
            fans.append(("大於5", 60))
        elif all(1 <= n < 5 for n in all_nums):
            fans.append(("小於5", 60))

    if all(get_num(t) != 5 for t in all_tiles):
        fans.append(("缺5", 10))
    if all(t not in YAOJIU for t in all_tiles):
        fans.append(("斷么", 5))
    elif all(t in TERMINALS for t in all_tiles):
        fans.append(("清么", 100))
    elif all(t in YAOJIU for t in all_tiles) and len(suits_present) > 0:
        fans.append(("混么", 80))

    fans.extend(evaluate_context_and_flower_fans(ctx, is_menqing=True, is_special_non_menqing_hand=True, skip_no_flower=skip_no_flower))
    return finalize_with_dealer(fans, ctx)


def evaluate_shiliubuda_hand(
    pair_tile: int,
    suit_sets: Dict[int, Tuple[int, int, int]],
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """
    評估【十六不搭 (50番) / 16飛十六不搭 (60番)】及其專屬備註規則：
    - 支援 不搭三相逢 10(20) & 不搭龍 10(20)
    - 必含五門齊(15) 或 七門齊(20)
    - 備註：不搭可計象眼 (2番)，不計門清、一摸八、門清叮
    """
    fans: List[Tuple[str, int]] = []
    if ctx.special_wait_variant == "16fei_buda":
        fans.append(("16飛十六不搭", 60))
    else:
        fans.append(("十六不搭", 50))

    # 五門齊(15) / 七門齊(20)
    if ctx.has_season_grass and ctx.has_plant_flower:
        fans.append(("七門齊", 20))
    else:
        fans.append(("五門齊", 15))

    # 不搭三相逢 10(20) vs 不搭龍 10(20)
    t1, t2, t3 = suit_sets[1], suit_sets[2], suit_sets[3]
    is_dark_buda = ctx.buda_dragon_is_concealed
    if t1 == t2 == t3:
        fans.append(("不搭三相逢(暗)" if is_dark_buda else "不搭三相逢", 20 if is_dark_buda else 10))
    elif set(t1) | set(t2) | set(t3) == {1, 2, 3, 4, 5, 6, 7, 8, 9}:
        # 例如三門分別為 (1,4,7), (2,5,8), (3,6,9) 湊齊 1~9 不搭雜龍
        fans.append(("不搭龍(暗)" if is_dark_buda else "不搭龍", 20 if is_dark_buda else 10))

    # 象眼 (2番)
    if is_suit(pair_tile) and get_num(pair_tile) in (2, 5, 8):
        fans.append(("象眼", 2))

    # 缺5 (10番)
    all_suit_nums = set(t1) | set(t2) | set(t3)
    if 5 not in all_suit_nums:
        fans.append(("缺5", 10))

    fans.extend(evaluate_context_and_flower_fans(ctx, is_menqing=True, is_special_non_menqing_hand=True))
    return finalize_with_dealer(fans, ctx)


# ==========================================
# 7. 主入口函數：自動拆牌、找最高番數並計算金額
# ==========================================

@dataclass
class ScoringResult:
    is_valid_hu: bool
    hand_pattern_name: str
    total_fan: int
    fan_breakdown: List[Tuple[str, int]]
    best_melds: List[Meld]
    best_pair: Optional[int]
    base_payout: float
    message: str = ""


def calculate_hk_tw_mahjong(
    hand_tiles: List[int],
    fixed_melds: Optional[List[Meld]] = None,
    ctx: Optional[GameContext] = None
) -> ScoringResult:
    if fixed_melds is None:
        fixed_melds = []
    if ctx is None:
        ctx = GameContext()

    # 特殊情況 0：七搶一 (50番) / 八仙過海 (100番) 直接食胡
    if ctx.special_flower_hu in ("qiqiangyi", "baxianguohai"):
        base_f = [("八仙過海 (8隻花直接食胡)", 100)] if ctx.special_flower_hu == "baxianguohai" else [("七搶一 (7搶1花胡)", 50)]
        base_f.extend(evaluate_context_and_flower_fans(ctx, is_menqing=True, is_special_non_menqing_hand=True, skip_no_flower=True))
        total_fan, fans = finalize_with_dealer(base_f, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        return ScoringResult(True, base_f[0][0], total_fan, fans, fixed_melds, None, payout)

    expected_hand_len = 17 - 3 * len(fixed_melds)
    if len(hand_tiles) != expected_hand_len:
        return ScoringResult(
            is_valid_hu=False,
            hand_pattern_name="張數錯誤",
            total_fan=0,
            fan_breakdown=[],
            best_melds=[],
            best_pair=None,
            base_payout=0.0,
            message=f"手牌張數應為 {expected_hand_len} 張 (目前輸入 {len(hand_tiles)} 張，已落地 {len(fixed_melds)} 組)"
        )

    candidates: List[ScoringResult] = []
    all_tiles_flat = list(hand_tiles) + [t for m in fixed_melds for t in m.tiles]

    # 1. 檢查【十三么 (120) / 13飛 (130) / 14飛 (140)】
    shisanyao_res = check_shisanyao(hand_tiles, fixed_melds)
    if shisanyao_res is not None:
        pair_tile, extra_meld = shisanyao_res
        if ctx.special_wait_variant == "14fei_13yao":
            fans = [("14飛十三么", 140)]
        elif ctx.special_wait_variant == "13fei_13yao":
            fans = [("13飛十三么", 130)]
        else:
            fans = [("十三么", 120)]

        # 十三么必齊五門，檢查是否七門齊(20)或五門齊(15)
        if ctx.has_season_grass and ctx.has_plant_flower:
            fans.append(("七門齊", 20))
        else:
            fans.append(("五門齊", 15))

        if all(get_num(t) != 5 for t in all_tiles_flat):
            fans.append(("缺5", 10))

        fans.extend(evaluate_context_and_flower_fans(ctx, is_menqing=True, is_special_non_menqing_hand=True))
        total_fan, fans = finalize_with_dealer(fans, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "十三么", total_fan, fans, extra_meld, pair_tile, payout))

    # 2. 檢查【十六不搭 (50) / 16飛十六不搭 (60)】
    buda_res = check_shiliubuda(hand_tiles, fixed_melds)
    if buda_res is not None:
        pair_tile, suit_sets = buda_res
        total_fan, fans = evaluate_shiliubuda_hand(pair_tile, suit_sets, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "十六不搭", total_fan, fans, [], pair_tile, payout))

    # 3. 檢查【嚦咕嚦咕 (45) / 8飛嚦咕嚦咕 (55)】
    ligu_res = check_liguligu(hand_tiles, fixed_melds)
    if ligu_res is not None:
        eight_pairs, triplet_tile = ligu_res
        total_fan, fans = evaluate_liguligu_hand(eight_pairs, triplet_tile, all_tiles_flat, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "嚦咕嚦咕", total_fan, fans, [Meld('pong', (triplet_tile,) * 3, False)], eight_pairs[0], payout))

    # 4. 檢查【標準牌型 (5組面子 + 1對眼)】
    decomps = find_standard_decompositions(hand_tiles, fixed_melds)
    for melds, pair in decomps:
        total_fan, fans = evaluate_standard_decomposition(melds, pair, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "標準牌型(5面子+1眼)", total_fan, fans, melds, pair, payout))

    if not candidates:
        return ScoringResult(
            is_valid_hu=False,
            hand_pattern_name="詐糊 (未構成胡牌牌型)",
            total_fan=0,
            fan_breakdown=[("詐糊罰款 (賠每門 $100)", 0)],
            best_melds=[],
            best_pair=None,
            base_payout=0.0,
            message="輸入的牌無法組成 5組面子+1對眼 或 十三么/十六不搭/嚦咕嚦咕。"
        )

    return max(candidates, key=lambda r: r.total_fan)


def calculate_lazhuang_settlement(
    previous_debt: float,
    current_fan: int,
    base_price: float = 1.0,
    fan_price: float = 0.1,
    event_type: str = "continue_win"
) -> Dict[str, float]:
    current_hand_amount = round(current_fan * fan_price + base_price, 2)
    if event_type == "continue_win":
        new_total_debt = round((previous_debt * 1.5) + current_hand_amount, 2)
        return {
            "當鋪基本金額": current_hand_amount,
            "上鋪累積金額": previous_debt,
            "拉莊後最新累積金額 (x1.5 + 今鋪)": new_total_debt
        }
    elif event_type == "counter_win_or_zimo":
        half_deducted = round(previous_debt / 2.0, 2)
        return {
            "原累積欠款": previous_debt,
            "扣減一半後應付金額": half_deducted,
            "當鋪贏回金額": current_hand_amount,
            "淨結算 (正數為應付，負數為倒贏)": round(half_deducted - current_hand_amount, 2)
        }
    return {"當鋪基本金額": current_hand_amount}
