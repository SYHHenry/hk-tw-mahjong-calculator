from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations
from typing import List, Tuple, Dict, Optional, Set

# ==========================================
# 1. 牌張編碼定義與輔助轉換函數
# ==========================================
# 萬子: 11-19 (一萬~九萬)
# 筒子: 21-29 (一筒~九筒)
# 索子: 31-39 (一索~九索)
# 風牌: 41=東, 42=南, 43=西, 44=北
# 三元牌: 51=中, 52=發, 53=白

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
    """回傳門類: 1=萬, 2=筒, 3=索, 4=風, 5=三元"""
    return tile // 10


def get_num(tile: int) -> int:
    """回傳序數 (1~9)，字牌回傳 0"""
    return tile % 10 if is_suit(tile) else 0


@dataclass(frozen=True)
class Meld:
    """
    面子結構:
    - type: 'chow' (順子), 'pong' (刻子), 'kong' (槓子)
    - tiles: 例如順子 (11, 12, 13), 刻子 (41, 41, 41), 槓子 (51, 51, 51, 51)
    - is_open: True 代表已落地 (上、碰、明槓)；False 代表門前 (手牌暗順、手牌暗刻、暗槓)
    """
    type: str
    tiles: Tuple[int, ...]
    is_open: bool = False

    def __repr__(self) -> str:
        prefix = "明" if self.is_open else "暗"
        t_str = "".join(TILE_NAMES.get(t, str(t)) for t in self.tiles)
        return f"[{prefix}{self.type}:{t_str}]"


@dataclass
class GameContext:
    """牌局狀態與特殊事件參數（對應手機 App 介面勾選項）"""
    seat_wind: int = 41               # 自己門風/正風 (41=東, 42=南, 43=西, 44=北)
    winning_tile: Optional[int] = None # 最後食胡的那張牌

    # 花牌狀態 (春夏秋冬=1~4, 梅蘭菊竹=1~4)
    good_flowers: int = 0             # 正花數量 (與座位同號，每隻 2 番)
    bad_flowers: int = 0              # 爛花數量 (與座位不同號，每隻 1 番)
    flower_sets: int = 0              # 一台花數量 (0=無, 1=一台花10番, 2=兩台花胡30番)
    is_flower_hu_only: bool = False   # 兩台花(8隻花)直接食胡，不計手牌

    # 食胡與聽牌狀態
    is_zimo: bool = False             # 自摸 (1番；若連同門清則計門清自摸5番)
    is_riichi: bool = False           # 聽牌 / 叮 (5番)
    wait_type: str = "normal"         # 'normal'(兩面/多面), 'duipeng'(對碰 1番), 'jiadu'(假獨 1番), 'dudu'(獨獨/單釣/邊張/卡張 2番)

    # 特殊時機番
    is_tianhu: bool = False           # 天胡 (100番: 莊家起手補花後即食胡)
    is_dihu: bool = False             # 地胡 (80番: 閒家第一次摸牌即自摸)
    is_renhu: bool = False            # 人胡 (80番: 閒家在四隻牌內食胡)
    is_haidi: bool = False            # 海底撈月 (20番: 最後一隻牌自摸)
    within_tiles: int = 0             # 7=七只內(20番), 10=十只內(10番), 0=無

    # 花上 / 槓上 / 搶槓
    is_huashang: bool = False         # 花上食胡 (1番: 摸花時自摸)
    is_gangshang: bool = False        # 槓上食胡 (1番: 開槓時自摸)
    is_qianggang: bool = False        # 搶槓食胡 (1番: 搶槓當被搶那家出沖，不當自摸)
    is_gang_on_gang: bool = False     # 槓上槓食胡 (30番: 開槓後再開槓自摸)
    is_qiang_gang_on_gang: bool = False # 搶槓上槓食胡 (30番: 當槓上槓那家出沖)

    # 莊家與連莊設定
    is_dealer: bool = False           # 是否做莊 (做莊加 1 番)
    dealer_streak: int = 0            # 連莊數 (0=無連莊, 1=連一[+3番], 2=連二[+5番], N=連N[+2N+1番])

    # 計錢設定
    base_price: float = 10.0          # 一底金額 (例如 $10)
    fan_price: float = 2.0            # 每番金額 (例如 $2)


# ==========================================
# 2. 特殊牌型判別器 (不屬於 5面子+1眼 的牌型)
# ==========================================

def check_shisanyao(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[Tuple[int, List[Meld]]]:
    """
    檢查【十三么 (80番)】：
    規則：十三么（13隻么九番子，其中1隻成對，共14隻），
    另三隻是自己摸回來的順子或暗刻，不能上或碰回來。
    """
    if any(m.is_open for m in fixed_melds):
        return None
    if len(fixed_melds) > 1 or (len(fixed_melds) == 1 and fixed_melds[0].type == 'kong'):
        return None

    counts = Counter(hand_tiles)
    if len(fixed_melds) == 1:
        extra_meld = fixed_melds[0]
        if not all(counts[y] >= 1 for y in YAOJIU):
            return None
        pair_candidates = [y for y in YAOJIU if counts[y] == 2]
        if len(pair_candidates) == 1 and sum(counts.values()) == 14:
            return pair_candidates[0], [extra_meld]
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


def check_shiliubuda(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[int]:
    """
    檢查【十六不搭 / 九唔搭八 (40番)】：
    規則：東南西北中發白，其他三門每樣三隻，但不能搭上（同門任兩隻差值 >= 3，如 149、259），再加一對眼。
    """
    if fixed_melds or len(hand_tiles) != 17:
        return None
    counts = Counter(hand_tiles)
    if not all(counts[h] >= 1 for h in HONORS):
        return None
    if len(counts) != 16 or max(counts.values()) != 2:
        return None
    pair_tile = next(t for t, c in counts.items() if c == 2)

    for suit in (1, 2, 3):
        suit_tiles = sorted(t % 10 for t in counts.keys() if t // 10 == suit)
        if len(suit_tiles) != 3:
            return None
        if (suit_tiles[1] - suit_tiles[0] < 3) or (suit_tiles[2] - suit_tiles[1] < 3):
            return None
    return pair_tile


def check_liguligu(hand_tiles: List[int], fixed_melds: List[Meld]) -> Optional[Tuple[List[int], int]]:
    """
    檢查【嚦咕嚦咕 (40番)】：
    規則：八對子，三隻一樣的不能碰出（17張手牌由 7個對子 + 1個暗刻 組成）。
    """
    if fixed_melds or len(hand_tiles) != 17:
        return None
    counts = Counter(hand_tiles)
    odd_tiles = [t for t, c in counts.items() if c % 2 == 1]
    if len(odd_tiles) != 1 or counts[odd_tiles[0]] != 3:
        return None
    triplet_tile = odd_tiles[0]
    pairs = []
    for t, c in sorted(counts.items()):
        if t == triplet_tile:
            continue
        if c == 2:
            pairs.append(t)
        elif c == 4:
            pairs.extend([t, t])
        else:
            return None
    if len(pairs) == 7:
        return pairs, triplet_tile
    return None


# ==========================================
# 3. 標準牌型拆解器 (5組面子 + 1對眼)
# ==========================================

def find_standard_decompositions(
    hand_tiles: List[int],
    fixed_melds: List[Meld]
) -> List[Tuple[List[Meld], int]]:
    """將手牌 + 已落地面子拆解為所有合法的 (5組面子, 1對眼) 組合"""
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

        # 1. 嘗試暗刻 (Pong)
        if current_counts[first_tile] >= 3:
            current_counts[first_tile] -= 3
            current_melds.append(Meld('pong', (first_tile, first_tile, first_tile), is_open=False))
            backtrack(current_counts, current_melds, current_pair)
            current_melds.pop()
            current_counts[first_tile] += 3

        # 2. 嘗試順子 (Chow)
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
# 4. 完整 68+ 種番型評估引擎 (依截圖規則)
# ==========================================

def evaluate_common_context_fans(
    ctx: GameContext,
    is_menqing: bool,
    skip_no_flower: bool = False
) -> List[Tuple[str, int]]:
    """評估所有牌型共通的花牌、門清自摸、聽牌、叫胡、時機與槓上番"""
    fans: List[Tuple[str, int]] = []
    total_flowers = ctx.good_flowers + ctx.bad_flowers + (ctx.flower_sets * 4)

    # --- 花牌番 ---
    if ctx.flower_sets == 2:
        fans.append(("兩台花(花胡)", 30))
    elif ctx.flower_sets == 1:
        fans.append(("一台花", 10))

    if ctx.good_flowers > 0:
        fans.append((f"正花 x{ctx.good_flowers}", 2 * ctx.good_flowers))
    if ctx.bad_flowers > 0:
        fans.append((f"爛花 x{ctx.bad_flowers}", 1 * ctx.bad_flowers))

    if not skip_no_flower and total_flowers == 0 and ctx.flower_sets == 0:
        fans.append(("無花", 1))

    # --- 門清與自摸 (搶槓不當自摸) ---
    effective_zimo = ctx.is_zimo and not (ctx.is_qianggang or ctx.is_qiang_gang_on_gang)
    if is_menqing and effective_zimo:
        fans.append(("門清自摸", 5))
    else:
        if is_menqing:
            fans.append(("門清", 3))
        if effective_zimo:
            fans.append(("自摸", 1))

    # --- 聽牌(叮)與叫胡方式 ---
    if ctx.is_riichi:
        fans.append(("聽牌(叮)", 5))
    if ctx.wait_type == "duipeng":
        fans.append(("對碰", 1))
    elif ctx.wait_type == "jiadu":
        fans.append(("假獨", 1))
    elif ctx.wait_type == "dudu":
        fans.append(("獨獨", 2))

    # --- 天地人胡、海底、七/十只內 ---
    if ctx.is_tianhu:
        fans.append(("天胡", 100))
    elif ctx.is_dihu:
        fans.append(("地胡", 80))
    elif ctx.is_renhu:
        fans.append(("人胡", 80))

    if ctx.is_haidi:
        fans.append(("海底撈月", 20))
    if ctx.within_tiles == 7:
        fans.append(("七只內", 20))
    elif ctx.within_tiles == 10:
        fans.append(("十只內", 10))

    # --- 花上 / 槓上 / 搶槓 ---
    if ctx.is_huashang:
        fans.append(("花上食胡", 1))
    if ctx.is_gang_on_gang:
        fans.append(("槓上槓食胡", 30))
    elif ctx.is_gangshang:
        fans.append(("槓上食胡", 1))

    if ctx.is_qiang_gang_on_gang:
        fans.append(("搶槓上槓食胡", 30))
    elif ctx.is_qianggang:
        fans.append(("搶槓食胡", 1))

    return fans


def apply_dealer_and_jihu(
    fans: List[Tuple[str, int]],
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """套用【雞胡 (10番)】判定與【做莊 / 連莊】加番"""
    effective_zimo = ctx.is_zimo and not (ctx.is_qianggang or ctx.is_qiang_gang_on_gang)
    hand_fan_sum = sum(score for _, score in fans)

    # 截圖規則：雞胡 (10番) - 胡出時(不計莊前)只得一番。如果自摸或已叫了聽牌就一定不是雞胡了
    if hand_fan_sum == 1 and not effective_zimo and not ctx.is_riichi and not ctx.is_flower_hu_only:
        fans = [("雞胡 (原為1番)", 10)]

    # 莊家與連莊加番：凡做莊胡牌額外加 1 番；連莊額外加 骰仔數字 x 2 + 1 番
    if ctx.is_dealer:
        fans.append(("莊家", 1))
        if ctx.dealer_streak > 0:
            streak_bonus = ctx.dealer_streak * 2 + 1
            fans.append((f"連{ctx.dealer_streak} (拉莊)", streak_bonus))

    total = sum(score for _, score in fans)
    return total, fans


def evaluate_standard_decomposition(
    melds: List[Meld],
    pair: int,
    ctx: GameContext
) -> Tuple[int, List[Tuple[str, int]]]:
    """對單一標準拆解 (5組面子 + 1對眼) 進行完整番數計算"""
    fans: List[Tuple[str, int]] = []

    all_tiles = [t for m in melds for t in m.tiles] + [pair, pair]
    non_kong_tiles = [t for m in melds if m.type != 'kong' for t in m.tiles] + [pair, pair]
    tile_counts_non_kong = Counter(non_kong_tiles)

    suits_present = {get_suit(t) for t in all_tiles if is_suit(t)}
    has_winds = any(t in WINDS for t in all_tiles)
    has_dragons = any(t in DRAGONS for t in all_tiles)
    has_honors = has_winds or has_dragons
    total_flowers = ctx.good_flowers + ctx.bad_flowers + (ctx.flower_sets * 4)

    chows = [m for m in melds if m.type == 'chow']
    pongs = [m for m in melds if m.type in ('pong', 'kong')]
    kongs = [m for m in melds if m.type == 'kong']

    is_pinghu = (len(chows) == 5)
    is_menqing = all(not m.is_open for m in melds)
    effective_zimo = ctx.is_zimo and not (ctx.is_qianggang or ctx.is_qiang_gang_on_gang)

    # --------------------------------------------------
    # A. 平胡 / 無字 / 無花 / 無字花 / 大平糊 (組合互斥處理)
    # --------------------------------------------------
    skip_no_flower = False
    is_no_flower = (total_flowers == 0 and ctx.flower_sets == 0)

    is_qingyise = (len(suits_present) == 1 and not has_honors)
    is_queyimen = (len(suits_present) == 2)
    is_duanyao = all(t not in YAOJIU for t in all_tiles)
    is_quandaiyao_no_honor = (not has_honors) and all(any(t in TERMINALS for t in m.tiles) for m in melds) and (pair in TERMINALS)
    is_qingyao = all(t in TERMINALS for t in all_tiles)

    # 截圖規則：不能重複計算類似番數，例如缺一門不能計無字
    implies_no_honor = is_qingyise or is_queyimen or is_duanyao or is_quandaiyao_no_honor or is_qingyao

    if is_no_flower and not has_honors and is_pinghu:
        fans.append(("無字花平胡(大平糊)", 10))
        skip_no_flower = True
    elif is_no_flower and not has_honors:
        fans.append(("無字花", 5))
        skip_no_flower = True
        if is_pinghu:
            fans.append(("平胡", 3))
    else:
        if is_pinghu:
            fans.append(("平胡", 3))
        if not has_honors and not implies_no_honor:
            fans.append(("無字", 1))

    fans.extend(evaluate_common_context_fans(ctx, is_menqing, skip_no_flower=skip_no_flower))

    # --------------------------------------------------
    # B. 將眼 (1番)：以一對二、五或八做眼
    # --------------------------------------------------
    if is_suit(pair) and get_num(pair) in (2, 5, 8):
        fans.append(("將眼", 1))

    # --------------------------------------------------
    # C. 明槓 (1番) / 暗槓 (2番)
    # --------------------------------------------------
    open_kongs = sum(1 for m in kongs if m.is_open)
    concealed_kongs = sum(1 for m in kongs if not m.is_open)
    if open_kongs > 0:
        fans.append((f"明槓 x{open_kongs}", 1 * open_kongs))
    if concealed_kongs > 0:
        fans.append((f"暗槓 x{concealed_kongs}", 2 * concealed_kongs))

    # --------------------------------------------------
    # D. 字牌刻子與三元 / 四喜系列
    # --------------------------------------------------
    dragon_pongs = [m for m in pongs if m.tiles[0] in DRAGONS]
    wind_pongs = [m for m in pongs if m.tiles[0] in WINDS]

    if len(dragon_pongs) == 3:
        fans.append(("大三元", 40))
    elif len(dragon_pongs) == 2 and pair in DRAGONS:
        fans.append(("小三元", 20))
    else:
        for m in dragon_pongs:
            fans.append((f"碰出{TILE_NAMES[m.tiles[0]]}", 2))

    if len(wind_pongs) == 4:
        fans.append(("大四喜", 80))
    elif len(wind_pongs) == 3 and pair in WINDS:
        fans.append(("小四喜", 60))
    elif len(wind_pongs) == 3:
        fans.append(("大三風", 30))
    elif len(wind_pongs) == 2 and pair in WINDS:
        fans.append(("小三風", 15))
    else:
        for m in wind_pongs:
            w = m.tiles[0]
            if w == ctx.seat_wind:
                fans.append((f"碰出{TILE_NAMES[w]}(正風)", 2))
            else:
                fans.append((f"碰出{TILE_NAMES[w]}(非正風)", 1))

    # --------------------------------------------------
    # E. 對對胡 / 間間胡 / 暗刻 / 全求人 / 半求人
    # --------------------------------------------------
    # 截圖二暗刻解說：明槓、暗槓或在自己手上三隻一樣的牌叫做暗刻
    concealed_pongs = [m for m in pongs if (not m.is_open) or m.type == 'kong']

    is_jianjianhu = (len(pongs) == 5 and is_menqing and effective_zimo)
    if is_jianjianhu:
        fans.append(("間間胡", 100))
    else:
        if len(pongs) == 5:
            fans.append(("對對胡", 30))
        if len(concealed_pongs) == 5:
            fans.append(("五暗刻", 80))
        elif len(concealed_pongs) == 4:
            fans.append(("四暗刻", 30))
        elif len(concealed_pongs) == 3:
            fans.append(("三暗刻", 10))
        elif len(concealed_pongs) == 2:
            fans.append(("二暗刻", 3))

    if all(m.is_open for m in melds):
        if effective_zimo:
            fans.append(("半求人", 8))
        else:
            fans.append(("全求人", 15))

    # --------------------------------------------------
    # F. 順子系列：明暗龍 / 明暗雜龍 / 老少 / 一般高 / 相逢 / 同順
    # --------------------------------------------------
    has_dragon_straight = False
    for suit in (1, 2, 3):
        s_123 = [i for i, m in enumerate(chows) if m.tiles[0] == suit * 10 + 1]
        s_456 = [i for i, m in enumerate(chows) if m.tiles[0] == suit * 10 + 4]
        s_789 = [i for i, m in enumerate(chows) if m.tiles[0] == suit * 10 + 7]
        if s_123 and s_456 and s_789:
            has_dragon_straight = True
            is_concealed_dragon = any(not chows[i].is_open for i in s_123) and \
                                  any(not chows[i].is_open for i in s_456) and \
                                  any(not chows[i].is_open for i in s_789)
            if is_concealed_dragon:
                fans.append(("暗龍", 20))
            else:
                fans.append(("明龍", 10))
            break

    if not has_dragon_straight:
        for p_suits in permutations((1, 2, 3)):
            c_123 = [i for i, m in enumerate(chows) if m.tiles[0] == p_suits[0] * 10 + 1]
            c_456 = [i for i, m in enumerate(chows) if m.tiles[0] == p_suits[1] * 10 + 4]
            c_789 = [i for i, m in enumerate(chows) if m.tiles[0] == p_suits[2] * 10 + 7]
            if c_123 and c_456 and c_789:
                is_concealed_mixed = any(not chows[i].is_open for i in c_123) and \
                                     any(not chows[i].is_open for i in c_456) and \
                                     any(not chows[i].is_open for i in c_789)
                if is_concealed_mixed:
                    fans.append(("暗雜龍", 15))
                else:
                    fans.append(("明雜龍", 8))
                break

    # 老少 (2番)：同門 123+789 或 111+999
    for suit in (1, 2, 3):
        has_123_456_789 = any(m.tiles[0] == suit * 10 + 1 for m in chows) and \
                          any(m.tiles[0] == suit * 10 + 4 for m in chows) and \
                          any(m.tiles[0] == suit * 10 + 7 for m in chows)
        if not has_123_456_789:
            chow_123 = sum(1 for m in chows if m.tiles[0] == suit * 10 + 1)
            chow_789 = sum(1 for m in chows if m.tiles[0] == suit * 10 + 7)
            for _ in range(min(chow_123, chow_789)):
                fans.append(("老少(順子)", 2))

        pong_111 = any(m.tiles[0] == suit * 10 + 1 for m in pongs)
        pong_999 = any(m.tiles[0] == suit * 10 + 9 for m in pongs)
        if pong_111 and pong_999:
            fans.append(("老少(刻子)", 2))

    # 四同順(20) / 五同順(40) vs 一般高/三般高/四般高 & 二相逢/三相逢
    chow_by_num: Dict[int, List[Meld]] = {}
    for m in chows:
        chow_by_num.setdefault(get_num(m.tiles[0]), []).append(m)

    for num, m_list in chow_by_num.items():
        cnt = len(m_list)
        suit_counter = Counter(get_suit(m.tiles[0]) for m in m_list)

        if cnt == 5:
            fans.append(("五同順", 40))
        elif cnt == 4:
            if len(suit_counter) == 1:
                fans.append(("四般高", 30))
            else:
                fans.append(("四同順", 20))
        else:
            for s, s_cnt in suit_counter.items():
                if s_cnt == 3:
                    fans.append(("三般高", 15))
                elif s_cnt == 2:
                    fans.append(("一般高", 3))

            distinct_suits = len(suit_counter)
            if distinct_suits == 3:
                fans.append(("三相逢(順子)", 10))
            elif distinct_suits == 2:
                fans.append(("二相逢(順子)", 2))

    # --------------------------------------------------
    # G. 刻子系列：二兄弟 / 小三兄弟 / 大三兄弟 & 小三姊妹 / 大三姊妹
    # --------------------------------------------------
    suit_pongs = [m for m in pongs if is_suit(m.tiles[0])]

    pongs_by_num: Dict[int, Set[int]] = {}
    for m in suit_pongs:
        pongs_by_num.setdefault(get_num(m.tiles[0]), set()).add(get_suit(m.tiles[0]))

    for num, suits_set in pongs_by_num.items():
        if len(suits_set) == 3:
            fans.append(("大三兄弟(刻子)", 15))
        elif len(suits_set) == 2:
            if is_suit(pair) and get_num(pair) == num and get_suit(pair) not in suits_set:
                fans.append(("小三兄弟(刻子)", 10))
            else:
                fans.append(("二兄弟(刻子)", 3))

    for suit in (1, 2, 3):
        nums_in_suit = sorted(get_num(m.tiles[0]) for m in suit_pongs if get_suit(m.tiles[0]) == suit)
        has_big_sisters = False
        for i in range(len(nums_in_suit) - 2):
            if nums_in_suit[i+1] == nums_in_suit[i] + 1 and nums_in_suit[i+2] == nums_in_suit[i] + 2:
                fans.append(("大三姊妹", 15))
                has_big_sisters = True
                break
        if not has_big_sisters and is_suit(pair) and get_suit(pair) == suit:
            pair_num = get_num(pair)
            for i in range(len(nums_in_suit)):
                for j in range(i + 1, len(nums_in_suit)):
                    trio = sorted([nums_in_suit[i], nums_in_suit[j], pair_num])
                    if trio[1] == trio[0] + 1 and trio[2] == trio[1] + 1:
                        fans.append(("小三姊妹", 8))
                        break

    # --------------------------------------------------
    # H. 四歸系列：四歸一(5) / 四歸二(10) / 四歸四(20)
    # --------------------------------------------------
    for tile, cnt in tile_counts_non_kong.items():
        if cnt == 4:
            in_pair = (pair == tile)
            in_pong = any(m.type == 'pong' and m.tiles[0] == tile for m in melds)
            chow_appearances = sum(1 for m in chows if tile in m.tiles)

            if chow_appearances == 4:
                fans.append((f"四歸四({TILE_NAMES[tile]})", 20))
            elif in_pair and chow_appearances == 2:
                fans.append((f"四歸二({TILE_NAMES[tile]})", 10))
            elif in_pong and chow_appearances == 1:
                fans.append((f"四歸一({TILE_NAMES[tile]})", 5))

    # --------------------------------------------------
    # I. 門類與色系：清一色(80) / 混一色(30) / 五門齊(10) / 缺一門(5)
    # --------------------------------------------------
    if is_qingyise:
        fans.append(("清一色", 80))
    elif len(suits_present) == 1 and has_honors:
        fans.append(("混一色", 30))
    elif len(suits_present) == 3 and has_winds and has_dragons:
        fans.append(("五門齊", 10))
    elif is_queyimen:
        fans.append(("缺一門", 5))

    # --------------------------------------------------
    # J. 么九系列：斷么(5) / 全帶混么(10) / 全帶么(15) / 混么(30) / 清么(80)
    # --------------------------------------------------
    if is_duanyao:
        fans.append(("斷么", 5))
    elif is_qingyao:
        fans.append(("清么", 80))
    elif all(t in YAOJIU for t in all_tiles):
        fans.append(("混么", 30))
    else:
        every_meld_has_yaojiu = all(any(t in YAOJIU for t in m.tiles) for m in melds) and (pair in YAOJIU)
        if every_meld_has_yaojiu:
            if has_honors:
                fans.append(("全帶混么", 10))
            else:
                fans.append(("全帶么", 15))

    return apply_dealer_and_jihu(fans, ctx)


# ==========================================
# 5. 總入口函數：自動拆牌、找最高番數並計算金額
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
    """
    港式台牌計番主入口：
    - hand_tiles: 手牌列表 (包含最後食胡的那張牌；若無副露則應為 17 張)
    - fixed_melds: 已落地或已固定的副露/暗槓列表 (每組算 3 張手牌額度)
    - ctx: 牌局環境參數 (花數、自摸、莊家、底價等)
    """
    if fixed_melds is None:
        fixed_melds = []
    if ctx is None:
        ctx = GameContext()

    # 特殊情況 0：兩台花 (8隻花) 立即食胡，不須計手牌
    if ctx.is_flower_hu_only or ctx.flower_sets == 2:
        fans = evaluate_common_context_fans(ctx, is_menqing=True, skip_no_flower=True)
        total_fan, fans = apply_dealer_and_jihu(fans, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        return ScoringResult(True, "兩台花(花胡)", total_fan, fans, fixed_melds, None, payout)

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

    # 1. 檢查【十三么 (80番)】
    shisanyao_res = check_shisanyao(hand_tiles, fixed_melds)
    if shisanyao_res is not None:
        pair_tile, extra_meld = shisanyao_res
        fans = [("十三么", 80)]
        fans.extend(evaluate_common_context_fans(ctx, is_menqing=True))
        total_fan, fans = apply_dealer_and_jihu(fans, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "十三么", total_fan, fans, extra_meld, pair_tile, payout))

    # 2. 檢查【十六不搭 / 九唔搭八 (40番)】
    shiliubuda_pair = check_shiliubuda(hand_tiles, fixed_melds)
    if shiliubuda_pair is not None:
        fans = [("十六不搭(九唔搭八)", 40), ("五門齊", 10)]
        if is_suit(shiliubuda_pair) and get_num(shiliubuda_pair) in (2, 5, 8):
            fans.append(("將眼", 1))
        fans.extend(evaluate_common_context_fans(ctx, is_menqing=True))
        total_fan, fans = apply_dealer_and_jihu(fans, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "十六不搭", total_fan, fans, [], shiliubuda_pair, payout))

    # 3. 檢查【嚦咕嚦咕 (40番)】
    ligu_res = check_liguligu(hand_tiles, fixed_melds)
    if ligu_res is not None:
        pairs_list, triplet_tile = ligu_res
        fans = [("嚦咕嚦咕", 40)]
        suits_present = {get_suit(t) for t in all_tiles_flat if is_suit(t)}
        has_winds = any(t in WINDS for t in all_tiles_flat)
        has_dragons = any(t in DRAGONS for t in all_tiles_flat)
        has_honors = has_winds or has_dragons
        if len(suits_present) == 1 and not has_honors:
            fans.append(("清一色", 80))
        elif len(suits_present) == 1 and has_honors:
            fans.append(("混一色", 30))
        elif len(suits_present) == 2:
            fans.append(("缺一門", 5))
        elif len(suits_present) == 3 and has_winds and has_dragons:
            fans.append(("五門齊", 10))
        if all(t not in YAOJIU for t in all_tiles_flat):
            fans.append(("斷么", 5))
        fans.extend(evaluate_common_context_fans(ctx, is_menqing=True))
        total_fan, fans = apply_dealer_and_jihu(fans, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "嚦咕嚦咕", total_fan, fans, [Meld('pong', (triplet_tile,)*3, False)], pairs_list[0], payout))

    # 4. 檢查【標準牌型 (5組面子 + 1對眼)】
    decomps = find_standard_decompositions(hand_tiles, fixed_melds)
    for melds, pair in decomps:
        total_fan, fans = evaluate_standard_decomposition(melds, pair, ctx)
        payout = total_fan * ctx.fan_price + ctx.base_price
        candidates.append(ScoringResult(True, "標準牌型(5面子+1眼)", total_fan, fans, melds, pair, payout))

    if not candidates:
        return ScoringResult(
            is_valid_hu=False,
            hand_pattern_name="詐胡 (未構成胡牌牌型)",
            total_fan=0,
            fan_breakdown=[("詐胡罰款 (赔30番 x 3家)", 90)],
            best_melds=[],
            best_pair=None,
            base_payout=0.0,
            message="輸入的牌無法組成 5組面子+1對眼 或 十三么/十六不搭/嚦咕嚦咕。"
        )

    return max(candidates, key=lambda r: r.total_fan)


# ==========================================
# 6. 拉莊與即時付錢計算器 (依截圖第 3、4 頁規則)
# ==========================================

def calculate_lazhuang_settlement(
    previous_debt: float,
    current_fan: int,
    base_price: float = 10.0,
    fan_price: float = 2.0,
    event_type: str = "continue_win"
) -> Dict[str, float]:
    """
    計算港式台牌「拉莊（乘倍半 1.5x）」與「扣一半」規則：
    - 'continue_win': 上一鋪胡出的，今鋪又胡出 -> 上一鋪輸的錢先乘 1.5 倍，再加上今鋪輸的錢
    - 'counter_win_or_zimo': 輸錢那家自摸或反出沖俾上一鋪贏家 -> 輸了的錢可以扣回一半
    """
    current_hand_amount = current_fan * fan_price + base_price
    if event_type == "continue_win":
        new_total_debt = (previous_debt * 1.5) + current_hand_amount
        return {
            "當鋪基本金額": current_hand_amount,
            "上鋪累積金額": previous_debt,
            "拉莊後最新累積金額 (x1.5 + 今鋪)": new_total_debt
        }
    elif event_type == "counter_win_or_zimo":
        half_deducted = previous_debt / 2.0
        return {
            "原累積欠款": previous_debt,
            "扣減一半後應付金額": half_deducted,
            "當鋪贏回金額": current_hand_amount,
            "淨結算 (正數為應付，負數為倒贏)": half_deducted - current_hand_amount
        }
    return {"當鋪基本金額": current_hand_amount}
