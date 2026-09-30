"""把本地 PRTS 干员档案编译为离线游戏使用的机制事实。

这里只发布可由结构化字段或明确的战斗描述支持的事实。规则是可复用的
能力判定，不保存固定题目；实际四条线索仍由浏览器逐局组合。
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from itertools import combinations
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "干员文字资料" / "全体干员文字资料.json"
OUTPUT = Path(__file__).with_name("事实索引.js")
# 与干员快照相同的 f6a8967a 提交：cn/gamedata/excel/range_table.json。
RANGE_TABLE = json.loads(Path(__file__).with_name("攻击范围表.json").read_text(encoding="utf-8"))
RANGE_GRIDS = {range_id: {(cell["row"], cell["col"]) for cell in info["grids"]}
               for range_id, info in RANGE_TABLE.items()}
CATALOG_OUTPUTS = (Path(__file__).with_name("事实索引_全线索名目.txt"),
                   ROOT / "事实索引_全线索名目.txt")
BRANCH_NAMES = json.loads((ROOT / "干员档案展示版" / "资料映射" / "职业分支名称.json").read_text(encoding="utf-8"))

PINYIN_MAP_FILE = Path(__file__).with_name("干员拼音映射.json")
if PINYIN_MAP_FILE.exists():
    OPERATOR_PINYIN_MAP = json.loads(PINYIN_MAP_FILE.read_text(encoding="utf-8"))
else:
    OPERATOR_PINYIN_MAP = {}

CUSTOM_OPERATOR_PINYIN = {
    "重岳": ["chong", "yue"],
    "仇白": ["qiu", "bai"],
    "吽": ["hong"],
    "调香师": ["tiao", "xiang", "shi"],
    "撷英调香师": ["xie", "ying", "tiao", "xiang", "shi"],
    "伺夜": ["si", "ye"],
}

PROFESSION_ORDER = ("先锋", "近卫", "重装", "狙击", "术师", "医疗", "辅助", "特种")
PROFESSION_RANKS = {
    "先锋": 0, "近卫": 1, "重装": 2, "狙击": 3,
    "术士": 4, "术师": 4, "医疗": 5, "辅助": 6, "特种": 7
}

try:
    import pypinyin
except ImportError:
    pypinyin = None


def get_operator_pinyin_tuple(name: str) -> tuple[str, ...]:
    if name in CUSTOM_OPERATOR_PINYIN:
        return tuple(CUSTOM_OPERATOR_PINYIN[name])
    if name in OPERATOR_PINYIN_MAP:
        return tuple(OPERATOR_PINYIN_MAP[name])
    if pypinyin is not None:
        return tuple(s.lower() for s in pypinyin.lazy_pinyin(name))
    return tuple(name.lower())


def operator_sort_key(profile: dict) -> tuple:
    name = profile["name"]
    prof_rank = PROFESSION_RANKS.get(profile.get("profession"), 8)
    return (prof_rank, get_operator_pinyin_tuple(name), name)


DAMAGE_NAMES = {"physical": "物理", "arts": "法术", "true": "真实", "elemental": "元素"}
# 这些医疗分支的常态普攻是治疗，不产生对敌伤害；咒愈师另有法术攻击。
# 分支依据：PRTS「分支一览」及各分支干员页面的分支信息。
HEALING_ATTACK_BRANCHES = {"physician", "ringhealer", "wandermedic", "watchman", "healer", "chainhealer"}
# PRTS「分支特性信息/data」写明这些分支可对空，回环射手依照
# 高台远程攻击的默认对空规则和分支无特殊限制判定。
# 仅能攻击自身阻挡的飞行单位不计对空；阵法术师仅在发动攻击时适用。
# 没有证据的分支继续保持未知。
NORMAL_AIR_BRANCHES = {
    "agent", "tactician",
    "fastshot", "closerange", "longrange", "reaperrange", "aoesniper",
    "siegesniper", "hunter", "skybreaker", "loopshooter",
    "lord", "shotprotector",
    "corecaster", "splashcaster", "blastcaster", "chain", "funnel",
    "mystic", "phalanx", "primcaster", "soulcaster",
    "slower", "summoner", "blessing", "underminer", "ritualist",
    "supportiveranger", "hookmaster", "traper", "geek",
    "incantationmedic", "alchemist", "skywalker",
}
# 已逐人复核这些分支的技能、天赋、模组和召唤物：常态仅治疗或近战攻击，
# 例外者有对敌伤害技能，不能据分支认定「无对空攻击能力」。
NO_AIR_REVIEWED_BRANCHES = {
    "physician": {"char_003_kalts", "char_345_folnic"},
    "ringhealer": set(),
    "wandermedic": set(),
    "healer": set(),
    "chainhealer": set(),  # Mon3tr 三技能只攻击自身阻挡的敌人。
    "watchman": {"char_1052_kalts2"},
    "bard": {"char_4134_cetsyr", "char_4184_dolris", "char_1012_skadi2"},
    "bearer": {"char_479_sleach"},
}
# 对地近战普攻以外没有独立索敌或范围伤害的干员。此表只列已核过
# 全部技能、天赋、模组的个体；范围技能、反击和召唤物仍留待逐个核对。
NO_AIR_REVIEWED_IDS = {
    # 尖兵：嵯峨二技能明确只命中地面敌人，三技能只攻击阻挡目标。
    "char_4188_confes", "char_362_saga", "char_123_fang", "char_4023_rfalcn",
    "char_115_headbr", "char_149_scave", "char_488_buildr", "char_240_wyvern",
    "char_198_blackd", "char_502_nblade",
    # 冲锋手、武者、无畏者：技能只强化对地近战攻击或攻击阻挡者。
    "char_222_bpipe", "char_220_grani", "char_290_vigna", "char_192_falco",
    "char_1036_fang2", "char_261_sddrag", "char_475_akafyu", "char_337_utage",
    "char_4142_laios", "char_208_melan", "char_154_morgan", "char_131_flameb",
    "char_4011_lessng",
    # 强攻手与处决者：PRTS 明确注明红、槐琥、傀影的部署范围伤害不可对空。
    "char_127_estell", "char_4166_varkis", "char_1026_gvial2",
    "char_356_broca", "char_281_popka", "char_143_ghost",
    "char_144_red", "char_243_waaifu", "char_250_phatom",
    "char_237_gravel", "char_1502_crosly",
    # 教官、解放者、策士：仅使用对地近战攻击的成员。
    "char_265_sophia", "char_4106_bryota", "char_130_doberm",
    "char_485_pallas", "char_308_swire", "char_445_wscoot",
    "char_4199_makiri",
    # 重剑手、决战者、术战者：技能和模组只强化地面选敌，或明示地面目标。
    "char_4083_chimes", "char_4063_quartz", "char_422_aurora",
    "char_416_zumama", "char_185_frncat", "char_350_surtr",
    "char_1019_siege2", "char_4098_vvana", "char_274_astesi",
    "char_333_sidero",
    # 斗士：均为近战普攻及其单体强化，无独立对空伤害。
    "char_157_dagda", "char_137_brownb", "char_415_flint", "char_155_tiger",
    # 守护者及铁卫：攻击只依赖对地近战选敌；其他技能仅治疗或防护。
    "char_196_sunbr", "char_226_hmau", "char_148_nearl", "char_4143_sensi",
    "char_4109_baslin", "char_2025_shu", "char_423_blemsh",
    "char_304_zebra", "char_209_ardign", "char_122_beagle",
    # 第二轮逐人复核：收割者的技能只强化自身对地近战攻击，圣约送葬人的
    # 结束伤害仅回击技能期间已攻击过的目标；武者仍依近战选敌。
    "char_4066_highmo", "char_1032_excu2", "char_491_humus", "char_421_crow",
    "char_188_helage", "char_4121_zuole", "char_4037_demetr",
    # 本源铁卫与不屈者的独立范围伤害明确限定地面；火神仅攻击阻挡者。
    "char_4148_philae", "char_4225_tanya", "char_4235_thumpy", "char_4214_cairn",
    "char_163_hpsts", "char_4130_luton", "char_4207_branch",
    # 工匠装置均只提供友方增益；本体技能未提供对空伤害。
    "char_4178_alanna", "char_4162_cathy", "char_484_robrta",
    "char_433_windft", "char_4212_nasti",
    # 余者的技能仅强化对地普攻、阻挡攻击或施加无伤害控制。
    "char_272_strong", "char_455_nothin", "char_496_wildmn", "char_4187_graceb",
    "char_4036_forcer", "char_241_panda",
    # PRTS：归溟幽灵鲨替身周围持续伤害明确不可对空；若叶睦
    # 二技能明确不可对空，替身不攻击。
    "char_1023_ghost2", "char_4183_mortis",
}
# 第十三轮：用户按「全部能造成伤害的能力」直接裁定原待定 33 人中的
# 31 人没有对空能力。与上面的资料复核清单分开，避免混淆依据来源。
NO_AIR_USER_CONFIRMED_IDS = {
    "char_4131_odda", "char_4132_ascln", "char_4186_tmoris",
    "char_230_savage", "char_4155_talr", "char_1027_greyy2",
    "char_394_hadiya", "char_4039_horn", "char_431_ashlok",
    "char_4220_kormr", "char_493_firwhl", "char_347_jaksel",
    "char_201_moeshd", "char_1049_catap2", "char_1033_swire2",
    "char_391_rosmon", "char_1051_headb2", "char_4058_pepe",
    "char_478_kirara", "char_264_f12yin", "char_215_mantic",
    "char_437_mizuki", "char_4077_palico", "char_112_siege",
    "char_4107_vrdant", "char_4145_ulpia", "char_464_cement",
    "char_1014_nearl2", "char_355_ethan", "char_4185_amoris",
    "char_1001_amiya2",
}
CONTROL_NAMES = {
    "stun": ("晕眩",), "slow": ("停顿",), "root": ("束缚",),
    "freeze": ("冻结",), "cold": ("寒冷",), "sleep": ("沉睡",),
    "levitate": ("浮空",), "silence": ("沉默", "失去特殊能力", "特殊能力失效"), "disarm": ("缴械",),
    "fear": ("恐惧",), "tremble": ("战栗",), "push": ("推开", "推力", "推动", "击退", "弹开"),
    "pull": ("拉拽", "拖拽", "牵引"), "teleport": ("传送",),
}
SURVIVAL = {
    "defense": ("防御力", "防御"), "resistance": ("法术抗性",),
    "dodge": ("闪避",), "shield": ("护盾", "屏障"),
    "shelter": ("庇护", "伤害减免", "伤害抵挡", "伤害-", "不会受到", "伤害减少", "伤害降低"),
    "conceal": ("迷彩", "隐匿"), "max_hp": ("生命上限", "最大生命值", "生命值上限"),
    "resist_status": ("抵抗", "免疫"),
}
OUTPUT_BUFF = {
    "attack": ("攻击力", "伤害提升", "伤害提高", "术法充盈"),
    "speed": ("攻击速度", "攻速"),
    "penetration": ("无视",),
    "ammo": ("弹药上限",),
}

# 审过 PRTS 单人页面的特殊机制；这里只补足不能从客户端短描述推断的事实。
AUDITED = {
    # PRTS：干员 Mon3tr 的「重构体」只承担生命流失、占位和治疗跳跃，
    # 不攻击或施加控制；与凯尔希的同名召唤物不是同一个能力实体。
    "char_4179_monstr": {"summon_no_damage_control": True},
    # 海嗣只延伸浊心斯卡蒂的作用范围；其伤害仍由三技能产生，类型仅为真实伤害且可对空。
    "char_1012_skadi2": {"summon_no_damage_control": True, "air_damage": True},
    # 受击反伤直接选中伤害来源，可伤害飞行敌人，但不属于普通攻击主动对空。
    "char_136_hsguma": {"true_aoe": "三技能切割前方一格内所有敌人", "air_damage": True},
    "char_2014_nian": {"air_damage": True},
    "char_381_bubble": {"air_damage": True},
    # 下列为 PRTS 单人页明示可对空、或技能独立选择敌方远程目标。
    "char_010_chen": {"air_damage": True},  # 二技能「赤霄·拔刀」。
    "char_301_cutter": {"air_damage": True},  # 一技能飞刀主动索敌飞行目标。
    "char_2024_chyue": {"air_damage": True},  # 二技能第一段可对空。
    "char_102_texas": {"air_damage": True},  # 二技能「剑雨」可对空。
    "char_4047_pianst": {"air_damage": True},  # 二技能终结攻击、受击反伤。
    "char_1050_chen3": {"air_damage": True},  # 三技能剑气可对空。
    "char_003_kalts": {"air_damage": True},  # Mon3tr 倒下的范围真实伤害。
    "char_1052_kalts2": {"air_damage": True},  # 二技能医疗单元的范围伤害。
    "char_345_folnic": {"air_damage": True},  # 二技能远程药弹优先索敌敌人。
    "char_4134_cetsyr": {"air_damage": True},  # 二技能微尘碰撞伤害可对空。
    "char_4184_dolris": {"air_damage": True},  # 二技能每 0.3 秒的伤害可对空。
    "char_479_sleach": {"air_damage": True},  # 三技能虽索敌地面，落旗伤害可对空。
    "char_1044_hsgma2": {"air_damage": True},  # 一技能反伤直接选中伤害来源。
    "char_376_therex": {"air_damage": True},  # 天赋爆炸可对空。
    "char_159_peacok": {"air_damage": True},  # 二技能「创世纪」。
    "char_349_chiave": {"air_damage": True},  # 二技能「火焰剥离」。
    "char_4026_vulpis": {"air_damage": True},  # 二技能「坠刃拷问」。
    "char_1028_texas2": {"air_damage": True},  # 三技能剑雨可对空。
    "char_277_sqrrel": {"air_damage": True},  # 二技能水炮范围伤害可对空。
    "char_400_weedy": {"air_damage": True},  # 三技能液氮炮范围伤害可对空。
    "char_017_huang": {"air_damage": True},  # 三技能终结爆炸可对空。
    "char_322_lmlee": {"air_damage": True},  # 二技能标记爆炸可对空。
    "char_214_kafka": {"air_damage": True},  # 二技能部署时的群伤可对空。
    "char_1035_wisdel": {"air_damage": True},  # 天赋残影爆炸可对空。
    "char_4217_makoto": {"air_damage": True},  # 塔纳托斯恐惧斩杀可对空。
    "char_4016_kazema": {"air_damage": True},  # 替身状态下可对空。
    "char_1029_yato2": {"air_damage": True},  # 三技能注明可以攻击空中单位。
    "char_4126_fuze": {"normal_air": "PRTS 导火索分支信息备注：普通攻击可对空"},
    "char_4125_rdoc": {"normal_air": "PRTS 医生分支信息备注：普通攻击可对空"},
    "char_486_takila": {"air_damage": True},  # 天赋受击反弹直指攻击来源。
    "char_4064_mlynar": {"air_damage": True},  # 第二天赋真实伤害反弹直指攻击来源。
    "char_4010_etlchi": {"air_damage": True},  # 二技能血镰可对空。
    "char_4072_ironmn": {"air_damage": True},  # 铁钳号·原型机技能伤害可对空。
    "char_1043_leizi2": {"air_damage": True},  # 二技能攻击可对空。
    "char_420_flamtl": {"air_damage": True},  # 二技能「红松林」PRTS 明注可对空。
    "char_1045_svash2": {"air_damage": True},  # 二、三技能攻击 PRTS 明注可对空。
    "char_2026_yu": {"air_damage": True},  # 二技能先伤害周围所有敌人，再传送地面目标。
    "char_260_durnar": {"air_damage": True},  # 模组受击时对伤害来源追加法术伤害。
    "char_4025_aprot2": {"air_damage": True},  # 模组受击时对伤害来源追加法术伤害。
    "char_378_asbest": {"air_damage": True},  # 模组受击时对伤害来源追加法术伤害。
    "char_4088_hodrer": {"air_damage": True},  # 三技能使攻击自己的敌人持续受到真实伤害。
    "char_4065_judge": {"air_damage": True},  # 天赋受击时直接反伤攻击来源。
    "char_4116_blkkgt": {"air_damage": True},  # 三技能 PRTS 明注可对空。
    "char_4124_iana": {"air_damage": True},  # 一技能溅射 PRTS 明注可对空。
    "char_459_tachak": {"normal_air": "PRTS 战车分支信息备注：普通攻击可对空"},
    "char_252_bibeak": {"air_damage": True},  # 二技能 PRTS 注明可选择飞行单位。
    "char_369_bena": {"normal_air": "PRTS 贝娜天赋备注：替身形态下普通攻击可对空"},
    "char_4009_irene": {"air_damage": True},  # 用户裁定：艾丽妮具备对空伤害能力。
    "char_1030_noirc2": {"air_damage": True},  # 用户裁定：火龙S黑角具备对空伤害能力。
    # 逐人核过普通攻击、全部技能、天赋、模组及召唤物；这里只收录能完整排除对空伤害者。
    # 年／泡泡的受击反伤已确证能伤害飞行目标；可颂另按用户裁定归入无对空。
    "char_202_demkni": {"no_air": "近战普攻；全部技能仅治疗或削弱敌人，无对空伤害"},
    "char_311_mudrok": {"no_air": "近战普攻；二技能仅伤害地面敌人，三技能只攻击被阻挡敌人"},
    "char_150_snakek": {"no_air": "近战普攻；技能仅强化防御或停止攻击"},
    "char_325_bison": {"no_air": "近战普攻；技能仅强化自身及友方防御"},
    "char_284_spot": {"no_air": "近战普攻；技能停止攻击后治疗友方"},
    "char_500_noirc": {"no_air": "近战普攻；无技能，天赋仅强化生存"},
    "char_199_yak": {"no_air": "近战普攻；技能仅强化自身生存"},
    "char_289_gyuki": {"no_air": "近战普攻；技能仅回复自身生命或强化近战攻击"},
    "char_106_franka": {"no_air": "近战普攻；技能与模组仅强化近战攻击"},
    "char_263_skadi": {"no_air": "近战普攻；技能与模组仅强化近战攻击"},
    "char_286_cast3": {"no_air": "近战普攻；无技能与对空伤害天赋"},
    "char_4093_frston": {"no_air": "近战普攻；无技能与对空伤害天赋"},
    "char_4218_aigis": {"normal_air": "特性：起飞后只攻击空中敌人"},
    "char_4213_skybx": {"normal_air": "特性：起飞后只攻击空中敌人"},
    "char_294_ayer": {"normal_air": "领主的普通远程攻击可对空"},
    "char_4219_yukari": {"normal_air": "普通攻击可对空",
                          "output_multi": "二技能对最多四名其他干员施加触发型术法充盈效果"},
    "char_430_fartth": {"range_shrink": "三技能将攻击范围改为前方直线，失去侧方格", "normal_air": "神射手普通攻击可对空"},
    "char_4131_odda": {"skill_inherited_damage": {"锻锤之力": "physical"}},
    "char_4013_kjera": {"skill_inherited_damage": {"心随意动": "arts"}},
    "char_422_aurora": {"skill_inherited_damage": {"人工降雪": "physical"}},
    "char_304_zebra": {"hunger_regen": "一技能增加目标的生命回复速度，可作用于绝食干员", "no_direct_heal": "技能与天赋均无直接治疗"},
    "char_1046_sbell2": {"summon_no_damage_control": True},
    # 造型仪只给所在近战位的单位防御与护盾，也可放在罗比菈塔所在格；装置不攻击。
    "char_484_robrta": {"summon_no_damage_control": True,
                         "self_shield": "天赋「造型仪调试」：造型仪可作用于自身所在近战位，获得防御增益和护盾"},
    # 三技能击倒目标时主动破碎琉璃璧，触发第一天赋的范围伤害与晕眩。
    "char_4080_lin": {"skill_talent_aoe_stun": ("流光乍裂", "计出万全")},
}

# 逐人核对原始技能、天赋和模组后确认的错误归属。保留自动提取规则，
# 但不允许其把自身、召唤物或敌人的效果误记为干员本体／其他干员的效果。
REVIEWED_EXCLUSIONS = {
    "char_4082_qiubai": {"ally:output:attack"},
    "char_426_billro": {"ally:output:attack"},
    "char_476_blkngt": {"ally:output:attack"},
    "char_456_ash": {"ally:output:attack"},
    "char_137_brownb": {"ally:output:attack"},
    "char_423_blemsh": {"ally:output:attack"},
    "char_1035_wisdel": {"ally:output:attack"},
    "char_1019_siege2": {"ally:output:attack"},
    "char_4117_ray": {"ally:output:attack"},
    "char_427_vigil": {"ally:output:penetration", "heal:attack_self"},
    "char_459_tachak": {"ally:output:penetration"},
    "char_4067_lolxh": {"ally:output:penetration"},
    "char_4123_ela": {"ally:output:penetration"},
    "char_350_surtr": {"ally:survival:max_hp", "ally:survival_nonheal"},
    "char_478_kirara": {"heal:hunger"},
    "char_202_demkni": {"heal:hunger"},
    "char_159_peacok": {"control:can:stun"},
    "char_4147_mitm": {"mechanic:stop_attack"},
    "char_1016_agoat2": {"attack:5_hits"},
    "char_4063_quartz": {"debuff:fragile"},
    # 三技能近战复制体可拉拽并晕眩；远程复制体只能束缚，两种形态互斥。
    "char_249_mlyss": {"combo:skill_two_controls:pull:root",
                       "combo:skill_two_controls:root:stun"},
}

# 每条必须描述独立的战斗机制。相近表述共用 topic，不能在同一题里充数。
# 模式仅查最高等级技能的明文；数值模板与这些机制事实另行处理。
SKILL_TEXT_FACTS = (
    ("attack:arts_switch", "攻击", "damage_switch", "有技能能将普通攻击改为法术伤害",
     r"(?<!召唤物)(?<!召唤物的)(?:伤害类型|普攻的?伤害类型)(?:改为|变为|转化为)[^，,；;。]{0,6}法术|(?<!召唤物)(?<!召唤物的)(?:普通攻击|攻击)(?:(?:改为|变为|转化为)[^，,；;。]{0,8}法术伤害|造成(?:相当于[^，,；;。]{0,20})?法术伤害)"),
    ("attack:true_switch", "攻击", "damage_switch", "有技能能将普通攻击改为真实伤害",
     r"(?:伤害类型|普攻的?伤害类型)(?:改为|变为|转化为)[^，,；;。]{0,6}真实|(?:普通攻击|攻击)(?:改为|变为|转化为)[^，,；;。]{0,8}真实伤害"),
    ("attack:physical_switch", "攻击", "damage_switch", "有技能能将普通攻击改为物理伤害",
     r"(?:伤害类型|普攻的?伤害类型)(?:改为|变为|转化为)[^，,；;。]{0,6}物理|(?:普通攻击|攻击)(?:改为|变为|转化为)[^，,；;。]{0,8}物理伤害"),
    ("attack:extra_arts", "攻击", "extra_damage", "有技能能在原有攻击外追加法术伤害",
     r"(?:(?:额外|追加|附加)(?!\s*攻击[一1\d]个目标)(?:对[^，。]{0,12})?(?:造成|受到)?|附带(?!.{0,10}效果的(?:敌人|敌方|目标)))(?:一次)?(?:相当于|每秒)?[^，。]{0,25}法术伤害(?!\d+%的.{0,8}损伤)"),
    ("attack:extra_true", "攻击", "extra_damage", "有技能能在原有攻击外追加真实伤害",
     r"(?:额外|追加|附带).{0,35}真实伤害"),
    ("attack:splash", "攻击", "attack_spread", "有技能能造成溅射伤害",
     r"溅射(?:物理|法术|真实)?伤害|攻击溅射到"),
    ("attack:bounce", "攻击", "attack_spread", "有技能能使攻击在目标间弹射",
     r"(?:攻击|子弹|箭矢|投射物).{0,22}弹射|弹射.{0,20}(?:敌人|目标)"),
    ("attack:pierce", "攻击", "attack_spread", "有技能能使攻击穿透敌人",
     r"(?:攻击|子弹|箭矢|投射物).{0,25}(?:穿透|贯穿).{0,25}(?:敌人|目标)|(?:穿透|贯穿).{0,20}(?:敌人|目标)"),
    ("attack:chain", "攻击", "attack_spread", "有技能能造成攻击在敌人间跳跃传导",
     r"(?<!每次治疗的)(?<!治疗的)(?<!治疗)(?:在(?:敌人|目标)间.{0,15}跳跃|跳跃至其他.{0,10}敌人|并流连锁|(?:次攻击|普攻|弹跳|箭矢|投射物|法术).{0,15}跳跃|攻击在.{0,15}跳跃|最多在\d+个(?:目标|敌人)间跳跃)"),
    ("attack:random_target", "目标", "target_priority", "有技能会随机选择攻击目标",
     r"随机攻击.{0,20}(?:敌人|目标)|随机(?:一名|一个)?(?:敌人|目标).{0,8}(?:攻击|造成)|"
     r"随机对.{0,25}(?:敌人|目标).{0,8}(?:攻击|造成|发射)|攻击.{0,10}随机(?:敌人|目标)"),
    ("target:elite_first", "目标", "target_priority", "有技能优先作用或仅作用于精英或领袖敌人",
     r"(?:优先(?:攻击)?.{0,5}|只(?:以|攻击).{0,5})(?:精英|领袖)"),
    ("target:blocked_first", "目标", "target_priority", "有技能仅攻击或优先攻击被阻挡的敌人",
     r"(?:优先攻击|优先对|仅选择|只攻击)(?:[^，；。]{0,10}(?<!没有)(?<!未)被阻挡|(?:自身|我方|友方)阻挡的)"),
    ("target:unblocked_first", "目标", "target_priority", "有技能优先攻击未被阻挡的敌人",
     r"优先攻击(?:没有被|未被|未)阻挡"),
    ("attack:interval_longer", "攻击", "attack_tempo", "有技能会延长自身攻击间隔",
     r"(?:^|[，；:：]|但|和)(?:自身)?(?:攻击前摇和)?攻击间隔(?:略微|稍微|较小幅度|较大幅度|大幅度|小幅度|大幅|小幅)?(?:延长|增大|增加)"),
    ("attack:speed_up", "攻击", "attack_tempo", "有技能能提高自身攻击速度",
     r"(?:^|[，；:：]|(?:使)?自身|自己的)(?:的)?攻击速度\+(?:[1-9]\d*)"),
    ("attack:speed_down", "攻击", "attack_tempo", "有技能会降低自身攻击速度",
     r"(?:^|[，；])(?:自身)?攻击速度(?:略微|较大幅度|大幅)?(?:降低|减少|下降|-\d+)"),
    ("heal:extra_target", "恢复", "heal_targets", "有技能可以额外治疗一名或多名友方单位",
     r"额外治疗(?:一名|[2-9]名|一个|[2-9]个)"),
    ("heal:all_allies", "恢复", "heal_targets", "有技能可以治疗范围内所有友方单位",
     r"(?:治疗|恢复|回复)[^，,；;。\n]{0,22}(?:范围内|攻击范围内|周围(?:的)?)[^，,；;。\n]{0,15}所有(?:友[方军]|我方)|"
     r"(?:范围内|攻击范围内|周围(?:的)?).{0,15}所有(?:友[方军]|我方).{0,30}(?:治疗|恢复|回复)(?![^，,；;。\n]{0,20}损伤)"),
    ("survival:physical_dodge", "生存", "dodge_type", "有技能提供物理闪避",
     r"物理(?:和法术|与法术|及法术)?闪避|法术(?:和|与|及)物理闪避"),
    ("survival:arts_dodge", "生存", "dodge_type", "有技能提供法术闪避",
     r"法术(?:和物理|与物理|及物理)?闪避|物理(?:和|与|及)法术闪避"),
    ("survival:conceal", "生存", "conceal", "有技能可以提供迷彩或隐匿效果",
     r"(?:获得|进入|赋予|施加)(?:.{0,10})(?:迷彩|隐匿)"),
    ("survival:resist_status", "生存", "status_resist", "有技能赋予抵抗效果",
     r"(?:获得|具有|施加|赋予).{0,8}抵抗(?:效果|状态|，|；|$)"),
    ("survival:undying", "生存", "survival_last_stand", "有技能使自身生命值暂时不会降至零",
     r"(?:自身|干员的)生命值(?:始终)?不会低于1|不会被击倒"),
    ("survival:invincible", "生存", "survival_last_stand", "有技能可以获得无敌状态",
     r"(?:自身|自己).{0,20}无敌|(?:获得|进入)无敌(?:状态|效果)|(?:无法行动且)?不受到伤害"),
    ("survival:status_immunity", "生存", "status_resist", "有技能可以免疫异常状态或控制效果",
     r"(?:自身)?免疫.{0,15}(?:异常状态|控制状态|控制效果|晕眩|寒冷|冻结|沉睡|停顿|束缚)"),
    ("skill:floating_unit", "召唤", "deployable_kind", "有技能会释放浮游单元攻击敌人",
     r"释放浮游单元(?:随机)?锁定.{0,25}(?:进行)?攻击"),
    ("skill:detonate", "技能", "skill_detonation", "技能中的召唤物可以被引爆",
     r"(?:召唤物|装置|陷阱|无人机|炮台|浮游单元|机械水獭|矿石[\"“]杀手[\"”]|矿石杀手|樱桃三号).{0,30}引爆|"
     r"引爆.{0,20}(?:召唤物|装置|陷阱|无人机|炮台|浮游单元|机械水獭|矿石[\"“]杀手[\"”]|矿石杀手|樱桃三号)"),
    ("skill:refresh", "技能", "skill_refresh", "有技能可以刷新技力、技能或再部署时间",
     r"(?:刷新|(?<!不)重置).{0,20}(?:技力|技能|再部署)|(?:立即|立刻)恢复所有技力"),
    ("skill:ramp", "技能", "skill_ramp", "有技能的效果会随持续时间逐渐增强",
     r"(?:攻击力|防御力|伤害|效果).{0,15}逐渐(?:增加|提升|提高|增至)|逐渐(?:增加|提升|提高|增至).{0,18}(?:攻击力|防御力|伤害|效果)"),
    ("skill:stack", "技能", "skill_stack", "有技能效果可以叠加多层",
     r"(?:最多|可)叠加[2-9]层"),
    ("skill:two_phase", "技能", "skill_phase", "有技能再次使用时会发生变化",
     r"第二次(?:开启|使用)时|再次开启时|第二次及以后使用时"),
    ("skill:passive_active", "技能", "skill_phase", "有技能同时拥有被动和主动效果",
     r"(?:被动(?:效果)?[:：].{0,350}(?:主动(?:效果|开启|触发)?|开启|自动开启)[:：]|(?:主动(?:效果|开启|触发)?|开启|自动开启)[:：].{0,350}被动(?:效果)?[:：]|被动(?:效果)?[:：].{0,80}主动触发)"),
    ("skill:redeploy_reduction", "技能", "redeploy", "有技能可以缩短召唤物的再部署时间",
     r"(?:召唤物|无人机|炮台|沙地兽|[“「][^”」]{1,12}[”」]).{0,15}再部署时间(?:缩短|减少|-)"),
    ("skill:dp_refund", "技能", "skill_dp", "有技能可以返还部署费用",
     r"返还.{0,18}部署费用"),
    ("skill:deploy_cost_down", "技能", "skill_dp", "有技能可以降低部署费用",
     r"(?:部署)?费用(?:降低|减少|-\d+)"),
    ("debuff:hit_rate", "削弱", "debuff_hit_rate", "有技能可以降低敌人的命中率",
     r"(?:敌人|敌方|目标).{0,30}(?:物理与法术)?命中率(?:-|降低|减少)"),
)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or "").replace("\\n", "，"))).strip()


def expand_skill_values(description: object, params: dict[str, object]) -> str:
    """只展开技能本等级已提供的数值，避免把模板占位符展示给玩家。"""
    normalized = {str(key).casefold(): value for key, value in params.items()}
    def replace(match: re.Match[str]) -> str:
        token, _, fmt = match.group(1).partition(":")
        negative = token.startswith("-")
        key = token[1:] if negative else token
        value = normalized.get(key.casefold())
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "数值未标注"
        number = -float(value) if negative else float(value)
        if "%" in fmt:
            precision = re.search(r"\.(\d+)", fmt)
            return f"{number * 100:.{int(precision.group(1)) if precision else 0}f}%"
        return str(int(number)) if number.is_integer() else f"{number:g}"
    return clean(re.sub(r"\{([^{}]+)\}", replace, str(description or "")))


def compact(value: str, limit: int = 125) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def phase_number(value: dict) -> int:
    return int(str((value.get("解锁条件") or {}).get("阶段", "PHASE_0")).split("_")[-1])


def highest_talents(basic: dict) -> list[tuple[str, str]]:
    result = []
    for group in basic.get("天赋列表") or []:
        pool = [x for x in group.get("候选项列表") or []
                if not x.get("所需潜能等级") and not x.get("是否隐藏天赋")
                and clean(x.get("描述")) not in {"", "？？？？？"}]
        if pool:
            chosen = max(pool, key=lambda x: (phase_number(x), (x.get("解锁条件") or {}).get("等级") or 0))
            result.append((clean(chosen.get("名称")), clean(chosen.get("描述"))))
    return result


def module_effects(operator: dict) -> list[dict]:
    result = [{"id": "base", "name": "不装备专属模组", "trait": [], "talent": {}, "extra": [], "cost_change": False}]
    for module in operator.get("模组资料") or []:
        info = module.get("模组资料") or {}
        name = clean(info.get("模组名称"))
        # 特限证章属于特殊玩法的授权效果，不计入干员自身能力。
        if info.get("类型") == "INITIAL" or "特限证章" in name:
            continue
        stages = (module.get("战斗数据") or {}).get("阶段资料") or []
        if not stages:
            continue
        stage = max(stages, key=lambda x: x.get("装备等级") or 0)
        item = {"id": module["模组ID"], "name": name,
                "trait": [], "talent": {}, "extra": [], "cost_change": False}
        for component in stage.get("组成部件") or []:
            for candidate in (component.get("覆盖特性数据集合") or {}).get("候选项列表") or []:
                if candidate.get("所需潜能等级") or 0:
                    continue
                params = {x.get("键值"): x.get("数值") for x in candidate.get("参数表") or []}
                phrase = expand_skill_values(candidate.get("覆盖说明") or candidate.get("补充描述"), params)
                if phrase:
                    item["trait"].append(phrase)
            for candidate in (component.get("新增或覆盖天赋数据集合") or {}).get("候选项列表") or []:
                if candidate.get("所需潜能等级") or 0:
                    continue
                number = candidate.get("天赋序号")
                params = {x.get("键值"): x.get("数值") for x in candidate.get("参数表") or []}
                phrase = expand_skill_values(candidate.get("升级说明") or candidate.get("描述"), params)
                if isinstance(number, int) and number >= 0 and phrase:
                    item["talent"][number] = (clean(candidate.get("名称")), phrase)
                elif phrase:
                    item["extra"].append(phrase)
        for parameter in stage.get("属性参数表") or []:
            if parameter.get("键值") in {"cost", "dp_cost"}:
                item["cost_change"] = True
                item["cost_delta"] = int(parameter.get("数值") or 0)
        result.append(item)
    return result


def max_potential_cost(basic: dict) -> int:
    phase = (basic.get("阶段资料") or [])[-1]
    nodes = phase.get("属性成长节点") or []
    cost = int((nodes[-1].get("数据") or {}).get("部署费用") or 0)
    for potential in basic.get("潜能提升资料") or []:
        for change in (((potential.get("增益") or {}).get("属性") or {}).get("属性修正值") or []):
            if change.get("属性类型") == "COST" and change.get("配方物品") == "ADDITION":
                cost += int(change.get("数值") or 0)
    return cost


def make_profile(operator: dict) -> dict:
    form_id = operator["形态ID列表"][0]
    basic = operator["形态资料"][form_id]["干员基础数据"]
    rarity_text = str(basic.get("稀有度") or "")
    rarity = int(re.search(r"\d+", rarity_text).group())
    # 兼容修正前档案的旧写法；正式快照使用与 PRTS 一致的 1～6 星。
    if rarity_text.endswith("星") and rarity > 6:
        raise ValueError(f"异常星级：{operator['干员名称']} {rarity_text}")
    talents = highest_talents(basic)
    phases = basic.get("阶段资料") or []
    final_nodes = (phases[-1].get("属性成长节点") or []) if phases else []
    base_block = ((final_nodes[-1].get("数据") or {}).get("阻挡数")
                  if final_nodes else None)
    skills = []
    for skill in basic.get("技能列表") or []:
        record = (operator.get("技能资料") or {}).get(skill.get("技能编号")) or {}
        levels = record.get("多等级资料") or []
        if levels:
            level = levels[-1]
            params = {x.get("键值"): x.get("数值") for x in level.get("参数表") or []}
            params.setdefault("duration", level.get("时长"))
            skills.append({"id": skill.get("技能编号"), "name": clean(level.get("名称")),
                           "text": expand_skill_values(level.get("描述"), params),
                           "range_id": level.get("攻击范围编号"),
                           "params": params, "activation": level.get("技能类型"),
                           "sp_type": (level.get("技力数据") or {}).get("技力类型"),
                           "sp_cost": (level.get("技力数据") or {}).get("技力消耗"),
                           "initial_sp": (level.get("技力数据") or {}).get("初始技力"),
                           "duration": level.get("时长"),
                           "duration_type": level.get("时长类型")})
    trait_candidates = (basic.get("特性") or {}).get("候选项列表") or []
    trait_params = {}
    if trait_candidates:
        candidate = max(trait_candidates, key=lambda x: (phase_number(x),
                        (x.get("解锁条件") or {}).get("等级") or 0))
        trait_params = {x.get("键值"): x.get("数值") for x in candidate.get("参数表") or []}
    return {"id": form_id, "name": operator["干员名称"], "profession": basic.get("职业") or "",
            "branch": basic.get("职业分支编号") or "", "rarity": rarity,
            "position": basic.get("部署位置") or "",
            "archive": f"../干员档案展示版/干员档案/{operator['干员名称']}.html",
            "trait": expand_skill_values(basic.get("描述"), trait_params), "talents": talents, "skills": skills,
            "base_block": base_block,
            "base_range_id": phases[-1].get("攻击范围编号") if phases else None,
            "modules": module_effects(operator), "cost_maxpot": max_potential_cost(basic),
            "has_summons": bool(basic.get("显示召唤物索引") or operator.get("召唤物资料"))}


def sources_for(profile: dict, module: dict, skill: dict | None) -> list[tuple[str, str]]:
    sources = [("特性", profile["trait"])]
    for index, (name, phrase) in enumerate(profile["talents"]):
        replacement = module["talent"].get(index)
        sources.append((f"天赋「{name}」" + (f"／模组「{module['name']}」" if replacement else ""),
                        replacement[1] if replacement else phrase))
    for phrase in module["trait"]:
        sources.append((f"模组「{module['name']}」", phrase))
    for phrase in module["extra"]:
        sources.append((f"模组「{module['name']}」", phrase))
    if skill:
        sources.append((f"技能「{skill['name']}」", skill["text"]))
    return sources


def deals_typed_damage(phrase: str, label: str) -> bool:
    """伤害词必须描述出手，而非吸收、抵挡、减免或单纯承受伤害。"""
    for sentence in re.split(r"[；;。\n]", phrase):
        clauses = re.split(r"[，,]", sentence)
        for index, clause in enumerate(clauses):
            # 技能代价给自己或友方造成伤害，不表示能伤害敌人。
            if re.search(rf"(?:对自身|对自己|对友方|对我方).{{0,18}}造成.{{0,25}}{label}伤害|"
                         rf"(?:自身|自己|友方|我方).{{0,15}}受到.{{0,25}}{label}伤害", clause):
                if not re.search(rf"(?:敌人|敌方|目标).{{0,25}}受到.{{0,25}}{label}伤害", clause):
                    continue
            if re.search(rf"伤害类型变为{label}|攻击(?:改为|变为).{{0,35}}{label}伤害", clause):
                return True
            if re.search(rf"(?:造成|附带|附加|引爆|转化为).{{0,90}}{label}伤害", clause):
                return True
            if re.search(rf"(?:敌人|敌方|目标).{{0,90}}受到.{{0,90}}{label}伤害", clause):
                return True
            # 处理“攻击使目标中毒，在3秒内每秒受到75点法术伤害”等后分句省略目标主语的情形
            if re.search(rf"受到.{{0,50}}{label}伤害", clause):
                preceding = "".join(clauses[:index + 1])
                if (re.search(r"敌人|敌方|目标|经过的|令其|使之|使其", preceding)
                        and not re.search(r"自身|自己|友方|我方|友军", clause)):
                    return True
    return False


def inflicts_elemental_loss(phrase: str, kind: str | None = None) -> bool:
    """只承认施加给敌方的损伤；友方损伤治疗和减免不属于伤害。"""
    loss = re.escape(kind) if kind else r"(?:元素|凋亡|灼燃|神经|侵蚀|狂躁)"
    for clause in re.split(r"[，,；;。\n]", phrase):
        if re.search(rf"(?:恢复|回复|治疗|吸收|降低|减少).{{0,28}}{loss}损伤", clause):
            continue
        if re.search(rf"(?:造成(?!的)|附带|施加).{{0,70}}{loss}损伤", clause):
            return True
        if re.search(rf"(?:敌人|敌方|目标).{{0,55}}受到(?!的).{{0,25}}{loss}损伤", clause):
            return True
    return False


def deals_weakpoint_damage(phrase: str) -> bool:
    """弱点伤害可按目标防御属性转成物理或法术伤害。"""
    return bool(re.search(
        r"攻击(?:变为|改为)弱点伤害|"
        r"攻击[^，；。]{0,70}造成[^，；。]{0,30}弱点伤害|"
        r"造成的(?:物理和法术)?伤害变为弱点伤害", phrase))


def damage_types(profile: dict, sources: list[tuple[str, str]]) -> set[str]:
    trait = profile["trait"]
    result = set()
    if profile["branch"] == "artsprotector":
        result.update(("physical", "arts"))
    elif deals_typed_damage(trait, "法术"):
        result.add("arts")
    elif deals_typed_damage(trait, "真实"):
        result.add("true")
    elif (profile["branch"] not in HEALING_ATTACK_BRANCHES
          and not re.match(r"^(?:通常时|通常)?不(?:进行普通)?攻击", trait)):
        result.add("physical")
    for _, phrase in sources:
        if deals_weakpoint_damage(phrase):
            result.update(("physical", "arts"))
        if deals_typed_damage(phrase, "物理"):
            result.add("physical")
        if deals_typed_damage(phrase, "法术"):
            result.add("arts")
        if deals_typed_damage(phrase, "真实"):
            result.add("true")
        if deals_typed_damage(phrase, "元素"):
            result.add("elemental")
        if inflicts_elemental_loss(phrase):
            result.add("elemental")
    return result


def control_types(sources: list[tuple[str, str]]) -> set[str]:
    result = set()
    for _, phrase in sources:
        # PRTS：对敌人连续施加两层寒冷会触发冻结；例如灵知「零度爆发」蓄力。
        if (re.search(r"(?:敌人|敌方|目标).{0,25}造成.{0,12}寒冷", phrase)
                and "额外造成一层寒冷" in phrase):
            result.add("freeze")
        for code, words in CONTROL_NAMES.items():
            for word in words:
                matches = list(re.finditer(re.escape(word), phrase))
                if not matches:
                    continue
                for match in matches:
                    before = phrase[max(0, match.start() - 65):match.start()]
                    after = phrase[match.end():match.end() + 22]
                    if code == "teleport" and (after.startswith("带") or not re.search(
                            r"(?:敌人|敌方|目标).{0,40}传送|传送.{0,40}(?:敌人|敌方|目标)", phrase)):
                        continue
                    # 已处于某状态、攻击该状态的敌人及自身/友方受控都不是施加控制。
                    # 技能结束后的无目标晕眩属于自身/召唤物代价；明确写出敌人时才收录。
                    if (code == "stun" and re.search(r"(?:结束|部署)后[^，；。]{0,15}$", before)
                            and not re.match(r"(?:(?:所有|全部|周围|附近|范围内|地面|空中|未阻挡的)){0,2}(?:敌人|敌方|目标)", after)):
                        continue
                    latest_subject = re.split(r"[，；。]|(?:并|且)(?=使|令|让)", before)[-1]
                    clean_subject = re.sub(r"(?:向|至)(?:自己|自身)中心(?:小幅度|大幅度)?|目标点",
                                           lambda m: "友方位置" if m.group(0) == "目标点" else "",
                                           latest_subject)
                    subjects = re.findall(r"自身|自己|友方|我方|友军|敌人|敌方|目标|攻击来源", clean_subject)
                    if subjects and subjects[-1] in {"自身", "自己", "友方", "我方", "友军"}:
                        if not re.match(r"(?:所有|全部|周围|地面|空中|未阻挡的)?(?:敌人|敌方|目标)", after):
                            continue
                    if code not in {"teleport", "silence"}:
                        passive_before = before
                        if re.search(r"(?:敌人|敌方|目标)被$", before):
                            passive_before = before[:-1]
                        if re.search(r"(?:若|如果|当|攻击|对|敌人|目标).{0,35}(?:已经处于|已处于|处于|在被|(?<!未)被(?!(?:自身|友方|我方)?阻挡))[^，；。]{0,20}$", passive_before):
                            continue
                        if re.search(r"(?:目标|敌人|敌方).{0,8}(?:已经|已)?(?:处于|在被|(?<!未)被(?!(?:自身|友方|我方)?阻挡))[^，；。]{0,10}$", passive_before):
                            continue
                    if re.match(r"(?:状态)?的(?:敌人|目标|单位)|(?:敌人|目标)(?:时|若|受到|被|的)", after):
                        continue
                    if re.match(r"(?:延长|时间刷新|效果提升|状态的|结束时)", after):
                        continue
                    if re.search(r"(?:使|令|让|赋予|获得|进入|受到|陷入)[^，；。]{0,18}(?:自身|自己|友方|我方|友军)(?![^，；。]{0,15}(?:敌人|敌方|目标))[^，；。]{0,12}$", before):
                        continue
                    if re.search(r"(?:免疫|抵抗)[^，；。]{0,8}$", before):
                        continue
                    if re.search(r"(?:结束(?!后)|解除|抵消|免疫|刷新|延长)[^，；。]{0,8}$", before):
                        continue
                    if re.search(r"造成(?:停顿|恐惧|寒冷|冻结|晕眩|束缚)(?:、(?:停顿|恐惧|寒冷|冻结|晕眩|束缚))*时使", phrase[max(0, match.start() - 20):match.end() + 12]):
                        continue
                    result.add(code)
                    break
    return result


def ally_effect(sources: list[tuple[str, str]], terms: dict, require_multi: bool = False,
                skills: list[dict] | None = None) -> tuple[str, str] | None:
    recipient_pattern = (r"(?:其他|其余|友方|我方).{0,28}(?:干员|单位|角色)|友军|"
                         r"一名(?:近战|远程)位上的单位|"
                         r"(?:所有|全体|全场|场上|在场(?!时)|多名|周围|附近|范围内|自己身后|前方|身前).{0,30}"
                         r"(?:干员|友方单位|我方单位|友军|角色)|【[^】]+】干员|"
                         r"(?:Ave Mujica|颂乐人偶)成员|"
                         r"所有初始部署费用[^，；。]{0,20}单位|"
                         r"(?:携带.{0,20}技能|装置天赋生效)的干员|"
                         r"(?:治疗的)?(?:所有)?目标")
    for label, phrase in sources:
        clauses = re.split(r"[，,；;。\n]", phrase)
        for index, clause in enumerate(clauses):
            if not clause:
                continue
            # 「这个效果」承接前一句的属性增益，例如能天使模组把攻击与生命增益赋予两名友方。
            effect_clause = clause
            if re.search(r"(?:这个|该|此)效果.{0,16}(?:赋予|给予|施加)给", clause):
                preceding = phrase.split(clause, 1)[0].rstrip("，,；;。\n")
                effect_clause = preceding.rsplit("。", 1)[-1] + "，" + clause
            elif re.search(r"其他【[^】]+】干员获得.{0,16}提高效果", clause):
                # 「提高效果」指代前文已明写的自身属性增益，例如乌尔比安。
                effect_clause = phrase.split(clause, 1)[0] + "，" + clause
            elif "相同效果" in clause and re.search(r"自己身后的干员", clause):
                effect_clause = phrase.split(clause, 1)[0] + "，" + clause
            recipient_clause = clause
            if index and clauses[index - 1]:
                previous = clauses[index - 1]
                between = phrase.split(previous, 1)[-1].split(clause, 1)[0]
                pronoun_continuation = bool(re.search(
                    r"^(?:使其|使目标|自身与其|自身和其|超过目标|每次治疗使目标|且其中每个干员)", clause))
                single_output_continuation = (not require_multi
                    and all(code in OUTPUT_BUFF for code in terms)
                    and bool(re.search(r"^(?:攻击力|攻击速度|攻速|且造成的|且自身|且获得)", clause))
                    and bool(re.search(r"(?:干员|单位|友军|角色|目标).{0,35}(?:\+|获得|提高|提升|增加)", previous)))
                survival_continuation = (not require_multi and bool(re.search(
                    r"^(?:防御力|法术抗性|生命上限|最大生命值|获得|并获得)", clause))
                    and bool(re.search(r"(?:干员|单位|友军|目标).{0,35}(?:\+|获得|提高|提升|施加|免疫)", previous)))
                collective_continuation = (all(code in OUTPUT_BUFF for code in terms)
                    and bool(re.search(r"^且(?:攻击力|攻击速度|攻速)", clause))
                    and bool(re.search(r"使(?:所有|全体).{0,25}干员获得", previous)))
                sp_continuation = ("sp" in terms
                    and bool(re.search(r"^且(?:技力|每秒技力|初始技力)", clause))
                    and bool(re.search(recipient_pattern, previous)))
                if (re.fullmatch(r"[，,：:\n\s]+", between)
                        and (pronoun_continuation or single_output_continuation
                             or survival_continuation or collective_continuation or sp_continuation)
                        and re.search(recipient_pattern, previous)):
                    recipient_clause = previous + "，" + clause
            if re.search(r"(?:没有|不存在|不含).{0,12}(?:友方|我方|其他).{0,12}(?:干员|单位)", clause):
                continue
            recipient = re.search(recipient_pattern + r"|该干员", recipient_clause)
            if not recipient:
                continue
            if re.search(r"(?:存在|没有|至少有).{0,25}(?:干员|单位).{0,4}时改为(?:攻击力|攻击速度|攻速)", recipient_clause):
                continue
            # 友方仅作为触发条件、真正增强的是自身时，不能算友方增益。
            if re.search(r"(?:友方|我方).{0,15}(?:干员|单位).{0,12}使(?!其)(?:自身|自己|[\u4e00-\u9fff·]{2,8})(?:的)?(?:攻击力|攻击速度|攻速)", recipient_clause):
                continue
            if require_multi:
                # 「范围内一名干员」虽同时命中范围词，也只有一个受益者。
                if re.search(r"(?:一|1)(?:名|位|个)(?:随机)?(?:其他|友方|我方)?(?:干员|单位|角色)", recipient_clause):
                    continue
                if re.search(r"(?:一名|一位|一个|1名|1位|1个).{0,18}(?:友方|我方|其他|【[^】]+】).{0,15}(?:干员|单位)|(?:友方|我方|其他).{0,15}(?:一名|一位|一个|1名|1位|1个)", recipient_clause):
                    continue
                if re.search(r"(?:当前复制的|随机另一名|其他随机一名).{0,15}干员", recipient_clause):
                    continue
                if re.search(r"(?:存在|没有|至少有).{0,25}(?:友方|我方|其他|【[^】]+】).{0,15}(?:干员|单位).{0,5}时(?:改为)?", recipient_clause):
                    continue
                if re.search(r"(?:攻击力|攻击速度|攻速|伤害)(?:最高|最低)的(?:攻击力|攻击速度|攻速|伤害)", recipient_clause):
                    continue
                plural = bool(re.search(r"(?:所有|全体|全场|多名|周围|附近|场上|在场(?!时)|范围内).{0,30}(?:干员|单位|友军|角色)", recipient_clause))
                capped = bool(re.search(r"最多(?:[2-9]|\d{2,})名.{0,12}(?:干员|单位)", recipient_clause))
                counted = bool(re.search(r"(?:两|二|三|四|五|六|七|八|九|[2-9]|\d{2,})名(?:随机)?(?:友方|我方|其他)(?:干员|单位)", recipient_clause))
                collective = bool(re.search(r"(?:其他|其余|在场|场上)?(?:友方)?(?:近战|远程|地面|高台|先锋|近卫|重装|狙击|术师|医疗|辅助|特种)(?:干员|单位)|其他.{0,12}干员|【[^】]+】干员|(?:Ave Mujica|颂乐人偶)成员|"
                                            r"(?:携带.{0,20}技能|装置天赋生效)的干员", recipient_clause))
                if not plural and not capped and not counted and not collective:
                    continue
            for code, words in terms.items():
                if any(word in effect_clause for word in words):
                    pre_verb = (re.search(r"(?:回复|恢复|增加|提高|提升|赋予|提供|给予|获得)[^，,；;。\n]{0,8}$", recipient_clause[:recipient.start()]).group(0)
                                if re.search(r"(?:回复|恢复|增加|提高|提升|赋予|提供|给予|获得)[^，,；;。\n]{0,8}$", recipient_clause[:recipient.start()]) else "")
                    benefit = (effect_clause if effect_clause != clause
                               else (pre_verb + recipient_clause[recipient.end():]))
                    if code in OUTPUT_BUFF and words == OUTPUT_BUFF[code]:
                        if code == "attack" and not re.search(
                                r"攻击力(?:和防御力)?(?:\+|提高|提升|增加|上升|提升至)|"
                                r"(?:提高|提升|增加).{0,10}攻击力|"
                                r"(?:造成的)?(?:物理|法术|真实|元素)?伤害(?:提高|提升|增加|\+)|"
                                r"获得.{0,45}攻击力.{0,15}鼓舞|术法充盈", benefit):
                            continue
                        if code == "speed" and not re.search(
                                r"(?:攻击速度|攻速)(?:\+|提高|提升|增加|上升)|"
                                r"(?:提高|提升|增加).{0,10}(?:攻击速度|攻速)|获得\d+攻速", benefit):
                            continue
                        if code == "penetration" and not re.search(r"无视.{0,16}(?:防御力|法术抗性)", benefit):
                            continue
                        if code == "ammo" and not re.search(r"弹药上限\+\d+|补弹\d+", benefit):
                            continue
                    if code in SURVIVAL and words == SURVIVAL[code]:
                        survival_patterns = {
                            "defense": r"防御力(?:各)?(?:\+|提高|提升|增加)|防御\+|获得.{0,45}防御力.{0,15}鼓舞|攻击力(?:和|与)防御力\+",
                            "resistance": r"法术抗性(?:额外)?(?:\+|提高|提升|增加)|获得.{0,15}法术抗性",
                            "dodge": r"(?:获得|提供|赋予).{0,25}闪避|闪避(?:\+|提高|提升)",
                            "shield": r"(?:获得|提供|赋予|施加|转化为).{0,30}(?:护盾|屏障)",
                            "shelter": r"(?:获得|提供|赋予|施加).{0,25}庇护|伤害(?:减免|抵挡)|(?<!自然环境的)受到(?!来自(?:自然)?环境).{0,20}伤害(?:减少|降低|-)|不会受到(?!来自(?:自然)?环境).{0,20}伤害",
                            "conceal": r"(?:获得|提供|赋予|施加).{0,20}(?:迷彩|隐匿)",
                            "max_hp": r"(?:生命上限|最大生命值)(?:\+|提高|提升|增加)|获得.{0,45}(?:生命上限|最大生命值|生命值上限).{0,15}鼓舞",
                            "resist_status": r"(?:获得|提供|赋予|施加).{0,20}抵抗|使目标获得抵抗",
                        }
                        if not re.search(survival_patterns[code], benefit):
                            continue
                    if code == "sp" and not re.search(r"(?:回复|恢复|获得|增加|初始).{0,25}技力|技力.{0,25}(?:\+|回复)", benefit):
                        continue
                    if code == "sp" and re.search(r"自身.{0,12}(?:回复|恢复|获得).{0,12}技力", benefit):
                        continue
                    return code, f"{label}：{compact(phrase if effect_clause != clause or recipient_clause != clause else clause)}"
    return None


def direct_heal(sources: list[tuple[str, str]]) -> bool:
    for _, phrase in sources:
        for clause in re.split(r"[；;。\n]", phrase):
            if ("治疗" in clause or re.search(r"(?:恢复|回复).{0,8}生命", clause)) and not re.search(r"(?:每秒|生命回复速度|持续恢复)", clause):
                return True
    return False


def own_regen(sources: list[tuple[str, str]]) -> tuple[str, str] | None:
    for label, phrase in sources:
        if "持续恢复范围内所有友军生命（每秒恢复" in phrase or "持续恢复范围内所有友方生命" in phrase:
            return label, compact(phrase)
        for clause in re.split(r"[；;。\n]", phrase):
            if re.search(r"(?:友方|我方|其他).{0,18}(?:干员|单位).{0,45}生命回复速度", clause):
                return label, compact(phrase)
            m = re.search(r"(?:所有|全体|全场|全地图|周围|附近|范围内|攻击范围内|场上|地块上|播种地块|落点周围|【[^】]+】干员|友方|我方|其他干员|其他友方|其他角色)"
                          r"[^，,；;。]{0,25}"
                          r"(?:每秒(?:回复|恢复)|持续恢复|持续回复|获得每秒回复)(?!.{0,25}损伤).{0,30}(?:生命|最大生命)", clause)
            if not m:
                m = re.search(r"(?:使|令|让)[^，,；;。]{0,25}(?:周围|友方|我方|其他|所有|全体|全场|范围内)[^，,；;。]{0,20}每秒(?:回复|恢复)(?!.{0,25}损伤).{0,30}(?:生命|最大生命)", clause)
            if not m:
                m = re.search(r"每秒(?:回复|恢复)(?:为|向)?.{0,15}(?:周围|范围内|所有|全体|全场|友方|其他|附近|友军|目标)[^，,；;。]{0,25}(?!.{0,25}损伤).{0,30}(?:生命|最大生命)", clause)
            if not m:
                m = re.search(r"(?:使目标|使其|使受影响目标|使生效目标).{0,15}每秒(?:回复|恢复)(?!.{0,25}损伤).{0,30}(?:生命|最大生命)", clause)
            if m:
                matched_text = clause
                if re.search(r"^(?:自身|自己)每秒", matched_text.strip()):
                    continue
                if re.search(r"(?:自身|自己).{0,10}(?:防御力|攻击力|阻挡数).{0,30}每秒(?:回复|恢复)", matched_text):
                    continue
                if re.search(r"所有触手|流形为", matched_text):
                    continue
                return label, compact(phrase)
    return None


def true_aoe(sources: list[tuple[str, str]]) -> tuple[str, str] | None:
    area_target = (r"(?:所有(?:地面|空中)?(?:敌人|目标)|全部(?:地面|空中)?(?:敌人|目标)|"
                   r"(?:周围|附近)(?:的)?(?:所有|全部|其他)?(?:地面|空中)?(?:敌人|目标)|"
                   r"(?:该)?目标周围的(?:所有|全部)(?:地面|空中)?敌军)")
    for label, phrase in sources:
        # 扩散术师与炮手的普通攻击是命中点溅射，半径内敌人均会受伤。
        if label == "特性" and phrase in {"攻击造成群体法术伤害", "攻击造成群体物理伤害"}:
            branch = "扩散术师" if "法术" in phrase else "炮手"
            return f"{branch}分支", f"特性：{phrase}；PRTS 分支信息：普通攻击在命中位置造成溅射范围伤害"
        # PRTS 轰击术师分支明确写着「普通攻击同时攻击范围内的所有敌人」。
        if label == "特性" and phrase == "攻击造成超远距离的群体法术伤害":
            return label, "轰击术师：普通攻击同时攻击范围内的所有敌人"
        for clause in re.split(r"[；;。\n]", phrase):
            # 「阻挡的所有敌人」有限定条件，是假群攻；不能只看到「所有」就计入真群攻。
            if (re.search(r"(?:阻挡|被阻挡|攻击到|命中|锁定|冻结).{0,12}所有(?:地面|空中)?(?:敌人|目标)", clause)
                    or "随机攻击" in clause):
                continue
            area_damage = re.search(rf"{area_target}.{{0,25}}(?:造成|受到).{{0,40}}伤害", clause)
            if area_damage and re.search(
                    r"(?:造成|受到)的|伤害(?:提高|提升|增加|加深|减免|降低|\+)|"
                    r"受到.{0,30}攻击时|(?:自身|技能结束).{0,30}受到|"
                    r"共造成\d+次", area_damage.group()):
                area_damage = None  # 后文改述友方攻击或自身受伤，不是这些敌人受到群伤。
            # “对目标及其周围造成伤害”与“对目标周围造成溅射伤害”
            # 均是无人数上限的范围伤害；“周围最多3名敌人”不符合。
            splash_damage = re.search(
                r"对(?:该)?目标(?:及其|和其|与其)?周围(?:的(?:敌人|敌军))?"
                r"造成[^，,；;。]{0,40}伤害", clause)
            if (area_damage
                    or splash_damage
                    or re.search(rf"对.{{0,45}}{area_target}造成.{{0,70}}伤害", clause)
                    or re.search(rf"对.{{0,35}}{area_target}.{{0,15}}(?:进行(?:一次|多次)?攻击|发动.{{0,12}}斩击|使用.{{0,12}}切割|射击)", clause)
                    # 散射手的分支特性省略了谓语「攻击」，但特性确实攻击范围内全部敌人。
                    or (label == "特性" and clause.startswith("攻击范围内的所有敌人，"))):
                return label, compact(phrase)
    return None


def max_target(skill: dict) -> int:
    for key in ("max_target", "target_cnt", "target_num", "attack@max_target", "target@max_target", "skill@max_target"):
        value = skill["params"].get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for key, value in skill["params"].items():
        if key.endswith("max_target") or key.endswith("target_cnt"):
            if isinstance(value, (int, float)):
                return int(value)
    return 0


def capped_damage_targets(skill: dict, branch: str = "") -> int:
    """只取技能最高等级明确写出的、一次伤害动作的目标人数。"""
    count = max_target(skill)
    text = skill["text"]
    extra_total = 0
    # “额外攻击N名”是在原有攻击目标之外增加N名；伏击客普攻目标数不封顶。
    extra = re.search(r"额外攻击([一二两三四五六七1-7])(?:名|个)(?:飞行)?(?:敌人|目标)", text)
    target_add = re.search(r"攻击目标数\+([1-7])", text)
    if (extra or target_add) and branch != "stalker" and not re.search(r"攻击范围内的?所有敌人", text):
        if extra:
            extra_count = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}.get(extra.group(1))
            extra_count = extra_count or int(extra.group(1))
        else:
            extra_count = int(target_add.group(1))
        base = re.search(r"(?:同时攻击|攻击对)([2-7])(?:名|个)(?:敌人|目标)", text)
        extra_total = (int(base.group(1)) if base else 1) + extra_count
        if not 3 <= extra_total <= 7:
            extra_total = 0
    # 锁定后继续攻击被锁定目标算多目标；只锁定并施加状态不算攻击。
    locked_total = 0
    if "停止攻击" not in text:
        for val in range(3, 8):
            target = rf"(?:至多|最多)?{val}(?:名|个)(?:敌人|目标)"
            if re.search(rf"锁定[^，；。]{{0,25}}{target}[^，；。]{{0,35}}(?:攻击|造成[^，；。]{{0,12}}伤害)", text):
                locked_total = val
                break
    if 3 <= count <= 7:
        target = rf"(?:最多|至多)?{count}(?:名|个)(?:地面|空中|重量最重)?(?:不同的)?(?:敌人|敌方|目标|敌方单位)"
        for clause in re.split(r"[；;。\n]", text):
            if (re.search(rf"对.{{0,50}}{target}.{{0,40}}(?:造成|伤害|发射|斩击|攻击)", clause)
                    or re.search(rf"同时攻击.{{0,20}}{target}", clause)
                    or re.search(rf"向.{{0,25}}{target}.{{0,20}}发射", clause)
                    or re.search(rf"攻击.{{0,20}}{target}", clause)):
                return max(count, extra_total, locked_total)
    for m in re.finditer(r"(?:同时攻击|可同时攻击|攻击对|立即对|每次攻击对|攻击至多|额外攻击|向|随机对|且攻击).{0,25}(?:至多|最多)?([3-7])(?:名|个)(?:地面|空中|重量最重)?(?:不同的)?(?:敌人|敌方|目标|敌方单位)", text):
        val = int(m.group(1))
        if (re.search(rf"(?:对|同时攻击|向|且攻击).{{0,30}}(?:至多|最多)?{val}.{{0,40}}(?:造成|伤害|发射|攻击|斩击|物理|法术|真实)", text)
                or re.search(rf"(?:同时攻击|且攻击).{{0,15}}(?:至多|最多)?{val}", text)):
            return max(val, extra_total, locked_total)
    # 原文存在“每次对最多N名”“以二连击攻击最多N名”等等价写法；
    # 仅施加状态及从多个初始目标分别链接的数量不作为一次伤害上限。
    for val in range(3, 8):
        target = rf"(?:至多|最多)?{val}(?:名|个)(?:地面|空中)?(?:敌人|目标)"
        direct = (
            rf"(?:每次对|对[^，；。]{{0,22}}){target}[^，；。]{{0,24}}造成",
            rf"以[^，；。]{{0,12}}攻击{target}",
            rf"每次攻击(?![^，；。]{{0,15}}(?:少于|多于|不足|超过))[^，；。]{{0,12}}{target}",
            rf"对前方{target}进行一次远程攻击",
            rf"攻击[^；。]{{0,35}}最多在{val}个目标间跳跃",
            rf"(?:可以|且)攻击{val}个敌人",
            rf"将[^，；。]{{0,30}}{target}[^，；。]{{0,25}}[，,]对其造成",
            rf"束缚[^，；。]{{0,15}}{target}[^。]{{0,32}}每秒对被束缚的敌人造成",
        )
        if any(re.search(pattern, text) for pattern in direct):
            return max(val, extra_total, locked_total)
    return max(extra_total, locked_total)


def explicit_skill_fact(skills: list[dict], pattern: str) -> tuple[str, str] | None:
    """只从最高技能等级的明文描述取正向事实。"""
    for skill in skills:
        if re.search(pattern, skill["text"]):
            return skill["name"], skill["text"]
    return None


def direct_dp_skill(skills: list[dict]) -> tuple[str, str] | None:
    """逐渐/持续回费的总额不能充当即时获得费用的证据。"""
    pattern = r"(?:获得|回复)\d+点(?:部署)?费用"
    for skill in skills:
        for match in re.finditer(pattern, skill["text"]):
            clause = re.split(r"[，,；;。]", skill["text"][:match.start()])[-1]
            if re.search(r"逐渐|每秒|持续时间内|技能持续期间|一段时间内|每次攻击", clause):
                continue
            return skill["name"], skill["text"]
    return None


def all_allies_life_heal(text: str) -> bool:
    """将全员生命治疗与全员元素损伤回复、减伤分开。"""
    for clause in re.split(r"[；;。\n]", text):
        targets = re.finditer(r"(?:范围内|周围|附近)[^，,；;。]{0,15}所有(?:友[方军]|我方)", clause)
        for target in targets:
            before = clause[max(0, target.start() - 45):target.start()]
            after = clause[target.end():target.end() + 90]
            if (re.search(r"(?:治疗|回复|恢复)[^，,；;。]{0,45}$", before)
                    and re.search(r"生命(?:值)?", after)):
                return True
            if re.search(r"(?:治疗|回复|恢复)[^；;。]{0,55}生命(?:值)?", after):
                return True
            if re.search(r"进行一次[^，,；;。]{0,35}治疗", after):
                return True
    return False


def trap_skill_evidence(profile: dict) -> str | None:
    """陷阱师可在技能中用天赋所列专名指代陷阱。"""
    direct = explicit_skill_fact(
        profile["skills"], r"(?:获得|放置|部署)(?:一个|一枚|多个|\d+个)?.{0,8}陷阱")
    if direct:
        return f"技能「{direct[0]}」（最高等级）：{compact(direct[1])}"
    if profile["branch"] != "traper" or "陷阱" not in profile["trait"]:
        return None
    for talent_name, talent_text in profile["talents"]:
        trap = re.search(r"可以使用\d+(?:个|枚)([^（(，,；;。]{1,24})", talent_text)
        if not trap:
            continue
        trap_name = trap.group(1)
        for skill in profile["skills"]:
            gain = re.search(r"(?:获得|放置|部署)[^，,；;。]{0,16}"
                             + re.escape(trap_name), skill["text"])
            if gain:
                return (f"特性：{compact(profile['trait'], 40)}；"
                        f"天赋「{talent_name}」：{trap.group()}；"
                        f"技能「{skill['name']}」（最高等级）：{gain.group()}")
    return None


def self_max_hp_ratio_heal_skill(skills: list[dict]) -> tuple[str, str, str] | None:
    """识别按自身生命上限回血，排除治疗目标、召唤物及普通回满。"""
    max_hp = r"(?:最大生命(?:值)?|生命上限)"
    explicit_ratio = re.compile(
        rf"(?:回复|恢复)(?:自身)?(?:{max_hp}的?\d+%|\d+%的?{max_hp})")
    explicit_self_ratio = re.compile(r"(?:回复|恢复)自身(\d+)%的?生命(?:值)?")
    healing = re.compile(r"(?:回复|恢复).{0,16}(?:生命|\d+%)")
    other_actor = re.compile(r"流形|复制体|眠兽|狼群|仆役|触手|召唤物|装置|无人机|炮台")
    for skill in skills:
        text = skill["text"]
        structured_ratios = [value for key, value in skill["params"].items()
                             if key.endswith("hp_recovery_per_sec_by_max_hp_ratio")
                             and isinstance(value, (int, float)) and value > 0]
        max_hp_match = explicit_ratio.search(text)
        self_ratio_match = explicit_self_ratio.search(text)
        self_ratio_value = next((value for key, value in skill["params"].items()
                                 if (key == "hp_ratio" or key.endswith("@hp_ratio"))
                                 and isinstance(value, (int, float)) and value > 0
                                 and self_ratio_match
                                 and math.isclose(value * 100, int(self_ratio_match.group(1)))), None)
        if not max_hp_match and not structured_ratios and self_ratio_value is None:
            continue
        match = max_hp_match or self_ratio_match or healing.search(text)
        if not match:
            continue
        # 省略主语的“期间每秒回复”承接前一分句；流形和眠兽等不能算本体。
        before = re.split(r"[，,；;。]", text[:match.start()])
        if other_actor.search("，".join(before[-2:])):
            continue
        if structured_ratios:
            note = f"按生命上限计算，每秒回复自身{structured_ratios[0] * 100:g}%的生命值"
        elif self_ratio_value is not None:
            note = f"按生命上限计算，回复自身{self_ratio_value * 100:g}%的生命值"
        else:
            note = ""
        return skill["name"], text, note
    return None


def self_block_change_skill(skills: list[dict]) -> dict | None:
    """阻挡数变化必须作用于本体；友方或部署物的变化不能充当自身线索。"""
    change = re.compile(r"阻挡数.{0,5}(?:\+|-|增加|减少|变为)")
    other_recipient = re.compile(
        r"装置|援军|木偶舞者|樱桃三号|流形|眠兽|狼群|"
        r"(?:友方|我方)(?:单位|干员)|前方干员")
    for skill in skills:
        for match in change.finditer(skill["text"]):
            before = re.split(r"[，,；;。]", skill["text"][:match.start()])
            context = "，".join(before[-2:])
            fallback_to_self = re.search(r"该效果由自身获得", skill["text"][match.end():match.end() + 80])
            if other_recipient.search(context) and not fallback_to_self:
                continue
            return skill
    return None


def own_attack_range_expansion(skills: list[dict]) -> tuple[str, str] | None:
    """只认本体攻击范围的明确变化，不把范围内目标或装置当成主体。"""
    expansion = re.compile(
        r"攻击(?:范围|距离)(?:(?:更|更加|大幅)?(?:扩大|增大|增加|加长|延伸)|"
        r"(?:向|朝)[^，；。]{1,8}(?:扩大|延伸)|"
        r"与[^，；。]{1,8}范围(?:扩大|增加|延伸)|"
        r"[+＋]\s*(?:\{[a-zA-Z0-9_\.@]+\}|\d+)(?:格)?)|"
        r"(?:扩大|增大|增加|延伸)(?:自身|自己的)?攻击(?:范围|距离)"
    )
    other_actor = re.compile(r"装置|召唤物|无人机|炮台|浮游单元|陷阱|"
                             r"木偶舞者|矿石|沙地兽|棋子|心烛|重构体|替身|分身")
    for skill in skills:
        for match in expansion.finditer(skill["text"]):
            clause_before = re.split(r"[，；。]", skill["text"][:match.start()])[-1]
            if not other_actor.search(clause_before):
                return skill["name"], skill["text"]
    return None


RANGE_OUTSIDE_TEXT = re.compile(
    r"(?:范围外|原本范围以外|攻击范围改为.*无限|"
    r"攻击(?:范围|距离)(?:(?:更|更加|大幅)?(?:扩大|增大|增加|加长|延伸)|"
    r"(?:向|朝)[^，；。]{1,8}(?:扩大|延伸)|"
    r"与[^，；。]{1,8}范围(?:扩大|增加|延伸)|"
    r"[+＋]\s*(?:\{[a-zA-Z0-9_\.@]+\}|\d+)(?:格)?)|"
    r"(?:扩大|增大|增加|延伸)(?:自身|自己的)?攻击(?:范围|距离))"
)


def range_extra_cells(base_id: str | None, skill_id: str | None) -> set[tuple[int, int]]:
    """比较真实格子集合；不同 RangeId 不一定意味着攻击范围扩大。"""
    if not base_id or not skill_id or base_id not in RANGE_GRIDS or skill_id not in RANGE_GRIDS:
        return set()
    return RANGE_GRIDS[skill_id] - RANGE_GRIDS[base_id]


def outside_attack_status(profile: dict, skill: dict) -> bool | None:
    """True 为能打原范围外；None 为范围扩大但短描述不能确认攻击对象。"""
    text = skill["text"]
    if not range_extra_cells(profile["base_range_id"], skill["range_id"]) and not RANGE_OUTSIDE_TEXT.search(text):
        return False
    # RangeId 也用于治疗、支援和装置范围，必须另有对敌攻击证据。
    enemy_hit = bool(re.search(
        r"对[^，；。]{0,40}(?:敌人|敌方|敌军|目标)[^，；。]{0,45}"
        r"(?:造成[^，；。]{0,35}伤害|进行[^，；。]{0,12}攻击|发动[^，；。]{0,12}斩击)|"
        r"对(?:前方|周围|附近)[^，；。]{0,20}(?:造成[^，；。]{0,35}伤害|进行[^，；。]{0,12}攻击)|"
        r"对其发动[^，；。]{0,20}(?:攻击|斩击)|攻击造成[^，；。]{0,50}伤害",
        text))
    if enemy_hit:
        return True
    # 只攻击已阻挡敌人不因技能的状态作用范围扩大而获得范围外选敌。
    if re.search(r"攻击(?:自身)?阻挡的所有敌人", text):
        return False
    if (profile["branch"] in HEALING_ATTACK_BRANCHES
            or re.search(r"(?:下次|下一次)攻击.{0,20}(?:恢复|回复|治疗|友方)|"
                         r"(?:停止攻击|专心).{0,40}(?:治疗|恢复)|"
                         r"(?:所有|周围|附近).{0,20}(?:友方|我方|机械水獭).{0,35}(?:获得|治疗|恢复)", text)):
        return False
    # 本体停攻时，驭械术师的浮游单元仍可在明示扩大的范围内索敌。
    if "停止攻击" in text:
        if re.search(r"释放浮游单元锁定敌人攻击", text) and RANGE_OUTSIDE_TEXT.search(text):
            return True
        return False
    if own_attack_range_expansion([skill]):
        return True
    return None


def attack_self_heal_skill(skills: list[dict]) -> tuple[str, str] | None:
    """只认攻击动作触发的本体回血，不把攻击范围或自身周围当成主语。"""
    attack_trigger = re.compile(r"(?:每次|下次)攻击(?!范围|距离|力)|"
                                r"攻击(?=时|后|命中|回复|恢复|治疗)|"
                                r"命中(?:敌人|目标)(?:时|后)")
    own_heal = re.compile(r"(?:回复|恢复|治疗)(?:自身|自己)(?!周围|附近|攻击范围).{0,28}生命|"
                          r"(?:回复|恢复|治疗)(?!.{0,28}(?:友方|我方|友军|其他|周围|附近)).{0,28}生命")
    for skill in skills:
        for sentence in re.split(r"[；;。]", skill["text"]):
            for trigger in attack_trigger.finditer(sentence):
                heal = own_heal.search(sentence, trigger.end(), trigger.end() + 90)
                if heal and not re.search(r"技能结束|敌人倒下|被击倒|撤退", sentence[trigger.end():heal.start()]):
                    return skill["name"], skill["text"]
    return None


def self_hp_loss_skill(skills: list[dict]) -> tuple[str, str] | None:
    """只把干员本体的生命流失算作“自身流失生命”。"""
    loss = re.compile(r"流失.{0,22}生命|生命.{0,22}流失")
    other_subject = re.compile(r"装置|召唤物|Mon3tr|无人机|炮台|陷阱|友方|我方|"
                               r"(?:使|令|让)(?:目标|敌人|敌方)|心烛|屏障|护盾")
    for skill in skills:
        for sentence in re.split(r"[；;。]", skill["text"]):
            for match in loss.finditer(sentence):
                before = sentence[:match.start()]
                clause = before.rsplit("，", 1)[-1].rsplit(",", 1)[-1]
                # “装置回复自身生命，激活后流失”里的“自身”指装置；
                # 只接受与失血动作同一分句中的本体代词。
                if re.search(r"(?:自身|自己).{0,12}$", clause):
                    if not other_subject.search(clause):
                        return skill["name"], skill["text"]
                    continue
                if re.search(r"自身(?:和|与).{0,50}(?:友方|我方).{0,35}获得以下状态", before):
                    return skill["name"], skill["text"]
                if not other_subject.search(before):
                    return skill["name"], skill["text"]
    return None


def self_shield_source(sources: list[tuple[str, str]]) -> tuple[str, str] | None:
    """屏障须实际施加给本体，不能只以本体属性计量或施加给援军。"""
    patterns = (
        r"(?:自身|自己)(?:与|和).{0,35}获得.{0,45}(?:护盾|屏障)",
        r"(?:自身|自己)(?:立即)?获得.{0,35}(?:护盾|屏障)",
        r"超出自身生命上限的生命值可转化为屏障",
        r"拥有来源于自身的屏障",
        r"(?:^|[，；])(?:部署后)?(?:立即)?获得.{0,55}(?:护盾|屏障)",
        r"清除自身的元素损伤并获得.{0,20}屏障",
    )
    for source, phrase in sources:
        if any(re.search(pattern, phrase) for pattern in patterns):
            return source, phrase
    return None


def self_regen_source(sources: list[tuple[str, str]]) -> tuple[str, str] | None:
    """只认本体的周期性生命回复；元素损伤回复和生命流失不算。"""
    for source, phrase in sources:
        for sentence in re.split(r"[；;。]", phrase):
            clauses = re.split(r"[，,]", sentence)
            for index, clause in enumerate(clauses):
                if not (re.search(r"每\d*(?:\.\d+)?秒", clause)
                        and re.search(r"(?:回复|恢复|治疗).{0,28}生命", clause)):
                    continue
                context = "，".join(clauses[:index + 1])
                direct_self = re.search(r"(?:自身|自己).{0,8}每\d*(?:\.\d+)?秒.{0,8}(?:回复|恢复)", clause)
                if (not direct_self and re.search(r"其他干员|友方|我方|友军|目标干员|"
                                                  r"装置|援军|流形|复制体", context)):
                    continue
                if direct_self or re.search(r"(?:自身|自己)", context):
                    return source, phrase
    return None


def enemy_dot_source(sources: list[tuple[str, str]]) -> tuple[str, str] | None:
    """只认敌人按时间反复受伤；持续动作、屏障衰减和限时单次伤害不算。"""
    periodic_damage = re.compile(
        r"每(?:隔)?\d*(?:\.\d+)?秒[^，,；;。]{0,55}?"
        r"(?P<verb>造成|受到)[^，,；;。]{0,55}伤害"
        r"(?!降低|减少|减免|提升|增加|提高|加成)")
    sustained_damage = re.compile(
        r"持续(?P<verb>受到)[^，,；;。]{0,30}伤害"
        r"(?!降低|减少|减免|提升|增加|提高|加成)")
    enemy = re.compile(r"敌人|敌方|目标")
    other_recipient = re.compile(r"自身|自己|友方|我方|友军|装置|召唤物|屏障|护盾")
    for source, phrase in sources:
        for sentence in re.split(r"[；;。]", phrase):
            clauses = re.split(r"[，,]", sentence)
            for index, clause in enumerate(clauses):
                match = periodic_damage.search(clause) or sustained_damage.search(clause)
                if not match:
                    continue
                preceding = clause[:match.start()]
                if match.group("verb") == "受到":
                    # “友方每秒受到敌人造成的伤害”中的敌人是施害者。
                    last_enemy = max((m.start() for m in enemy.finditer(preceding)), default=-1)
                    last_other = max((m.start() for m in other_recipient.finditer(preceding)), default=-1)
                    if last_other > last_enemy:
                        continue
                    if last_enemy >= 0:
                        return source, phrase
                elif enemy.search(clause):
                    return source, phrase
                # “攻击使目标中毒，每秒受到伤害”省略了后一分句的主语。
                if index and enemy.search(clauses[index - 1]) and not other_recipient.search(clause):
                    return source, phrase
    return None


def counterattack_skill(skills: list[dict]) -> tuple[str, str] | None:
    """受击或闪避后由本体立即反击；友方受击触发的援护不算。"""
    damage = re.compile(
        r"(?:对目标|对[^，,；;。]{0,20}敌人|选择[^，,；;。]{0,20}敌人)"
        r"[^；;。]{0,45}造成[^，,；;。]{0,40}伤害")
    for skill in skills:
        for sentence in re.split(r"[；;。]", skill["text"]):
            for hit in re.finditer(r"(?:每次|下一次|下次)?受到攻击时", sentence):
                before = sentence[max(0, hit.start() - 15):hit.start()]
                if re.search(r"(?:该角色|友方|我方|目标干员|装置|召唤物)[^，,]{0,8}$", before):
                    continue
                if damage.search(sentence[hit.end():]):
                    return skill["name"], skill["text"]
            if re.search(r"闪避成功后[^；;。]{0,55}反击[，,]?造成[^，,；;。]{0,40}伤害", sentence):
                return skill["name"], skill["text"]
    return None


HIT_COUNT_WORDS = {"二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
HIT_COUNT_LABELS = {2: "两", 3: "三", 4: "四", 5: "五",
                    6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def skill_hit_counts(phrase: str) -> set[int]:
    """只收技能明写的一次攻击连击／连射次数，不把击中目标的累计次数算进去。"""
    result = set()
    for match in re.finditer(r"(10|[2-9]|[二两三四五六七八九十])连(?:击|射|发)", phrase):
        before = phrase[max(0, match.start() - 45):match.start()]
        if re.search(r"(?:攻击|射击|斩击|发动|释放|使用|交替|改为|变为|以)[^；。]{0,40}$", before):
            result.add(HIT_COUNT_WORDS.get(match.group(1), int(match.group(1))
                                       if match.group(1).isdigit() else 0))
    for match in re.finditer(r"连续(?:攻击|射击)(10|[2-9]|[二两三四五六七八九十])次", phrase):
        result.add(HIT_COUNT_WORDS.get(match.group(1), int(match.group(1))
                                   if match.group(1).isdigit() else 0))
    for match in re.finditer(
            r"(?:发动|进行)(10|[2-9]|[二两三四五六七八九十])次"
            r"(?:连续)?[^，；。]{0,32}?(?:斩击|攻击(?!力))", phrase):
        result.add(HIT_COUNT_WORDS.get(match.group(1), int(match.group(1))
                                    if match.group(1).isdigit() else 0))
    return result & HIT_COUNT_LABELS.keys()


def possible_support(profile: dict, kind: str) -> bool:
    """宽松候选集只用于唯一性筛选；真正发线索仍要通过严格事实与证据。"""
    recipient_hint = re.compile(r"友方|友军|我方|其他.{0,20}干员|所有.{0,25}干员|"
                                r"全体.{0,25}干员|范围内.{0,25}干员|【[^】]+】干员|"
                                r"干员(?:的)?(?:攻击力|攻击速度|攻速|防御力)")
    hints = {
        "attack": r"攻击力|伤害(?:提升|提高|增加)|鼓舞|术法充盈|无视.{0,12}(?:防御力|法术抗性)",
        "speed": r"攻击速度|攻速",
        "penetration": r"无视.{0,12}(?:防御力|法术抗性)",
        "ammo": r"弹药上限|补弹",
        "survival": r"防御|法术抗性|闪避|屏障|护盾|庇护|迷彩|隐匿|生命上限|最大生命值|抵抗|免疫|伤害减免|伤害抵挡|伤害-",
        "sp": r"技力",
    }
    for module in profile["modules"]:
        for skill in [None, *profile["skills"]]:
            for _, phrase in sources_for(profile, module, skill):
                if recipient_hint.search(phrase) and re.search(hints[kind], phrase):
                    return True
    return False


def facts_for(profile: dict, branch_rarities: dict[str, set[int]]) -> list[tuple[str, str, str, str, str]]:
    """(id, family, topic, clue, evidence); each fact is true for this operator."""
    output = []
    def add(key: str, family: str, topic: str, sentence: str, evidence: str):
        if key in REVIEWED_EXCLUSIONS.get(profile["id"], ()):
            return
        output.append((key, family, topic, sentence, evidence))

    configs = []
    for module in profile["modules"]:
        for skill in [None, *profile["skills"]]:
            sources = sources_for(profile, module, skill)
            configs.append({"module": module, "skill": skill, "sources": sources,
                            "damage": damage_types(profile, sources), "control": control_types(sources)})
    all_damage = set().union(*(x["damage"] for x in configs))
    all_control = set().union(*(x["control"] for x in configs))
    all_sources = [(label, phrase) for x in configs for label, phrase in x["sources"]]
    # 普通脆弱与物理、法术、元素专属脆弱分开；天赋和模组也可施加这些效果。
    generic_fragile = next(((label, phrase) for label, phrase in all_sources
                            if re.search(r"(?<!物理)(?<!法术)(?<!元素)脆弱|(?:敌人|敌方|敌军|目标).{0,20}受到的伤害(?:增加|提高|提升|\+)", phrase)), None)
    if generic_fragile:
        add("debuff:fragile", "削弱", "debuff_fragile",
            "能使敌人获得普通脆弱（物理、法术、真实伤害增加）",
            f"{generic_fragile[0]}：{compact(generic_fragile[1])}")
    for kind, label in (("physical", "物理"), ("arts", "法术"), ("elemental", "元素")):
        specific = next(((source, phrase) for source, phrase in all_sources
                         if re.search(rf"{label}脆弱|受到的{label}伤害(?:增加|提高|提升|\+)", phrase)), None)
        evidence = specific or (generic_fragile if kind != "elemental" else None)
        if evidence:
            add(f"debuff:{kind}_fragile", "削弱", "debuff_fragile_kind",
                f"可使敌人受到的{label}伤害增加",
                f"{evidence[0]}：{compact(evidence[1])}")
    audited = AUDITED.get(profile["id"], {})
    no_air_branch_exceptions = NO_AIR_REVIEWED_BRANCHES.get(profile["branch"])
    has_summons = profile["has_summons"]
    summon_damage_control_complete = not has_summons or audited.get("summon_no_damage_control", False)

    trait = profile["trait"]
    if profile["branch"] in NORMAL_AIR_BRANCHES:
        add("air:normal_attack", "目标", "air", "普通攻击可以对空",
            f"PRTS 分支特性信息：{BRANCH_NAMES[profile['branch']]}攻击时可对空")
    if re.search(r"优先攻击空中单位|优先攻击飞行单位", trait):
        add("air:normal_attack", "目标", "air", "普通攻击可以对空", f"特性：{compact(trait)}")
        add("target:normal_air_priority", "目标", "normal_target_priority",
            "职业特性使普攻优先攻击空中单位", f"特性：{compact(trait)}")
    # PRTS 分支信息：炮手、扩散术师的普通攻击是以命中位置为中心的范围溅射。
    # “群体伤害”也用于收割者等不同机制；阵法术师的描述还限定了技能开启时。
    # 因此不能只按这四个字生成泛化的普攻群伤事实。
    if profile["branch"] == "splashcaster" and trait == "攻击造成群体法术伤害":
        add("attack:normal_splash_arts", "攻击", "normal_attack_form",
            "普通攻击命中时会在目标位置造成法术溅射伤害",
            f"扩散术师分支；特性：{compact(trait)}；PRTS 分支信息：攻击为范围伤害")
    if profile["branch"] == "aoesniper" and trait == "攻击造成群体物理伤害":
        add("air:normal_attack", "目标", "air", "普通攻击可以对空",
            f"炮手分支；特性：{compact(trait)}；PRTS 分支信息：普通攻击可对空")
        add("attack:normal_splash_physical_air", "攻击", "normal_attack_form",
            "普通攻击可对空，命中时会在目标位置造成物理溅射伤害",
            f"炮手分支；特性：{compact(trait)}；PRTS 分支信息：可对空，攻击为范围伤害")
    if re.search(r"(?:治疗|恢复).{0,20}(?:友方单位间跳跃|友方目标间跳跃)|(?:会在|在)\d+个友方单位间跳跃", trait):
        add("heal:chain_trait", "恢复", "heal_form", "普通治疗会在多个友方目标间跳跃",
            f"特性：{compact(trait)}")
    if re.search(r"可以进行远程攻击.{0,20}攻击力降低", trait):
        add("attack:melee_ranged_trait", "攻击", "normal_attack_form",
            "身处近战位但特性允许进行有伤害衰减的远程攻击", f"特性：{compact(trait)}")
    if "击杀敌人后获得1点部署费用" in trait:
        add("deploy:kill_dp", "部署", "dp_source", "击杀敌人后可以获得部署费用",
            f"特性：{compact(trait)}")
    if "撤退时返还初始部署费用" in trait:
        add("deploy:retreat_refund", "部署", "dp_refund", "撤退时返还初始部署费用",
            f"特性：{compact(trait)}")
    if re.match(r"^(?:通常时|通常)?不(?:进行普通)?攻击", trait):
        add("attack:normal_none", "攻击", "normal_attack_form", "通常不进行普通攻击",
            f"特性：{compact(trait)}")
    if "不受部署数量限制" in trait:
        add("deploy:no_slot", "部署", "deployment_rule", "部署时不受部署数量限制",
            f"特性：{compact(trait)}")
    if "再部署时间极长" in trait:
        add("deploy:very_long_redeploy", "部署", "redeploy_rule", "特性包含再部署时间极长",
            f"特性：{compact(trait)}")
    base_block = re.search(r"能够阻挡(一|二|两|三|四|五|六|[1-6])个敌人", trait)
    if base_block:
        block_number = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6}.get(base_block.group(1))
        block_number = block_number or int(base_block.group(1))
        add(f"block:base:{block_number}", "阻挡", "base_block", f"部署于近战位，且不开技能时通常阻挡{block_number}名敌人",
            f"特性：{compact(trait)}")
    elif (profile["position"] == "近战位" and profile["branch"] not in {"librator", "skywalker"}
          and isinstance(profile["base_block"], (int, float))
          and 1 <= profile["base_block"] <= 6
          and not re.search(r"(?:通常|常态|技能未开启时).{0,20}阻挡数(?:为|变为)0", trait)):
        # 高台干员的属性表也可能写阻挡数1，但其部署位置不能阻挡地面敌人；
        # 解放者常态阻挡0，驭空客起飞后阻挡的是飞行敌人，均不能套用普通阻挡线索。
        block_number = int(profile["base_block"])
        add(f"block:base:{block_number}", "阻挡", "base_block", f"部署于近战位，且不开技能时通常阻挡{block_number}名敌人",
            f"干员档案·最高精英阶段属性：基础阻挡数 {block_number}")
    trait_zero = re.search(r"技能发动期间阻挡数变为0|技能期间阻挡数变为0", trait)
    skill_zero = explicit_skill_fact(profile["skills"], r"阻挡数变为0")
    if trait_zero or skill_zero:
        evidence = (f"特性：{compact(trait)}" if trait_zero
                    else f"技能「{skill_zero[0]}」（最高等级）：{compact(skill_zero[1])}")
        add("block:zero_while_skill", "阻挡", "skill_block", "技能期间自身阻挡数变为零", evidence)
    if not profile["skills"]:
        add("skill:no_active_slot", "技能", "skill_count", "没有可携带的技能",
            "干员档案的技能列表为空")
    for kind in ("物理", "法术"):
        other_kind = "法术" if kind == "物理" else "物理"
        pattern = (rf"(?:获得|拥有|具有).{{0,16}}"
                   rf"(?:{kind}(?:[与和及/]{other_kind})?|{other_kind}[与和及/]{kind})闪避|"
                   rf"{kind}闪避\+")
        found = next(((name, phrase) for name, phrase in profile["talents"]
                      if re.search(pattern, phrase)), None)
        if found:
            add(f"talent:dodge:{kind}", "生存", "dodge_type",
                f"天赋提供{kind}闪避", f"天赋「{found[0]}」：{compact(found[1])}")
    for key, pattern, sentence in (
        ("talent:on_deploy_global_heal", r"部署后(?:立即|立刻)(?:恢复|治疗).{0,18}(?:全场友方|全体友方)(?:单位|干员)",
         "部署后能立即治疗全场友方单位"),
        ("talent:redeploy_faster", r"再部署时间-\d+秒|再部署时间(?:减少|缩短)\d+秒",
         "天赋可以缩短自身再部署时间"),
        ("talent:anti_air_bonus", r"攻击(?:飞行|空中)(?:目标|敌人|单位)时.{0,18}攻击力(?:\+|提升|提高)",
         "天赋使攻击飞行敌人时的攻击力提高"),
        ("talent:first_block_dp", r"首次阻挡敌人时.{0,15}获得\d+点部署费用",
         "首次阻挡敌人时可以获得部署费用"),
        ("talent:extra_heal_target", r"(?:额外|同时)治疗一名(?:其他)?友方(?:单位|干员)",
         "天赋可以额外治疗一名友方单位"),
        ("talent:low_hp_heal", r"治疗时.{0,16}目标生命(?:值)?(?:少于|低于|不足)\d+%.{0,24}(?:治疗|恢复|回复)",
         "天赋会在友方目标生命值较低时额外治疗"),
        ("talent:isolated_buff", r"周围.{0,18}没有其他友方(?:单位|干员).{0,35}(?:攻击力|防御力)",
         "附近没有其他友方时，天赋会增强自身属性"),
        ("talent:block_two_defense", r"阻挡住?(?:两个|两名|2个|2名)(?:及以上|或以上|以上)?的?敌人时.{0,25}防御力",
         "阻挡至少两名敌人时，天赋会提高自身防御力"),
        ("talent:self_sp_recovery", r"(?!.*(?:所有|友方|我方|其他|辅助|术师))(?:自身.{0,25})?技力自然回复速度\+\d+(?:\.\d+)?/秒",
         "天赋提高自身的技力自然回复速度"),
        ("talent:self_resistance", r"(?:自身)?法术抗性\+\d+|"
         r"(?:自身|友方|我方).{0,12}(?:获得|提高|提升)(?:最高)?\+\d+(?:点)?法术抗性",
         "天赋可提高自身或友方干员的法术抗性"),
        ("talent:faction_attack_speed", r"(?:(?:所有|全部).{0,22}|【[^】]+】)(?:干员|成员).{0,20}攻击速度\+\d+",
         "天赋可以提高其他干员的攻击速度"),
        ("talent:own_deploy_cost_down", r"自身部署费用-\d+",
         "天赋降低自身部署费用"),
    ):
        found = next(((name, phrase) for name, phrase in profile["talents"] if re.search(pattern, phrase)), None)
        if found:
            # 同一效果也会被通用支援或治疗规则识别；共用主题，避免重复提示。
            topic = {"talent:faction_attack_speed": "ally_output",
                     "talent:extra_heal_target": "heal_targets"}.get(key, key)
            add(key, "天赋", topic, sentence, f"天赋「{found[0]}」：{compact(found[1])}")

    # 技能触发与技力方式直接来自最高等级的结构化字段，不从描述猜测。
    activation_names = {"MANUAL": "手动触发", "AUTO": "自动触发", "PASSIVE": "被动"}
    sp_names = {"INCREASE_WITH_TIME": "自动回复技力", "INCREASE_WHEN_ATTACK": "攻击回复技力",
                "INCREASE_WHEN_TAKEN_DAMAGE": "受击回复技力"}
    for code, label in activation_names.items():
        found = next((s for s in profile["skills"] if s["activation"] == code), None)
        if found:
            sentence = "拥有被动技能" if code == "PASSIVE" else f"拥有{label}的技能"
            add(f"skill:activation:{code.lower()}", "技能", "skill_activation",
                sentence, f"技能「{found['name']}」（最高等级）：触发方式为{label}")
    for code, label in sp_names.items():
        found = next((s for s in profile["skills"] if s["sp_type"] == code), None)
        if found:
            add(f"skill:sp:{code.lower()}", "技能", "skill_sp",
                f"拥有{label}的技能", f"技能「{found['name']}」（最高等级）：{label}")
    for activation, sp_type in (("MANUAL", "INCREASE_WHEN_ATTACK"),
                                ("AUTO", "INCREASE_WHEN_ATTACK"),
                                ("MANUAL", "INCREASE_WHEN_TAKEN_DAMAGE"),
                                ("AUTO", "INCREASE_WHEN_TAKEN_DAMAGE")):
        found = next((s for s in profile["skills"] if s["activation"] == activation and s["sp_type"] == sp_type), None)
        if found:
            add(f"skill:activation_sp:{activation.lower()}:{sp_type.lower()}", "技能", "skill_activation_sp",
                f"有{activation_names[activation]}、{sp_names[sp_type]}的技能",
                f"技能「{found['name']}」（最高等级）：{activation_names[activation]}；{sp_names[sp_type]}")
    sp_kinds = {s["sp_type"] for s in profile["skills"] if s["sp_type"] in sp_names}
    for left, right in (("INCREASE_WITH_TIME", "INCREASE_WHEN_ATTACK"),
                        ("INCREASE_WITH_TIME", "INCREASE_WHEN_TAKEN_DAMAGE"),
                        ("INCREASE_WHEN_ATTACK", "INCREASE_WHEN_TAKEN_DAMAGE")):
        if {left, right} <= sp_kinds:
            witnesses = [next(s["name"] for s in profile["skills"] if s["sp_type"] == code) for code in (left, right)]
            add(f"skill:two_sp:{left.lower()}:{right.lower()}", "技能", "skill_sp_variety",
                f"不同技能分别采用{sp_names[left]}和{sp_names[right]}",
                f"技能「{witnesses[0]}」：{sp_names[left]}；技能「{witnesses[1]}」：{sp_names[right]}")
    ready = next((s for s in profile["skills"] if s["activation"] == "MANUAL"
                  and isinstance(s["sp_cost"], (int, float)) and s["sp_cost"] > 0
                  and isinstance(s["initial_sp"], (int, float)) and s["initial_sp"] >= s["sp_cost"]), None)
    if ready:
        add("skill:ready_on_deploy", "技能", "skill_ready", "有手动技能在部署时就已蓄满技力",
            f"技能「{ready['name']}」（最高等级）：初始技力 {ready['initial_sp']}；消耗 {ready['sp_cost']}")
    zero_sp = next((s for s in profile["skills"] if s["activation"] != "PASSIVE" and s["initial_sp"] == 0), None)
    if zero_sp:
        add("skill:zero_initial_sp", "技能", "skill_initial_sp", "有消耗技力的技能初始技力为零",
            f"技能「{zero_sp['name']}」（最高等级）：初始技力 0")
    for seconds in (5, 8, 10, 12, 15, 18, 20, 25, 30, 35, 40, 45, 50, 60):
        found = next((s for s in profile["skills"] if s["duration_type"] != "AMMO"
                      and isinstance(s["duration"], (int, float)) and s["duration"] == seconds), None)
        if found:
            add(f"skill:duration:{seconds}", "数值", "skill_duration_exact",
                f"有技能在最高等级持续{seconds}秒",
                f"技能「{found['name']}」（最高等级）：持续时间 {seconds} 秒")
    for cost in (2, 3, 4, 5, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80):
        found = next((s for s in profile["skills"] if s["activation"] != "PASSIVE" and s["sp_cost"] == cost), None)
        if found:
            add(f"skill:sp_cost:{cost}", "数值", "skill_sp_cost_exact",
                f"有技能在最高等级需要{cost}点技力",
                f"技能「{found['name']}」（最高等级）：技力消耗 {cost}")

    for code in sorted(all_damage):
        if code == "physical":
            continue
        label = DAMAGE_NAMES[code]
        add(f"damage:can:{code}", "伤害", "damage", f"可以造成{label}伤害",
            next((f"{label2}：{compact(phrase)}" for label2, phrase in all_sources
                  if deals_typed_damage(phrase, label)
                  or (code == "elemental" and inflicts_elemental_loss(phrase))), "特性及攻击方式"))
    for kind in ("凋亡", "灼燃", "神经", "侵蚀", "狂躁"):
        found = next(((source, phrase) for source, phrase in all_sources
                      if inflicts_elemental_loss(phrase, kind)), None)
        if found:
            add(f"damage:loss:{kind}", "伤害", "elemental_loss_kind",
                f"可以对敌人施加{kind}损伤", f"{found[0]}：{compact(found[1])}")
    if len(all_damage) == 1 and summon_damage_control_complete:
        add("damage:only_one", "伤害", "damage", "仅能造成一种类型的伤害",
            "普通攻击、全部技能、天赋和专属模组均已盘点；只发现一种伤害类型")
    if len(all_damage) == 2 and summon_damage_control_complete:
        labels = "、".join(DAMAGE_NAMES[x] for x in sorted(all_damage))
        add("damage:exact_two", "伤害", "damage", "可造成的伤害类型有两种",
            f"全部合法配置的伤害类型：{labels}")
    if len(all_damage) == 1 and summon_damage_control_complete:
        code = next(iter(all_damage))
        add(f"damage:only:{code}", "伤害", "damage", f"只能造成{DAMAGE_NAMES[code]}伤害",
            f"普通攻击、技能、天赋和所有模组配置均已盘点：仅有{DAMAGE_NAMES[code]}伤害")
    # 移速数值削弱属于 debuff:move_speed，不增加或阻断异常状态/位移的控制计数。
    control_complete = summon_damage_control_complete and "elemental" not in all_damage
    if not all_control and control_complete:
        add("control:none", "控制", "control", "没有异常状态或位移控制",
            "普通攻击、全部技能、天赋和专属模组中未发现对敌方施加异常状态或位移；移速数值削弱另计")
    elif len(all_control) == 1 and control_complete:
        label = next(iter(all_control))
        add("control:one", "控制", "control", "具备一种类型的控制效果",
            f"全部合法配置仅发现：{CONTROL_NAMES[label][0]}")
    elif 2 <= len(all_control) <= 3 and control_complete:
        labels = "、".join(CONTROL_NAMES[code][0] for code in sorted(all_control))
        add(f"control:exact:{len(all_control)}", "控制", "control",
            f"具备{len(all_control)}种类型的控制效果", f"全部合法配置中包含：{labels}")
    elif len(all_control) == 4 and control_complete:
        labels = "、".join(CONTROL_NAMES[code][0] for code in sorted(all_control))
        add("control:exact:4", "控制", "control",
            "具备四种类型的控制效果", f"全部合法配置中包含：{labels}")
    for code in sorted(all_control):
        label = CONTROL_NAMES[code][0]
        add(f"control:can:{code}", "控制", "control", f"可对敌人施加{label}效果",
            next((f"{source}：{compact(phrase)}" for source, phrase in all_sources
                  if code in control_types([(source, phrase)])), "技能或天赋"))
    for skill in profile["skills"]:
        skill_damage = {code for code, label in DAMAGE_NAMES.items()
                        if deals_typed_damage(skill["text"], label)
                        or (code == "elemental" and inflicts_elemental_loss(skill["text"]))}
        inherited = audited.get("skill_inherited_damage", {}).get(skill["name"])
        if inherited:
            # 该技能仍按普通攻击类型造成伤害，短描述只列额外的控制效果。
            skill_damage.add(inherited)
        if deals_weakpoint_damage(skill["text"]):
            skill_damage.update(("physical", "arts"))
        skill_control = control_types([(f"技能「{skill['name']}」", skill["text"])])
        for left, right in combinations(sorted(skill_damage), 2):
            add(f"combo:skill_two_damage:{left}:{right}", "复合", "skill_two_damage",
                f"有技能既能造成{DAMAGE_NAMES[left]}伤害，也能造成{DAMAGE_NAMES[right]}伤害",
                f"同一技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
        for damage_code in sorted(skill_damage):
            for control_code in sorted(skill_control):
                add(f"combo:skill_damage_control:{damage_code}:{control_code}", "复合", "skill_damage_control",
                    f"有技能既能造成{DAMAGE_NAMES[damage_code]}伤害，也能施加{CONTROL_NAMES[control_code][0]}",
                    f"同一技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
        exclusive_groups = []
        for choice in re.finditer(r"随机施加以下任意一个状态[（(]([^）)]+)[）)]", skill["text"]):
            exclusive_groups.append({
                code for code, words in CONTROL_NAMES.items()
                if any(word in choice.group(1) for word in words)
            })
        for left, right in combinations(sorted(skill_control), 2):
            if any({left, right} <= group for group in exclusive_groups):
                continue
            add(f"combo:skill_two_controls:{left}:{right}", "复合", "skill_two_controls",
                f"同一技能可以施加{CONTROL_NAMES[left][0]}和{CONTROL_NAMES[right][0]}两种控制",
                f"同一技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
        if true_aoe([(f"技能「{skill['name']}」", skill["text"])]):
            for control_code in sorted(skill_control):
                add(f"combo:aoe_control:{control_code}", "复合", "aoe_control",
                    f"有技能兼具真群攻与{CONTROL_NAMES[control_code][0]}控制",
                    f"同一技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
    linked = audited.get("skill_talent_aoe_stun")
    if linked:
        linked_skill = next((s for s in profile["skills"] if s["name"] == linked[0]
                             and "琉璃璧破碎" in s["text"]), None)
        linked_talent = next((phrase for name, phrase in profile["talents"] if name == linked[1]
                              and true_aoe([("天赋", phrase)])
                              and "晕眩" in phrase), None)
        if linked_skill and linked_talent:
            add("combo:aoe_control:stun", "复合", "aoe_control",
                "有技能兼具真群攻与晕眩控制",
                f"技能「{linked_skill['name']}」：{compact(linked_skill['text'])}；"
                f"触发天赋「{linked[1]}」：{compact(linked_talent)}")
    if len(all_damage) == 1 and not all_control and control_complete:
        add("combo:one_damage_no_control", "复合", "damage_control_combo",
            "仅能造成一种类型的伤害，且没有异常状态或位移控制",
            f"所有技能及模组配置均只产生{DAMAGE_NAMES[next(iter(all_damage))]}伤害，无异常状态或位移控制")
    if len(all_damage) == 2 and len(all_control) == 1 and control_complete:
        damage_labels = "、".join(DAMAGE_NAMES[code] for code in sorted(all_damage))
        control_label = CONTROL_NAMES[next(iter(all_control))][0]
        add("combo:two_damage_one_control", "复合", "damage_control_combo",
            "可造成两种伤害类型与一种控制效果",
            f"普通攻击、全部技能、天赋及专属模组：{damage_labels}伤害；{control_label}控制")

    aoe = true_aoe(all_sources)
    if aoe or audited.get("true_aoe"):
        aoe_evidence = f"{aoe[0]}：{aoe[1]}" if aoe else audited["true_aoe"]
        add("attack:true_aoe", "攻击", "target_topology", "能造成真群攻",
            aoe_evidence)
    blocked_attack = next(((label, phrase) for label, phrase in all_sources
                           if re.search(r"(?<!Mon3tr)(?<!Mon3tr可以)(?<!召唤物)(?:同时)?攻击(?:阻挡的所有|所有阻挡的)敌人", phrase)), None)
    if blocked_attack:
        add("attack:all_blocked", "攻击", "target_topology", "可同时攻击自身阻挡的所有敌人",
            f"{blocked_attack[0]}：{compact(blocked_attack[1])}")
    allied_blocked = next(((label, phrase) for label, phrase in all_sources
                           if re.search(r"友方.{0,15}阻挡的所有敌人造成.{0,45}伤害", phrase)), None)
    if allied_blocked:
        add("attack:allied_blocked", "攻击", "target_topology", "有技能可伤害周围友方阻挡的所有敌人",
            f"{allied_blocked[0]}：{compact(allied_blocked[1])}")
    # 按各技能专三时的具体人数分别出线索；有限人数和范围全体是不同机制。
    for skill in profile["skills"]:
        count = capped_damage_targets(skill, profile["branch"])
        if count:
            add(f"attack:skill_targets:{count}", "攻击", "target_count",
                f"有技能可一次对最多{count}名敌人造成伤害",
                f"技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
    if audited.get("normal_air"):
        add("air:normal_attack", "目标", "air", "普通攻击可以对空", audited["normal_air"])
    if (audited.get("no_air") or profile["id"] in NO_AIR_REVIEWED_IDS
            or profile["id"] in NO_AIR_USER_CONFIRMED_IDS
            or (no_air_branch_exceptions is not None
                and profile["id"] not in no_air_branch_exceptions)):
        evidence = audited.get("no_air") or (
            "用户按全部能造成伤害的能力裁定无对空能力"
            if profile["id"] in NO_AIR_USER_CONFIRMED_IDS else
            f"逐人核对 {BRANCH_NAMES[profile['branch']]} 分支的技能、天赋、模组与召唤物；"
            "无可伤害飞行敌人的能力")
        add("air:solo_none", "目标", "air", "无对空攻击能力", evidence)
    if has_summons:
        add("summon:has", "召唤", "summon", "战斗能力中包含召唤物",
            "本地档案的召唤物索引非空；其效果按干员自身能力统计")
    grid_expanded = next((s for s in profile["skills"]
                          if range_extra_cells(profile["base_range_id"], s["range_id"])
                          and outside_attack_status(profile, s) is True), None)
    expanded = own_attack_range_expansion(profile["skills"])
    if grid_expanded:
        extra = range_extra_cells(profile["base_range_id"], grid_expanded["range_id"])
        add("range:expand", "范围", "range_expand", "有技能能扩大自身的攻击范围",
            f"技能「{grid_expanded['name']}」：攻击范围 {profile['base_range_id']} → "
            f"{grid_expanded['range_id']}，新增{len(extra)}格；{compact(grid_expanded['text'], 85)}")
    elif expanded:
        add("range:expand", "范围", "range_expand", "有技能能扩大自身的攻击范围",
            f"技能「{expanded[0]}」：{compact(expanded[1])}")
    block_change = self_block_change_skill(profile["skills"])
    if block_change:
        add("block:skill_change", "阻挡", "block_change", "有技能会改变自身的阻挡数",
            f"技能「{block_change['name']}」：{compact(block_change['text'])}")

    skill_mechanics = (
        ("ammo", "skill_resource", "技能", "拥有消耗弹药攻击的技能", r"(?:攻击装有|技能拥有|装有)\d+(?:枚|发)(?:弹药|子弹)"),
        ("early_stop", "skill_duration", "技能", "有技能可以主动提前结束",
         r"可(?:以)?随时(?:主动|手动)?(?:停止|结束)技能|可(?:以)?(?:随时)?(?:主动|手动)(?:停止|关闭|结束)(?:技能)?|手动停止(?:或[^，；。]+)?(?:后)?技能结束"),
        ("permanent", "skill_duration", "技能", "有技能启动后持续时间无限", r"持续时间无限"),
        ("next_attack", "skill_trigger", "技能", "有技能强化下一次攻击",
         r"(?:下次|下一次)(?:的)?攻击(?:.{0,55}(?:攻击力|伤害|连击|攻击两次|攻击三次)|力(?:提升|提高|变为|增加))"),
        ("overload", "skill_overload", "技能", "有技能具有过载效果", r"过载[:：]"),
        ("shorter_interval", "skill_attack_interval", "技能", "有技能能缩短自身攻击间隔",
         r"(?:^|[，,；;:：]|且|随后)(?:自身|自己的)?攻击间隔(?:超大幅度|极大幅度|较大幅度|较小幅度|大幅度|小幅度|超大幅|极大幅|较大幅|大幅|小幅|略微|稍微|一定程度)?(?:缩短|减小|降低)"),
        ("stop_attack", "skill_stop_attack", "技能", "有技能会让自身停止攻击", r"(?:^|[，；:：]|\d+秒内|后|立即)[^，；:：]{0,30}停止攻击(?:敌人)?"),
    )
    for code, topic, family, sentence, pattern in skill_mechanics:
        found = explicit_skill_fact(profile["skills"], pattern)
        if found:
            add(f"mechanic:{code}", family, topic, sentence,
                f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    direct_dp = direct_dp_skill(profile["skills"])
    if direct_dp:
        add("mechanic:deployment_cost", "技能", "skill_dp", "有技能可以直接获得部署费用",
            f"技能「{direct_dp[0]}」（最高等级）：{compact(direct_dp[1])}")
    self_loss = self_hp_loss_skill(profile["skills"])
    if self_loss:
        add("mechanic:self_hp_loss", "生存", "skill_hp", "有技能会使自身流失生命",
            f"技能「{self_loss[0]}」（最高等级）：{compact(self_loss[1])}")
    for key, family, topic, sentence, pattern in SKILL_TEXT_FACTS:
        if key == "attack:arts_switch" and (profile["profession"] == "术师"
                or re.search(r"^(?:普通)?攻击造成(?:群体)?法术伤害", trait)):
            continue
        found = explicit_skill_fact(profile["skills"], pattern)
        if key == "heal:all_allies" and found and not all_allies_life_heal(found[1]):
            found = next(((skill["name"], skill["text"]) for skill in profile["skills"]
                          if re.search(pattern, skill["text"]) and all_allies_life_heal(skill["text"])), None)
        if found:
            add(key, family, topic, sentence,
                f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    physical_talent = next(((name, phrase) for name, phrase in profile["talents"]
                            if re.search(r"技能开启时.{0,30}攻击变为物理伤害", phrase)), None)
    if physical_talent:
        add("attack:physical_switch", "攻击", "damage_switch", "有技能能将普通攻击改为物理伤害",
            f"天赋「{physical_talent[0]}」：{compact(physical_talent[1])}")
    found_high_def = next(((f"技能「{s['name']}」（最高等级）", s["text"]) for s in profile["skills"]
                           if re.search(r"优先攻击.{0,20}防御力(?:最高|较高)", s["text"])), None)
    if not found_high_def:
        found_high_def = next(((f"天赋「{tname}」", tphrase) for tname, tphrase in profile["talents"]
                               if re.search(r"优先攻击.{0,20}防御力(?:最高|较高)", tphrase)), None)
    if found_high_def:
        add("target:high_def_first", "目标", "target_priority", "优先攻击防御力高的敌人",
            f"{found_high_def[0]}：{compact(found_high_def[1])}")
    trap_evidence = trap_skill_evidence(profile)
    if trap_evidence:
        add("skill:trap", "召唤", "deployable_kind", "有技能可以获得或部署陷阱",
            trap_evidence)
    max_hp_heal = self_max_hp_ratio_heal_skill(profile["skills"])
    if max_hp_heal:
        name, description, note = max_hp_heal
        evidence = f"技能「{name}」（最高等级）：{compact(description).rstrip('；;，,。 ')}"
        if note:
            evidence += f"；本地技能参数：{note}"
        add("heal:max_hp_ratio", "恢复", "heal_amount", "有技能按生命上限比例回复自身生命值",
            evidence)
    for key, family, topic, sentence, pattern in (
        ("heal:extra_bounce", "恢复", "heal_targets", "技能可增加治疗的跳跃次数",
         r"(?:治疗|治愈).{0,28}(?:跳跃|弹跳).{0,15}(?:增加|\+)\d+次|(?:跳跃|弹跳)次数\+\d+"),
        ("attack:extra_target", "攻击", "attack_targets", "有技能可使一次攻击额外命中一个目标",
         r"攻击目标数\+[1一]|(?:攻击|目标数).{0,18}(?:额外|增加|\+)[一1](?:名|个)目标|额外攻击[一1](?:名|个)(?:敌人|目标)"),
        ("attack:splash_radius_expand", "攻击", "attack_spread", "有技能可扩大攻击的溅射或爆炸范围",
         r"(?:爆炸|溅射)(?:范围|半径).{0,12}(?:扩大|提升|增加|变为)"),
        ("attack:bonus_arts_hit", "攻击", "extra_damage", "技能攻击会附加按自身攻击力计算的法术伤害",
         r"(?:每次攻击|每一击|攻击时|攻击).{0,35}附(?:加|带)(?:相当于)?攻击力\d+%的法术伤害"),
        ("skill:allied_skill_trigger", "支援", "ally_skill", "技能可以使同阵营其他干员立即发动已就绪的技能",
         r"立刻使技能就绪的【[^】]+】干员同时开启技能"),
        ("skill:dp_over_time", "技能", "skill_dp", "有技能会在持续期间逐渐获得部署费用",
         r"(?:技能持续期间|持续时间内|一段时间内)(?:内)?(?:共|总共)?(?:获得|回复)(?:总共|共)?\d+点(?:部署)?费用|(?:期间)?逐渐(?:获得|回复)\d+点(?:部署)?费用|每秒(?:获得|回复)\d+点(?:部署)?费用"),
    ):
        found = explicit_skill_fact(profile["skills"], pattern)
        if found:
            add(key, family, topic, sentence,
                f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    for skill in profile["skills"]:
        res_match = re.search(r"(?:^|[，；])法术抗性\+\d+%?", skill["text"])
        if not res_match:
            continue
        previous_clause = re.split(r"[；;。]", skill["text"][:res_match.start()])[-1]
        if (re.search(r"(?:友方|我方|目标|摄影车|召唤物|装置)(?:干员|单位|角色)?.{0,120}$", previous_clause)
                or re.search(r"所有摄影车", previous_clause)):
            continue
        add("self:skill_resistance", "生存", "self_skill_resistance", "有技能可提高自身法术抗性",
            f"技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
        break
    for skill in profile["skills"]:
        hp_match = re.search(r"(?:^|[，；])(?:最大生命值|生命上限)\+\d+%", skill["text"])
        if not hp_match:
            continue
        previous_clause = re.split(r"[；;。]", skill["text"][:hp_match.start()])[-1]
        if (re.search(r"(?:友方|我方|目标)(?:干员|单位|角色)?.{0,120}$", previous_clause)
                or re.search(r"的(?:阻挡数|攻击力|防御力)\+\d+[^；。]{0,25}$", previous_clause)):
            continue
        add("self:skill_max_hp", "生存", "self_skill_max_hp", "有技能能提高自身生命上限",
            f"技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
        break
    for amount in (2, 3, 4, 5):
        found = explicit_skill_fact(profile["skills"], rf"(?:可|可以)充能{amount}次")
        if found:
            add(f"mechanic:charge:{amount}", "技能", "skill_charge",
                f"有技能在最高等级可充能{amount}次",
                f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    for skill in profile["skills"]:
        ammo_match = re.search(r"(?:攻击装有|技能拥有|装有)(\d+)(?:发|枚)(?:弹药|子弹)", skill["text"])
        if ammo_match:
            amount = int(ammo_match.group(1))
            if 1 <= amount <= 120:
                add(f"skill:ammo:{amount}", "数值", "skill_resource",
                    f"有技能在最高等级拥有{amount}发（枚）弹药",
                    f"技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
    hit_witnesses = {}
    for skill in profile["skills"]:
        for count in skill_hit_counts(skill["text"]):
            hit_witnesses.setdefault(count, skill)
    for count, skill in sorted(hit_witnesses.items()):
        code = {2: "two_hits", 3: "three_hits"}.get(count, f"{count}_hits")
        add(f"attack:{code}", "攻击", "hit_count",
            f"有技能可连续进行{HIT_COUNT_LABELS[count]}次攻击",
            f"技能「{skill['name']}」（最高等级）：{compact(skill['text'])}")
    for code, pattern, sentence in (
        ("ignore_defense", r"(?:攻击|伤害|命中|炮弹).{0,30}无视.{0,16}防御力|无视.{0,16}防御力",
         "有技能可以无视敌人的部分防御力"),
        ("ignore_resistance", r"(?:攻击|伤害|命中).{0,30}无视.{0,16}法术抗性|无视.{0,16}法术抗性",
         "有技能可以无视敌人的部分法术抗性"),
    ):
        found = explicit_skill_fact(profile["skills"], pattern)
        if found:
            add(f"attack:{code}", "攻击", "ignore_defense", sentence,
                f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    found = explicit_skill_fact(profile["skills"], r"攻击范围扩大至(?:整个战场|全场)")
    if found:
        add("range:battlefield", "范围", "range_expand", "有技能能将攻击范围扩大至整个战场",
            f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    found = explicit_skill_fact(profile["skills"], r"部署后立即对.{0,40}(?:敌人|目标).{0,35}造成.{0,40}伤害")
    if found:
        add("attack:on_deploy", "攻击", "deploy_attack", "有技能能在部署后立即对敌人造成伤害",
            f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    found = counterattack_skill(profile["skills"])
    if found:
        add("attack:counter_on_hit", "攻击", "counterattack",
            "有技能可在自身遭到攻击时反击敌人",
            f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    found = attack_self_heal_skill(profile["skills"])
    if found:
        add("heal:attack_self", "恢复", "attack_heal", "有技能可在攻击时回复自身生命值",
            f"技能「{found[0]}」（最高等级）：{compact(found[1])}")
    found = explicit_skill_fact(profile["skills"], r"优先攻击(?:空中|飞行)(?:敌人|单位|目标)")
    if found:
        add("target:prefer_air", "目标", "target_priority", "有技能优先攻击空中敌人",
            f"技能「{found[0]}」（最高等级）：{compact(found[1])}")

    for code, pattern, sentence in (
        ("defense", r"(?:敌人|敌方|目标).{0,24}防御力.{0,12}(?:降低|减少|下降|-[0-9])", "可以降低敌人的防御力"),
        ("resistance", r"(?:敌人|敌方|目标).{0,24}法术抗性.{0,12}(?:降低|减少|下降|-[0-9])", "可以降低敌人的法术抗性"),
        ("weak", r"(?:敌人|敌方|目标).{0,30}(?:虚弱|攻击力(?:降低|减少|下降|-[0-9]))|攻击力(?:降低|减少|下降|-[0-9]).{0,15}(?:敌人|目标)", "可以降低敌人的攻击力"),
    ):
        found = next(((source, phrase) for source, phrase in all_sources if re.search(pattern, phrase)), None)
        if found:
            add(f"debuff:{code}", "削弱", f"debuff_{code}", sentence,
                f"{found[0]}：{compact(found[1])}")
    for code, stat, sentence in (
        ("attack_speed", "攻击速度", "可以降低敌人的攻击速度"),
        ("move_speed", "移动速度", "可以降低敌人的移动速度"),
    ):
        pattern = rf"(?:敌人|敌方|敌军|目标|使其|令其).{{0,45}}{stat}(?:-|下降|降低|减少)"
        found = next(((source, phrase) for source, phrase in all_sources if re.search(pattern, phrase)), None)
        if found:
            add(f"debuff:{code}", "削弱", f"debuff_{code}", sentence,
                f"{found[0]}：{compact(found[1])}")
    dodge = next(((source, phrase) for source, phrase in all_sources
                  if re.search(r"(?:自身|自己).{0,24}闪避", phrase)), None)
    if dodge:
        add("self:dodge", "生存", "dodge_type", "自身可以获得闪避能力",
            f"{dodge[0]}：{compact(dodge[1])}")
    shield = self_shield_source(all_sources)
    if shield:
        add("self:shield", "生存", "self_shield", "自身可以获得护盾或屏障",
            f"{shield[0]}：{compact(shield[1])}")
    elif audited.get("self_shield"):
        add("self:shield", "生存", "self_shield", "自身可以获得护盾或屏障",
            audited["self_shield"])
    regen = self_regen_source(all_sources)
    if regen:
        add("self:regen", "生存", "self_regen", "自身可以持续回复生命值",
            f"{regen[0]}：{compact(regen[1])}")
    dot = enemy_dot_source(all_sources)
    if dot:
        add("damage:over_time", "伤害", "damage_over_time", "可以对敌人造成持续伤害",
            f"{dot[0]}：{compact(dot[1])}")

    multi_output_effects = {code: ally_effect(all_sources, {code: words}, require_multi=True)
                            for code, words in OUTPUT_BUFF.items()}
    other_output_effects = {code: ally_effect(all_sources, {code: words})
                            for code, words in OUTPUT_BUFF.items()}
    if audited.get("output_multi") and not any(multi_output_effects.values()):
        multi_output_effects["attack"] = ("attack", audited["output_multi"])
        other_output_effects["attack"] = ("attack", audited["output_multi"])
    if any(multi_output_effects.values()):
        evidence = next(effect[1] for effect in multi_output_effects.values() if effect)
        add("ally:output_multi", "支援", "ally_output", "天赋或技能可为多名其他干员提供输出增益", evidence)
    for output_code, effect in other_output_effects.items():
        if effect:
            add(f"ally:output:{output_code}", "支援", "ally_output",
                {"attack": "能提高其他干员的攻击力或造成的伤害",
                 "speed": "可以提高其他干员的攻击速度",
                 "penetration": "能让其他干员的攻击无视部分敌方防御或法术抗性",
                 "ammo": "能提高其他干员的技能弹药上限"}[output_code],
                effect[1])
    sp_support = ally_effect(all_sources, {"sp": ("技力",)}, require_multi=True, skills=profile["skills"])
    if sp_support:
        add("ally:sp_support", "支援", "ally_sp", "能为多名其他干员提供技力增益", sp_support[1])
    survival_effects = {code: ally_effect(all_sources, {code: words}) for code, words in SURVIVAL.items()}
    if any(survival_effects.values()):
        evidence = next(effect[1] for effect in survival_effects.values() if effect)
        add("ally:survival_nonheal", "支援", "ally_survival", "能为其他干员提供生存增益（不含治疗）", evidence)
        for survival_code, effect in survival_effects.items():
            if effect:
                add(f"ally:survival:{survival_code}", "支援", "ally_survival",
                    {"defense": "能提高其他干员的防御能力", "resistance": "能提高其他干员的法术抗性",
                     "dodge": "能提高其他干员的闪避", "shield": "能为其他干员提供护盾或屏障",
                     "shelter": "能为其他干员提供受伤害降低（庇护）效果", "conceal": "能使其他干员获得迷彩或隐匿",
                     "max_hp": "能提高其他干员的生命上限", "resist_status": "能使其他干员获得【抵抗】状态（缩短异常状态时间）"}[survival_code], effect[1])
    regen = own_regen(all_sources)
    if regen or audited.get("hunger_regen"):
        add("heal:hunger", "恢复", "regen", "能为无法被直接治疗的干员回复生命（缓回）",
            audited.get("hunger_regen") or f"{regen[0]}：{regen[1]}")
    direct_other = next(((source, phrase) for source, phrase in all_sources
                         if re.search(r"(?:恢复|回复|治疗).{0,20}(?:友方|我方|其他).{0,18}(?:干员|单位).{0,18}生命|"
                                      r"(?:友方|我方|其他).{0,18}(?:干员|单位).{0,25}(?:恢复|回复|治疗).{0,20}生命", phrase)
                         and not re.search(r"(?:每秒|生命回复速度|持续恢复).{0,20}生命", phrase)), None)
    if not direct_other and profile["branch"] in HEALING_ATTACK_BRANCHES:
        branch_cn = BRANCH_NAMES.get(profile["branch"], profile["branch"])
        direct_other = ("特性", f"{branch_cn}分支特性：普通攻击为直接治疗友方目标")
    if (not direct_other and not direct_heal(all_sources) and not has_summons) or audited.get("no_direct_heal"):
        add("heal:no_direct", "恢复", "direct_heal", "没有直接治疗其他干员的能力",
            audited.get("no_direct_heal") or "技能、天赋及模组未发现直接治疗；生命回复速度另计")
    if direct_other:
        add("heal:direct_other", "恢复", "direct_heal", "可以直接治疗其他干员",
            f"{direct_other[0]}：{compact(direct_other[1])}")
    for key, pattern, sentence in (
        ("ally:block_up", r"(?:周围其他友方干员|周围其他友方单位|所有阻挡数大于0的友方角色|友方干员|友方单位|其他干员|其他友方|身前一名干员|前方干员|身前一格.{0,55}我方干员).{0,65}阻挡数(?:\+[1-9]|增加|提升|提高)",
         "可以提高其他干员的阻挡数"),
        ("ally:range_up", r"(?:友方|我方|其他)[^，；。]{0,32}(?:干员|单位)[^，；。]{0,20}攻击范围(?:扩大|增加|\+)",
         "可以扩大其他干员的攻击范围"),
        ("ally:elemental_resist", r"(?:友方|我方|其他).{0,32}(?:干员|单位).{0,25}受到的元素损伤(?:降低|减少|-)",
         "可以降低其他干员受到的元素损伤"),
        ("ally:prevent_death", r"(?:一名干员|友方干员|友方单位|其他干员|我方干员).{0,45}生命值.{0,25}不低于1|(?:友方|我方|其他).{0,32}(?:干员|单位).{0,45}生命值.{0,20}不低于1|(?:其他友方干员|(?:友方|我方).{0,12}干员|[A-Za-z ]+成员).{0,25}受到致命伤害时.{0,20}(?:陷入沉睡|不撤退)|承担.{0,25}我方干员受到的致命伤害",
         "可以使其他干员暂时免于致命伤害"),
    ):
        found = next(((source, phrase) for source, phrase in all_sources if re.search(pattern, phrase)), None)
        if found:
            add(key, "支援", key, sentence, f"{found[0]}：{compact(found[1])}")
    elemental_heal = next(((source, phrase) for source, phrase in all_sources
                           if re.search(r"(?:友方|我方|其他).{0,45}(?:恢复|回复|治疗).{0,30}元素损伤|"
                                        r"(?:恢复|回复|治疗).{0,25}(?:友方|我方|其他).{0,30}元素损伤", phrase)), None)
    if elemental_heal:
        add("heal:elemental_loss", "恢复", "elemental_heal", "可以为友方回复元素损伤",
            f"{elemental_heal[0]}：{compact(elemental_heal[1])}")

    outside = [s for s in profile["skills"] if outside_attack_status(profile, s) is True]
    if len(outside) >= 2:
        add("range:two_skills_outside", "范围", "range_expand", "不止一个技能可以攻击原本攻击范围外的敌人",
            "、".join(f"{s['name']}：{compact(s['text'], 60)}"
                     + (f"（范围 {profile['base_range_id']} → {s['range_id']}，新增"
                        f"{len(range_extra_cells(profile['base_range_id'], s['range_id']))}格）"
                        if range_extra_cells(profile["base_range_id"], s["range_id"]) else "")
                     for s in outside))
    talent_shrink = next((f"天赋「{name}」：{compact(phrase)}" for name, phrase in profile["talents"]
                          if re.search(r"技能开启时.{0,25}攻击范围缩小", phrase)), None)
    shrink_cond = (audited.get("range_shrink") or talent_shrink
                   or any(re.search(r"攻击(?:范围|距离)(?:缩小|缩短|-\d+)", s["text"])
                          for s in profile["skills"]))
    if shrink_cond:
        add("range:can_shrink", "范围", "range_change", "有技能开启后会缩小攻击范围",
            audited.get("range_shrink") or talent_shrink or "技能文字明确写明攻击范围缩小或攻击距离缩短")
    if len(outside) >= 2 and shrink_cond:
        add("combo:outside_and_shrink", "复合", "range_change",
            "不止一个技能可攻击原范围外敌人，但开启某技能也会缩小范围",
            "可分别盘点不同技能；模组条件不在此线索中混用")

    rarity_count = len(branch_rarities[profile["branch"]])
    if 1 <= rarity_count <= 6:
        add(f"branch:rarities:{rarity_count}", "统计", "branch_rarity",
            f"所在分支覆盖{rarity_count}个星级", f"431名干员中，该分支星级为：{'、'.join(map(str, sorted(branch_rarities[profile['branch']])))}")
    branch_name = BRANCH_NAMES.get(profile["branch"])
    if branch_name:
        add(f"branch:identity:{profile['branch']}", "统计", "branch_identity",
            f"属于{branch_name}分支", f"干员档案：{profile['profession']}／{branch_name}")
    add(f"rarity:exact:{profile['rarity']}", "统计", "rarity_exact",
        f"星级为{profile['rarity']}星", f"干员档案：{profile['rarity']}星")
    add(f"profession:exact:{profile['profession']}", "统计", "profession_exact",
        f"职业为{profile['profession']}", f"干员档案：职业为{profile['profession']}")
    base_cost = profile["cost_maxpot"]
    all_costs = [base_cost + m.get("cost_delta", 0) for m in profile["modules"]]
    if all(10 <= c <= 99 for c in all_costs):
        add("cost:maxpot:two_digits", "统计", "maxpot_cost", "满潜满练时部署费用为两位数",
            f"最高精英阶段满潜能面板费用（含常规模组）为 {base_cost}" if len(set(all_costs)) == 1
            else f"无论是否装备模组，满潜满练部署费用均为两位数（{min(all_costs)}～{max(all_costs)}）")
    if all(c <= 9 for c in all_costs):
        add("cost:maxpot:one_digit", "统计", "maxpot_cost", "满潜满练时部署费用为一位数",
            f"最高精英阶段满潜能面板费用（含常规模组）为 {base_cost}" if len(set(all_costs)) == 1
            else f"无论是否装备模组，满潜满练部署费用均为一位数（{min(all_costs)}～{max(all_costs)}）")
    if len(set(all_costs)) == 1:
        cost = all_costs[0]
        add(f"cost:maxpot:exact:{cost}", "数值", "maxpot_cost",
            f"满潜满练时部署费用为{cost}", f"最高精英阶段满潜能面板费用（含常规模组）为 {cost}")
    return output


def implied_fact_ids(key: str) -> list[str]:
    """题面明确包含的较弱事实；同一题不能再拿它们充当另一条线索。"""
    parts = key.split(":")
    implied = set()
    if key == "combo:one_damage_no_control":
        implied.update(("damage:only_one", "control:none"))
    elif key == "combo:two_damage_one_control":
        implied.update(("damage:exact_two", "control:one"))
    elif key == "combo:outside_and_shrink":
        implied.update(("range:two_skills_outside", "range:can_shrink"))
    elif key == "range:two_skills_outside":
        implied.add("range:expand")
    elif len(parts) == 4 and parts[:2] == ["skill", "activation_sp"]:
        implied.update((f"skill:activation:{parts[2]}", f"skill:sp:{parts[3]}"))
    elif len(parts) == 4 and parts[:2] == ["skill", "two_sp"]:
        implied.update((f"skill:sp:{parts[2]}", f"skill:sp:{parts[3]}"))
    elif len(parts) == 3 and parts[:2] == ["combo", "aoe_control"]:
        implied.update(("attack:true_aoe", f"control:can:{parts[2]}"))
    elif len(parts) == 4 and parts[:2] == ["combo", "skill_damage_control"]:
        implied.update((f"damage:can:{parts[2]}", f"control:can:{parts[3]}"))
    elif len(parts) == 4 and parts[:2] == ["combo", "skill_two_controls"]:
        implied.update((f"control:can:{parts[2]}", f"control:can:{parts[3]}"))
    elif len(parts) == 4 and parts[:2] == ["combo", "skill_two_damage"]:
        implied.update((f"damage:can:{parts[2]}", f"damage:can:{parts[3]}"))
    elif key == "attack:normal_splash_arts":
        implied.add("attack:true_aoe")
    elif key == "attack:normal_splash_physical_air":
        implied.update(("air:normal_attack", "attack:true_aoe"))
    elif key == "attack:bonus_arts_hit":
        implied.add("attack:extra_arts")
    elif key == "target:normal_air_priority":
        implied.add("air:normal_attack")
    return sorted(implied)


def build_facts(profiles: list[dict]) -> tuple[list[dict], list[list[int]]]:
    branch_rarities = defaultdict(set)
    for profile in profiles:
        branch_rarities[profile["branch"]].add(profile["rarity"])
    facts: dict[str, dict] = {}
    for index, profile in enumerate(profiles):
        for key, family, topic, sentence, evidence in facts_for(profile, branch_rarities):
            fact = facts.setdefault(key, {"id": key, "family": family, "topic": topic,
                                          "text": sentence, "members": [], "evidence": {}})
            if index not in fact["evidence"]:
                fact["members"].append(index)
                fact["evidence"][index] = ["本地战斗资料与机制规则", evidence, profile["name"]]
    useful = [fact for fact in facts.values() if 1 <= len(fact["members"]) < len(profiles)]
    useful.sort(key=lambda x: x["id"])
    useful_by_id = {fact["id"]: fact for fact in useful}
    for fact in useful:
        fact["members"].sort(key=lambda idx: operator_sort_key(profiles[idx]))
        fact["memberNames"] = [profiles[index]["name"] for index in fact["members"]]
        implies = [fid for fid in implied_fact_ids(fact["id"])
                   if fid in useful_by_id
                   and set(fact["members"]) <= set(useful_by_id[fid]["members"])]
        if implies:
            fact["implies"] = sorted(implies)
    # 单人 PRTS 人工核对只证明该干员满足，不代表其它未核对者不满足。
    known_air = set(useful_by_id["air:normal_attack"]["members"]) if "air:normal_attack" in useful_by_id else set()
    known_air.update(index for index, profile in enumerate(profiles)
                     if AUDITED.get(profile["id"], {}).get("air_damage"))
    known_no_air = set(useful_by_id["air:solo_none"]["members"]) if "air:solo_none" in useful_by_id else set()
    possible_support_members = {
        kind: {index for index, profile in enumerate(profiles) if possible_support(profile, kind)}
        for kind in ("attack", "speed", "penetration", "ammo", "survival", "sp")
    }
    # 召唤物属于干员能力；目前文字解析未逐一覆盖其友方增益与连击。
    possible_summon_members = {index for index, item in enumerate(profiles) if item["has_summons"]}
    unknown_summons = {index for index, item in enumerate(profiles)
                       if item["has_summons"] and not AUDITED.get(item["id"], {}).get("summon_no_damage_control")}
    exhaustive_facts = {"damage:only_one", "damage:exact_two", "control:none", "control:one",
                        "combo:one_damage_no_control", "combo:two_damage_one_control"}
    for fact in useful:
        if fact["id"] == "air:normal_attack":
            fact["possibleMembers"] = [index for index in range(len(profiles)) if index not in known_no_air]
        elif fact["id"] == "air:solo_none":
            fact["possibleMembers"] = [index for index in range(len(profiles)) if index not in known_air]
        elif fact["id"] in exhaustive_facts or fact["id"].startswith(("damage:only:", "control:exact:")):
            # 召唤物尚未审完时，不能把未产出排他事实当作明确不满足。
            fact["possibleMembers"] = sorted(set(fact["members"]) | unknown_summons)
        elif fact["id"] == "ally:output_multi":
            fact["possibleMembers"] = sorted(set(fact["members"]) |
                set().union(*(possible_support_members[kind] for kind in OUTPUT_BUFF)) |
                possible_summon_members)
        elif fact["id"].startswith("ally:output:"):
            kind = fact["id"].rsplit(":", 1)[-1]
            fact["possibleMembers"] = sorted(set(fact["members"]) | possible_support_members[kind] |
                                             possible_summon_members)
        elif fact["id"].startswith("ally:survival"):
            fact["possibleMembers"] = sorted(set(fact["members"]) |
                                             possible_support_members["survival"] |
                                             possible_summon_members)
        elif fact["id"] == "ally:sp_support":
            fact["possibleMembers"] = sorted(set(fact["members"]) |
                                             possible_support_members["sp"] |
                                             possible_summon_members)
        elif fact["id"] == "mechanic:next_attack":
            # 未严格识别的“下一次攻击”写法不能在唯一性筛选时被当成否定。
            possible = {index for index, profile in enumerate(profiles)
                        if any(re.search(r"(?:下次|下一次).{0,6}攻击", skill["text"])
                               for skill in profile["skills"])}
            fact["possibleMembers"] = sorted(set(fact["members"]) | possible)
        elif fact["id"] == "range:two_skills_outside":
            # 网格变化有时只描述治疗、装置或状态范围；无法确认攻击对象时保留为候选。
            possible = {index for index, profile in enumerate(profiles)
                        if sum(outside_attack_status(profile, skill) is not False
                               for skill in profile["skills"]) >= 2}
            fact["possibleMembers"] = sorted(set(fact["members"]) | possible)
        elif fact["id"] == "block:skill_change":
            # 友方群体或装置前方干员是否包含施放者，不能只由短描述判定。
            possible = {index for index, profile in enumerate(profiles)
                        if any(re.search(r"(?:(?:所有|全部)(?:友方|我方)(?:单位|干员)|前方干员).{0,10}阻挡数(?:\+|-|增加|减少|变为)",
                                         skill["text"])
                               for skill in profile["skills"])}
            fact["possibleMembers"] = sorted(set(fact["members"]) | possible)
        elif fact["id"].startswith("attack:") and fact["topic"] == "hit_count":
            count = {"two_hits": 2, "three_hits": 3}.get(fact["id"].split(":", 1)[1])
            if count is None:
                count = int(fact["id"].split(":", 1)[1].split("_", 1)[0])
            terms = [str(count)] + [word for word, number in HIT_COUNT_WORDS.items() if number == count]
            possible = {index for index, profile in enumerate(profiles)
                        if any(count in skill_hit_counts(skill["text"])
                               for skill in profile["skills"])}
            fact["possibleMembers"] = sorted(set(fact["members"]) | possible |
                                             possible_summon_members)
    by_operator = [[] for _ in profiles]
    for number, fact in enumerate(useful):
        for index in fact["members"]:
            by_operator[index].append(number)
    return useful, by_operator


def find_round(candidates: list[int], facts: list[dict], masks: list[int], count: int,
               rng: random.Random) -> list[int] | None:
    if len(candidates) < 4:
        return None
    universe = (1 << count) - 1
    anchor_ids = {"attack:true_aoe", "combo:outside_and_shrink",
                  "range:two_skills_outside", "heal:hunger", "ally:output_multi", "ally:survival_nonheal"}
    anchor_ids.update(facts[n]["id"] for n in candidates if facts[n]["id"].startswith("attack:skill_targets:"))
    for _ in range(700):
        chosen = []
        used_topics = set()
        remaining = universe
        pool = candidates[:]
        rng.shuffle(pool)
        for step in range(4):
            options = []
            for fact_index in pool:
                fact = facts[fact_index]
                if fact["topic"] in used_topics:
                    continue
                if any((fact["id"].startswith("combo:") and fact["id"] in {"combo:one_damage_no_control", "combo:two_damage_one_control"}
                        and facts[n]["id"].startswith(("damage:", "control:")))
                       or (facts[n]["id"] in {"combo:one_damage_no_control", "combo:two_damage_one_control"}
                           and fact["id"].startswith(("damage:", "control:"))) for n in chosen):
                    continue
                if fact["family"] in {"统计", "数值"} and any(facts[n]["family"] in {"统计", "数值"} for n in chosen):
                    continue
                if fact["family"] == "复合" and any(facts[n]["family"] == "复合" for n in chosen):
                    continue
                if any((facts[n]["id"] in fact.get("implies", ()))
                       or (fact["id"] in facts[n].get("implies", ()))
                       or masks[fact_index] == masks[n]
                       for n in chosen):
                    continue
                size = (remaining & masks[fact_index]).bit_count()
                if step < 3 and size < 2:
                    continue
                if step == 3 and size != 1:
                    continue
                if size == remaining.bit_count():
                    continue
                quality = (3 if fact["id"] in anchor_ids else 2 if fact["family"] == "复合"
                           or fact["id"].startswith("control:can:")
                           or fact["family"] in {"技能", "攻击", "恢复", "范围", "削弱", "生存", "阻挡", "召唤"}
                           else 1 if fact["family"] in {"伤害", "支援", "目标"}
                           else -2 if fact["family"] == "数值" else 0)
                options.append((math.log2(size) - quality * 0.55, rng.random(), fact_index))
            if not options:
                break
            options.sort()
            window = options[:min(10, len(options))] if step < 3 else options
            picked = rng.choice(window)[2]
            chosen.append(picked)
            used_topics.add(facts[picked]["topic"])
            remaining &= masks[picked]
        if len(chosen) == 4 and len({facts[n]["family"] for n in chosen}) >= 3:
            return chosen
    return None


def write_catalog(profiles: list[dict], facts: list[dict]) -> None:
    """从发布事实生成完整目录，避免手工名目与索引版本脱节。"""
    by_family = defaultdict(list)
    for fact in facts:
        by_family[fact["family"]].append(fact)
    lines = ["明日方舟「猜干员」事实索引全线索名目",
             f"干员：{len(profiles)} 人；事实：{len(facts)} 条；分类：{len(by_family)} 种",
             "由 生成游戏数据.py 根据 事实索引.js 同一批事实自动生成。",
             "满足干员列出确认成员；唯一性校验还会考虑 possibleMembers 中的待核对成员。", ""]
    order = ("目标", "攻击", "阻挡", "范围", "伤害", "控制", "复合", "削弱", "恢复",
             "生存", "支援", "召唤", "部署", "天赋", "技能", "数值", "统计")
    number = 0
    for family in order:
        entries = by_family.get(family, [])
        if not entries:
            continue
        lines.extend((f"{family}（{len(entries)} 条）", "=" * 60))
        for fact in entries:
            number += 1
            lines.append(f"[{number:03d}] {fact['text']}")
            lines.append(f"ID：{fact['id']}　主题：{fact['topic']}　满足：{len(fact['members'])} 人")
            if fact.get("implies"):
                lines.append("已包含：" + "、".join(fact["implies"]))
            names = fact["memberNames"]
            for start in range(0, len(names), 12):
                lines.append(("干员：" if start == 0 else "　　　")
                             + "、".join(names[start:start + 12]))
            lines.append("")
        lines.append("")
    catalog = "\n".join(lines).rstrip() + "\n"
    for path in CATALOG_OUTPUTS:
        path.write_text(catalog, encoding="utf-8")


def main() -> None:
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    amiya_module_map = {
        "char_002_amiya": {"uniequip_001_amiya", "uniequip_002_amiya"},
        "char_1001_amiya2": {"uniequip_001_amiya2", "uniequip_002_amiya2"},
        "char_1037_amiya3": {"uniequip_001_amiya3", "uniequip_002_amiya3"},
    }
    ops_dict = data.get("干员", {})
    if "char_002_amiya" in ops_dict:
        amiya_mods = ops_dict["char_002_amiya"].get("模组资料", []) or []
        for cid, valid_ids in amiya_module_map.items():
            if cid in ops_dict:
                ops_dict[cid]["模组资料"] = [
                    m for m in amiya_mods
                    if (m.get("模组资料") or {}).get("模组编号") in valid_ids
                ]
    profiles = [make_profile(operator) for operator in data["干员"].values()]
    profiles.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    facts, by_operator = build_facts(profiles)
    masks = [sum(1 << n for n in fact.get("possibleMembers", fact["members"])) for fact in facts]
    fallback = {}
    for index, available in enumerate(by_operator):
        seed = sum(map(ord, profiles[index]["id"])) + index * 7919
        found = find_round(available, facts, masks, len(profiles), random.Random(seed))
        if found:
            fallback[index] = found
    if len(fallback) != len(profiles):
        missing = "、".join(profile["name"] for index, profile in enumerate(profiles) if index not in fallback)
        raise ValueError(f"有干员无法组成唯一的四线索题目，拒绝发布不完整答案池：{missing}")
    released = {
        "version": f"{data['资料说明'].get('来源提交') or 'local'}:{hashlib.sha256(raw).hexdigest()[:12]}:semantic-46",
        "operators": [{key: item[key] for key in ("id", "name", "profession", "rarity", "archive")} for item in profiles],
        "facts": facts, "byOperator": by_operator, "fallback": fallback,
    }
    header = ("// 自动生成的离线事实索引；修改规则请编辑 生成游戏数据.py，再重新生成本文件。\n"
              "// operators 的数组位置是干员编号；facts[].members 保存满足线索的编号，memberNames 按相同顺序列出姓名。\n"
              "// facts[].evidence[干员编号] = [依据来源, 描述摘录, 干员姓名]；possibleMembers 包含尚不能排除的干员编号。\n"
              "// facts[].implies 是该线索已经包含的较弱事实 ID；同一题不得同时使用。\n"
              "// byOperator[干员编号] 是其事实编号；fallback[干员编号] 是可组成唯一答案的四条事实编号。\n"
              "// 线索目录：事实 ID｜线索文字｜确认满足人数\n")
    header += "".join(f"// {fact['id']}｜{fact['text']}｜{len(fact['members'])} 人\n" for fact in facts)
    OUTPUT.write_text(header + "window.GUESS_DATA = " + json.dumps(released, ensure_ascii=False, indent=2) + ";\n",
                      encoding="utf-8")
    write_catalog(profiles, facts)
    print(f"候选干员：{len(profiles)}；机制事实：{len(facts)}；可出题答案：{len(fallback)}")


if __name__ == "__main__":
    main()
