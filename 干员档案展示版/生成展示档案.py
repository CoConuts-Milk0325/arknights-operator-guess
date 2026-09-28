#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从现有中文服资料生成离线网页档案和 Markdown 档案。"""

from __future__ import annotations

import html
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote


目录 = Path(__file__).resolve().parent
资料文件 = 目录.parent / "干员文字资料" / "全体干员文字资料.json"
干员页目录 = 目录 / "干员档案"
非干员页目录 = 目录 / "非干员档案"
Markdown目录 = 目录 / "Markdown档案"
映射目录 = 目录 / "资料映射"
势力文件 = 目录.parent / "干员文字资料" / "原始数据_中文服" / "阵营资料表.json"
物品名称表: dict[str, str] = {}
势力名称表: dict[str, str] = {}
多语种语音表: dict[str, dict[str, list[str]]] = {}
干员语音索引: dict[str, dict[str, list[tuple[str, str, str]]]] = {}
职业分支名称表: dict[str, str] = {}
攻击范围表: dict[str, list[list[int]]] = {}
上线获得表: dict[str, dict[str, str]] = {}

字段显示名 = {
    "最大生命值": "生命上限",
    "攻击力": "攻击",
    "防御力": "防御",
    "基础攻击间隔": "攻击间隔",
    "移动速度": "移动速度",
    "攻击速度": "攻击速度",
    "法术抗性": "法术抗性",
    "部署费用": "部署费用",
    "阻挡数": "阻挡数",
    "再部署时间": "再部署时间",
    "描述": "说明",
    "名称": "名称",
    "职业": "职业",
    "部署位置": "部署位置",
    "稀有度": "星级",
    "物品用途说明": "干员简介",
    "物品描述": "干员描述",
    "物品获取方式": "获得方式",
    "属性成长节点": "等级属性",
    "等级上限": "等级上限",
    "精英化消耗材料": "精英化材料",
    "技力数据": "技力",
    "技能类型": "触发方式",
    "时长类型": "持续类型",
    "初始技力": "初始",
    "技力消耗": "消耗",
    "时长": "持续",
    "阶段": "阶段",
    "等级": "等级",
    "天赋列表": "天赋",
    "候选项列表": "天赋效果",
    "潜能提升资料": "潜能提升",
    "标签列表": "标签",
    "效果文字": "基建技能",
    "增益技能名称": "基建技能名称",
    "剧情标题": "档案栏目",
    "剧情文本": "档案内容",
    "故事列表": "档案记录",
    "干员档案": "干员档案",
    "临床记录": "临床记录",
    "干员个人记录": "个人记录",
    "剧情简介": "剧情简介",
    "记录集名称": "记录集",
    "语音标题": "语音项目",
    "语音台词": "语音台词",
    "追加语音台词": "追加语音台词",
    "服装资料": "服装资料",
    "模组资料": "模组资料",
    "召唤物资料": "召唤物资料",
    "集成战略特设数据": "集成战略资料",
    "集成战略培养数据": "集成战略培养资料",
    "信赖成长节点": "信赖加成",
    "是否限定": "限定干员",
    "是否无法获取": "当前无法获取",
    "是否为特殊形态": "特殊形态",
    "是否隐藏天赋": "隐藏天赋",
    "所需潜能等级": "潜能条件",
    "解锁参数": "解锁条件",
    "解锁说明文字": "解锁说明",
    "未解锁说明": "解锁条件",
    "显示类型": "显示方式",
    "效率": "效率",
    "房间类型": "设施",
    "等级提升消耗": "专精材料",
    "潜能等级上限": "潜能上限",
}

跳过字段 = {
    "干员ID", "干员编号旧字段", "干员编号", "技能编号", "模组ID", "服装编号",
    "资源模型编号", "资源模型键值", "干员资源模型键值", "图标编号", "图标资源编号",
    "头像资源编号", "动态立绘编号", "干员立绘编号", "技力立绘编号", "动态头像编号",
    "动态入口编号", "语音台词键值", "语音资源编号", "语音资源文件", "脚本路径",
    "剧情源ID", "剧情信息", "剧情脚本编号", "剧情编号", "记录集ID", "记录集编号",
    "职业分支编号", "攻击范围编号", "显示序号", "排序序号", "排序编号", "编号",
    "键值", "参数表", "资源模型", "干员头像编号", "特殊形态头像资源编号",
    "特殊形态干员头像编号", "召唤物服装映射", "建筑编号", "形态模板编号",
    "类型名称一", "类型名称二",
}

枚举显示 = {
    "PHASE_0": "精英0",
    "PHASE_1": "精英1",
    "PHASE_2": "精英2",
    "PHASE_3": "精英3",
    "MELEE": "近战位",
    "RANGED": "远程位",
    "AUTO": "自动触发",
    "MANUAL": "手动触发",
    "INCREASE_WITH_TIME": "自然回复",
    "INCREASE_WHEN_ATTACK": "攻击回复",
    "INCREASE_WHEN_TAKEN": "受击回复",
    "OUTPUT": "效率提升",
    "TRADING": "贸易站",
    "MANUFACTURE": "制造站",
    "POWER": "发电站",
    "CONTROL": "控制中枢",
    "DORMITORY": "宿舍",
    "MEETING": "会客室",
    "WORKSHOP": "加工站",
    "TRAINING": "训练室",
    "NONE": "无",
    "DIRECT": "直接显示",
    "FAVOR": "信赖解锁",
    "AWAKE": "精英阶段解锁",
    "STAGE": "阶段解锁",
    "CN": "中文",
    "PIONEER": "先锋",
    "WARRIOR": "近卫",
    "TANK": "重装",
    "SNIPER": "狙击",
    "CASTER": "术师",
    "MEDIC": "医疗",
    "SUPPORT": "辅助",
    "SPECIAL": "特种",
    "MATERIAL": "材料",
    "CARD_EXP": "作战记录",
    "GOLD": "龙门币",
    "BUFF": "增益",
    "COST": "部署费用",
    "ADDITION": "增加",
    "ATK": "攻击",
    "DEF": "防御",
    "MAX_HP": "生命上限",
    "RESPAWN_TIME": "再部署时间",
    "TALENT_DATA_ONLY": "天赋数据",
    "TRAIT_DATA_ONLY": "特性数据",
    "TALENT": "天赋",
    "TRAIT": "特性",
    "DISPLAY": "展示",
    "ADVANCED": "进阶",
    "INITIAL": "初始",
    "ORIGINAL": "原始",
    "CUSTOM": "自定义",
    "FUNCTION": "效果",
    "PASSIVE": "被动",
    "RECOVERY": "恢复",
    "HIRE": "招聘",
    "ROGUE": "集成战略",
    "F_EXP": "作战记录",
    "F_GOLD": "龙门币",
    "F_DIAMOND": "合成玉",
    "F_EVOLVE": "精英化",
    "F_SKILL": "技能",
    "F_ASC": "晋升",
    "F_BUILDING": "基建",
}

职业顺序 = ["先锋", "近卫", "重装", "狙击", "术师", "医疗", "辅助", "特种"]
阶段显示 = {"PHASE_0": "精英0", "PHASE_1": "精英1", "PHASE_2": "精英2", "PHASE_3": "精英3"}
占位符规则 = re.compile(r"\{([^{}]+)\}")
代码标识 = re.compile(r"^(?:char|skchr|uniequip|bskill|token|story|obt|activity|item|buff|p_char|char_effect)_[A-Za-z0-9_@#./-]+$", re.IGNORECASE)


def 转义(值: object) -> str:
    return html.escape(str(值), quote=True)


def 可展示字段(键: str) -> bool:
    if 键 in 跳过字段:
        return False
    if any(标记 in 键 for 标记 in ("编号", "ID", "键值", "资源文件", "资源编号", "模型键值")):
        return False
    if any(标记 in 键 for 标记 in ("图标", "颜色", "头像资源", "动态立绘", "立绘编号", "语音资源", "模型键")):
        return False
    if "排序" in 键:
        return False
    if 键.startswith(("资源模型", "脚本路径")):
        return False
    return True


def 收集参数(节点: object) -> dict[str, object]:
    参数: dict[str, object] = {}
    if isinstance(节点, dict):
        条目列表 = 节点.get("参数表")
        if isinstance(条目列表, list):
            for 条目 in 条目列表:
                if not isinstance(条目, dict) or not 条目.get("键值"):
                    continue
                值 = 条目.get("文字值")
                if 值 is None:
                    值 = 条目.get("数值")
                if 值 is not None:
                    参数[str(条目["键值"])] = 值
        for 子值 in 节点.values():
            if isinstance(子值, (dict, list)):
                参数.update(收集参数(子值))
    elif isinstance(节点, list):
        for 子值 in 节点:
            参数.update(收集参数(子值))
    return 参数


def 格式化占位值(值: object, 格式: str, 负数: bool = False) -> str:
    if isinstance(值, (int, float)) and not isinstance(值, bool):
        数值 = -float(值) if 负数 else float(值)
        if "%" in 格式:
            小数位 = 0
            小数格式 = re.search(r"\.(\d+)", 格式)
            if 小数格式:
                小数位 = int(小数格式.group(1))
            return f"{数值 * 100:.{小数位}f}%"
        if "." in 格式:
            小数位 = len(格式.split(".", 1)[1].rstrip("f"))
            return f"{数值:.{小数位}f}"
        if 数值.is_integer():
            return str(int(数值))
        return f"{数值:g}"
    return str(值)


def 清理富文本(文本: object, 参数: dict[str, object] | None = None, 干员名: str = "") -> str:
    原文 = str(文本 or "")
    参数 = 参数 or {}

    def 替换(match: re.Match[str]) -> str:
        代号 = match.group(1).strip()
        if 代号 in {"@nickname", "nickname"}:
            return "【博士昵称】"
        键值, 分隔符, 格式 = 代号.partition(":")
        负数 = 键值.startswith("-")
        if 负数:
            键值 = 键值[1:]
        实际键 = 键值 if 键值 in 参数 else next((现有键 for 现有键 in 参数 if 现有键.casefold() == 键值.casefold()), None)
        if 实际键 is not None:
            return 格式化占位值(参数[实际键], 格式 if 分隔符 else "", 负数)
        return "数值未标注"

    return re.sub(r"<[^>]*>", "", 占位符规则.sub(替换, 原文))


def 显示值(值: object, 参数: dict[str, object] | None = None, 干员名: str = "", 字段: str = "") -> str:
    if isinstance(值, bool):
        return "是" if 值 else "否"
    if isinstance(值, str):
        if 值 in 枚举显示:
            return 枚举显示[值]
        稀有度 = re.fullmatch(r"TIER_(\d+)", 值)
        if 稀有度:
            return f"{int(稀有度.group(1))}星"
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", 值):
            保留原名字段 = ("名称", "标题", "内容", "描述", "画师", "原案", "作者", "配音", "剧情", "台词", "作品", "品牌", "档案姓名")
            if 字段 and any(项目 in 字段 for 项目 in 保留原名字段):
                return 清理富文本(值, 参数, 干员名)
            return ""
        return 清理富文本(值, 参数, 干员名)
    return str(值)


def 干员星级(值: object) -> str:
    """汇总档案与 PRTS 的星级口径均为一至六星。"""
    if isinstance(值, str):
        已转换 = re.fullmatch(r"([1-6])星", 值)
        if 已转换:
            return 已转换.group(0)
        原始 = re.fullmatch(r"TIER_([1-6])", 值)
        if 原始:
            return f"{原始.group(1)}星"
    raise ValueError(f"无法识别干员星级：{值!r}")


def 所属势力名称(值: object) -> list[str]:
    势力: list[str] = []
    if not isinstance(值, dict):
        return 势力
    for 字段 in ("所属国家编号", "所属组织编号", "所属队伍编号"):
        编号 = 值.get(字段)
        名称 = 势力名称表.get(str(编号 or ""), "")
        if 名称 and 名称 not in {"无团队", "无", "未知"} and 名称 not in 势力:
            势力.append(名称)
    return 势力


def 显示标签(键: str) -> str:
    return 字段显示名.get(键, 键)


def 文本段落(文本: str) -> tuple[str, str]:
    清理后 = 清理富文本(文本)
    段落 = [行.strip() for 行 in 清理后.splitlines()]
    段落 = [行 for 行 in 段落 if 行]
    网页 = "".join(f"<p>{转义(行)}</p>" for 行 in 段落) or f"<p>{转义(清理后)}</p>"
    Markdown = "\n".join(f"> {行}" if 行 else ">" for 行 in 清理后.splitlines()).strip()
    return 网页, Markdown


def 递归网页(节点: object, 干员名: str, 层级: int = 0, 字段: str = "") -> str:
    if 节点 is None:
        return ""
    参数 = 收集参数(节点)
    if isinstance(节点, str):
        if 代码标识.fullmatch(节点.strip()):
            return ""
        内容 = 显示值(节点, 参数, 干员名, 字段)
        if not 内容:
            return ""
        网页, _ = 文本段落(内容)
        return f"<div class='文字内容'>{网页}</div>"
    if isinstance(节点, (int, float, bool)):
        return f"<p class='单值'>{转义(显示值(节点, 参数, 干员名, 字段))}</p>"
    if isinstance(节点, list):
        内容 = [递归网页(项目, 干员名, 层级 + 1, 字段) for 项目 in 节点]
        内容 = [项 for 项 in 内容 if 项]
        return f"<div class='条目列表'>{''.join(内容)}</div>" if 内容 else ""
    if not isinstance(节点, dict):
        return ""

    标题 = 节点.get("名称") or 节点.get("标题") or 节点.get("增益技能名称")
    字段: list[str] = []
    子内容: list[str] = []
    for 键, 值 in 节点.items():
        if not 可展示字段(str(键)) or 代码标识.fullmatch(str(键)) or 值 is None or 值 == "":
            continue
        if 键 in {"名称", "标题", "增益技能名称", "参数表"}:
            continue
        if 键 == "物品消耗" and isinstance(值, dict):
            材料网页, _ = 模组材料内容(值)
            if 材料网页:
                子内容.append(f"<div class='嵌套字段'><h4>模组升级材料</h4>{材料网页}</div>")
            continue
        if isinstance(值, (dict, list)):
            子 = 递归网页(值, 干员名, 层级 + 1, str(键))
            if 子:
                子内容.append(f"<div class='嵌套字段'><h4>{转义(显示标签(str(键)))}</h4>{子}</div>")
            continue
        标记 = 显示值(值, 参数, 干员名, str(键))
        if not 标记:
            continue
        if str(键) == "描述":
            段落, _ = 文本段落(清理富文本(值, 参数, 干员名))
            子内容.append(f"<div class='说明文字'>{段落}</div>")
        else:
            字段.append(f"<div class='资料行'><dt>{转义(显示标签(str(键)))}</dt><dd>{转义(标记)}</dd></div>")
    if not 字段 and not 子内容:
        return ""
    标题块 = f"<h3>{转义(显示值(标题, 参数, 干员名))}</h3>" if 标题 else ""
    深度类 = " 深层资料" if 层级 > 1 else ""
    return f"<article class='资料卡{深度类}'>{标题块}{'<dl>' + ''.join(字段) + '</dl>' if 字段 else ''}{''.join(子内容)}</article>"


def 递归Markdown(节点: object, 干员名: str, 层级: int = 0, 字段: str = "") -> str:
    if 节点 is None:
        return ""
    参数 = 收集参数(节点)
    if isinstance(节点, str):
        if 代码标识.fullmatch(节点.strip()):
            return ""
        内容 = 显示值(节点, 参数, 干员名, 字段)
        if not 内容:
            return ""
        _, Markdown = 文本段落(内容)
        return Markdown
    if isinstance(节点, (int, float, bool)):
        return 显示值(节点, 参数, 干员名, 字段)
    if isinstance(节点, list):
        内容 = [递归Markdown(项目, 干员名, 层级 + 1, 字段) for 项目 in 节点]
        return "\n\n".join(项 for 项 in 内容 if 项)
    if not isinstance(节点, dict):
        return ""

    标题 = 节点.get("名称") or 节点.get("标题") or 节点.get("增益技能名称")
    行项目: list[str] = []
    子项目: list[str] = []
    for 键, 值 in 节点.items():
        if not 可展示字段(str(键)) or 代码标识.fullmatch(str(键)) or 值 is None or 值 == "":
            continue
        if 键 in {"名称", "标题", "增益技能名称", "参数表"}:
            continue
        if 键 == "物品消耗" and isinstance(值, dict):
            _, 材料文字 = 模组材料内容(值)
            if 材料文字:
                子项目.append(f"**模组升级材料**\n\n{材料文字}")
            continue
        if isinstance(值, (dict, list)):
            子 = 递归Markdown(值, 干员名, 层级 + 1, str(键))
            if 子:
                子项目.append(f"**{显示标签(str(键))}**\n\n{子}")
        elif 键 == "描述":
            _, 文本 = 文本段落(清理富文本(值, 参数, 干员名))
            子项目.append(文本)
        else:
            标记 = 显示值(值, 参数, 干员名, str(键))
            if 标记:
                行项目.append(f"- **{显示标签(str(键))}：** {标记}")
    标题行 = f"**{显示值(标题, 参数, 干员名)}**\n\n" if 标题 else ""
    字段文本 = "\n".join(行项目)
    子文本 = "\n\n".join(子项目)
    return "\n\n".join(项 for 项 in [标题行 + 字段文本 if 字段文本 else 标题行.rstrip(), 子文本] if 项)


def 区块(标题: str, 网页内容: str, Markdown内容: str, 锚点: str | None = None, 说明: str = "") -> tuple[str, str]:
    if not 网页内容 and not Markdown内容:
        return "", ""
    锚点 = 锚点 or 标题
    安全锚点 = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", 锚点).strip("-")
    引导 = f"<p class='区块说明'>{转义(说明)}</p>" if 说明 else ""
    网页 = f"<section class='档案区块' id='{转义(安全锚点)}'><div class='区块题头'><span>档案栏目</span><h2>{转义(标题)}</h2></div>{引导}{网页内容}</section>"
    Markdown = f"## {标题}\n\n{说明 + chr(10) + chr(10) if 说明 else ''}{Markdown内容}".rstrip()
    return 网页, Markdown


def 解锁提示(故事: dict[str, object]) -> str:
    类型 = str(故事.get("解锁类型") or "")
    参数 = str(故事.get("解锁参数") or "")
    明文 = str(故事.get("解锁说明文字") or "").strip()
    if 明文 and 明文 not in {"？？？？？", "?????"}:
        return 明文
    if 类型 == "DIRECT":
        return "初始开放"
    if 类型 == "FAVOR" and 参数.isdigit():
        return f"提升信赖至{参数}%以查看更多信息"
    if 类型 == "AWAKE":
        阶段码 = 参数.split(";", 1)[0]
        阶段名 = 阶段显示.get(f"PHASE_{阶段码}", "精英阶段")
        return f"提升至{阶段名}以查看更多信息"
    if 类型 == "STAGE":
        return "满足对应阶段条件后查看"
    if 类型 == "PATCH":
        return "完成对应形态解锁条件后查看"
    return "解锁条件以原始资料为准"


def 档案区块数据(档案: dict[str, object], 干员名: str) -> tuple[str, str]:
    网页组: list[str] = []
    Markdown组: list[str] = []
    for 栏目 in 档案.get("剧情语音文本", []) or []:
        if not isinstance(栏目, dict):
            continue
        栏目名 = str(栏目.get("剧情标题") or "档案")
        网页故事: list[str] = []
        Markdown故事: list[str] = []
        for 故事 in 栏目.get("故事列表", []) or []:
            if not isinstance(故事, dict):
                continue
            标题 = 解锁提示(故事)
            正文 = 清理富文本(故事.get("剧情文本", ""), 干员名=干员名)
            if not 正文.strip():
                continue
            故事段落 = "".join("<p>" + (转义(行) if 行 else "&nbsp;") + "</p>" for 行 in 正文.splitlines())
            网页故事.append(f"<article class='档案正文'><div class='解锁标记'>{转义(标题)}</div>{故事段落}</article>")
            _, Markdown正文 = 文本段落(正文)
            Markdown故事.append(f"### {标题}\n\n{Markdown正文}")
        if 网页故事:
            网页组.append(f"<article class='档案栏目'><h3>{转义(栏目名)}</h3>{''.join(网页故事)}</article>")
            Markdown组.append(f"### {栏目名}\n\n" + "\n\n".join(Markdown故事))
    if 网页组:
        return "<div class='档案子标题'>人员档案</div>" + "".join(网页组), "### 人员档案\n\n" + "\n\n".join(Markdown组)
    return "", ""


def 属性数据(形态资料: dict[str, object], 干员名: str) -> tuple[str, str, str]:
    记录: list[tuple[str, str, dict[str, object]]] = []
    详细: list[str] = []
    详细Markdown: list[str] = []
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if not isinstance(基础, dict):
            continue
        形态名称 = str(基础.get("名称") or 干员名)
        职业名 = 显示值(基础.get("职业", ""), 干员名=干员名)
        形态标题 = f"{形态名称} · {职业名}" if 职业名 else 形态名称
        形态详细: list[str] = []
        形态详细Markdown: list[str] = []
        for 阶段序号, 阶段 in enumerate(基础.get("阶段资料", []) or []):
            if not isinstance(阶段, dict):
                continue
            阶段名 = 阶段显示.get(f"PHASE_{阶段序号}", str(阶段.get("阶段名称") or "阶段"))
            for 节点 in 阶段.get("属性成长节点", []) or []:
                if not isinstance(节点, dict):
                    continue
                数据 = 节点.get("数据", {})
                if isinstance(数据, dict):
                    记录.append((形态标题, 阶段名, {"等级": 节点.get("等级", ""), **数据}))
                    形态详细.append(递归网页(数据, 干员名))
                    形态详细Markdown.append(递归Markdown(数据, 干员名))
        if 形态详细:
            详细.append(f"<article class='资料卡'><h3>{转义(形态标题)}</h3>{''.join(形态详细)}</article>")
            详细Markdown.append(f"### {形态标题}\n\n" + "\n\n".join(形态详细Markdown))
    表头 = ["形态", "精英阶段", "等级", "生命上限", "攻击", "防御", "法术抗性", "部署费用", "阻挡数", "再部署时间", "攻击间隔"]
    键名 = ["阶段", "等级", "最大生命值", "攻击力", "防御力", "法术抗性", "部署费用", "阻挡数", "再部署时间", "基础攻击间隔"]
    行列表: list[str] = []
    Markdown行: list[str] = ["| " + " | ".join(表头) + " |", "| " + " | ".join(["---"] * len(表头)) + " |"]
    for 形态标题, 阶段名, 数据 in 记录:
        单行 = [形态标题, 阶段名]
        for 键 in 键名[1:]:
            单行.append(str(数据.get(键, "—")))
        行列表.append("<tr>" + "".join(f"<td>{转义(值)}</td>" for 值 in 单行) + "</tr>")
        Markdown行.append("| " + " | ".join(值.replace("|", "\\|") for 值 in 单行) + " |")
    主表 = "<div class='横向表格'><table><thead><tr>" + "".join(f"<th>{转义(值)}</th>" for 值 in 表头) + "</tr></thead><tbody>" + "".join(行列表) + "</tbody></table></div>"
    详情 = "<details class='补充数据'><summary>展开完整战斗数据</summary>" + "".join(详细) + "</details>" if 详细 else ""
    详情Markdown = "\n\n### 完整战斗数据\n\n" + "\n\n".join(详细Markdown) if 详细Markdown else ""
    return 主表, "\n".join(Markdown行) + 详情Markdown, 详情


def 攻击范围内容(形态资料: dict[str, object], 干员名: str) -> tuple[str, str]:
    网页: list[str] = []
    Markdown: list[str] = []
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if not isinstance(基础, dict):
            continue
        职业 = 显示值(基础.get("职业", ""), 干员名=干员名)
        标题 = f"{基础.get('名称') or 干员名} · {职业}" if 职业 else str(基础.get("名称") or 干员名)
        阶段网页: list[str] = []
        阶段Markdown: list[str] = []
        for 序号, 阶段 in enumerate(基础.get("阶段资料", []) or []):
            编号 = 阶段.get("攻击范围编号") if isinstance(阶段, dict) else None
            if not 编号:
                continue
            if 编号 not in 攻击范围表:
                raise ValueError(f"{干员名}：找不到攻击范围 {编号}")
            格子 = {(int(行), int(列)) for 行, 列 in 攻击范围表[编号]}
            格子.add((0, 0))
            最小行, 最大行 = min(行 for 行, _ in 格子), max(行 for 行, _ in 格子)
            最小列, 最大列 = min(列 for _, 列 in 格子), max(列 for _, 列 in 格子)
            阶段名 = 阶段显示.get(f"PHASE_{序号}", f"阶段{序号}")
            单格网页: list[str] = []
            单格Markdown: list[str] = []
            for 行 in range(最小行, 最大行 + 1):
                单行: list[str] = []
                for 列 in range(最小列, 最大列 + 1):
                    if (行, 列) == (0, 0):
                        样式, 符号 = "干员格", "干"
                    elif (行, 列) in 格子:
                        样式, 符号 = "攻击格", "■"
                    else:
                        样式, 符号 = "空白格", "·"
                    单格网页.append(f"<span class='{样式}'>{符号}</span>")
                    单行.append(符号)
                单格Markdown.append(" ".join(单行))
            网格 = f"<div class='范围网格' style='grid-template-columns:repeat({最大列 - 最小列 + 1}, 30px)' role='img' aria-label='{转义(阶段名)}攻击范围'>{''.join(单格网页)}</div>"
            阶段网页.append(f"<div class='范围阶段'><h4>{转义(阶段名)}</h4>{网格}</div>")
            阶段Markdown.append(f"#### {阶段名}\n\n```text\n" + "\n".join(单格Markdown) + "\n```")
        if 阶段网页:
            网页.append(f"<article class='形态卡'><h3>{转义(标题)}</h3><div class='范围阶段列表'>{''.join(阶段网页)}</div></article>")
            Markdown.append(f"### {标题}\n\n" + "\n\n".join(阶段Markdown))
    说明 = "干＝干员位置；■＝攻击范围；·＝范围外。图中右侧为干员朝向。"
    return f"<p class='范围图例'>{说明}</p>" + "".join(网页), 说明 + "\n\n" + "\n\n".join(Markdown)


def 技能内容(技能资料: dict[str, object], 干员名: str) -> tuple[str, str]:
    网页技能: list[str] = []
    Markdown技能: list[str] = []
    for 技能编号, 技能 in (技能资料 or {}).items():
        if not isinstance(技能, dict) or 技能.get("隐藏"):
            continue
        等级资料 = 技能.get("多等级资料", []) or []
        if not 等级资料:
            continue
        技能名 = str(等级资料[0].get("名称") or "技能")
        行列表: list[str] = []
        Markdown表: list[str] = ["| 等级 | 触发方式 | 初始 | 消耗 | 持续 | 技能描述 |", "| --- | --- | ---: | ---: | ---: | --- |"]
        for 序号, 等级 in enumerate(等级资料, start=1):
            if not isinstance(等级, dict):
                continue
            等级名 = str(序号 if 序号 <= 7 else ["专精一", "专精二", "专精三"][min(序号 - 8, 2)])
            技力 = 等级.get("技力数据", {}) if isinstance(等级.get("技力数据"), dict) else {}
            参数 = 收集参数(等级)
            if 等级.get("时长") is not None:
                参数.setdefault("duration", 等级["时长"])
            描述 = 清理富文本(等级.get("描述", ""), 参数, 干员名)
            技能类型 = 显示值(等级.get("技能类型", ""), 参数, 干员名)
            初始 = 技力.get("初始技力", "—")
            消耗 = 技力.get("技力消耗", "—")
            持续 = 等级.get("时长", "—")
            if 持续 in (None, 0, 0.0):
                持续 = "—"
            行列表.append("<tr>" + "".join(f"<td>{转义(值)}</td>" for 值 in [等级名, 技能类型, 初始, 消耗, 持续]) + f"<td class='技能说明'>{转义(描述)}</td></tr>")
            Markdown表.append("| " + " | ".join(str(值).replace("|", "\\|").replace("\n", "<br>") for 值 in [等级名, 技能类型, 初始, 消耗, 持续, 描述]) + " |")
        网页技能.append(f"<article class='资料卡'><h3>{转义(技能名)}</h3><div class='横向表格'><table><thead><tr><th>等级</th><th>触发方式</th><th>初始</th><th>消耗</th><th>持续</th><th>技能描述</th></tr></thead><tbody>{''.join(行列表)}</tbody></table></div></article>")
        Markdown技能.append(f"### {技能名}\n\n" + "\n".join(Markdown表))
    return "".join(网页技能), "\n\n".join(Markdown技能)


def 材料清单(材料: object) -> tuple[str, str]:
    if not isinstance(材料, list):
        return "", ""
    网页: list[str] = []
    文字: list[str] = []
    for 项 in 材料:
        if not isinstance(项, dict):
            continue
        编号 = str(项.get("编号") or "")
        名称 = 物品名称表.get(编号)
        if not 名称:
            raise ValueError(f"找不到材料的中文名称：{编号}")
        数量 = 项.get("计数", "")
        网页.append(f"<span class='材料项'>{转义(名称)} <strong>×{转义(数量)}</strong></span>")
        文字.append(f"{名称}×{数量}")
    return "".join(网页), "、".join(文字)


def 模组材料内容(消耗: dict[str, object]) -> tuple[str, str]:
    网页: list[str] = []
    文字: list[str] = []
    for 等级, 材料 in sorted(消耗.items(), key=lambda item: int(item[0])):
        材料网页, 材料文字 = 材料清单(材料)
        if not 材料文字:
            continue
        网页.append(f"<div class='模组材料级'><strong>第{转义(等级)}级</strong>{材料网页}</div>")
        文字.append(f"- **第{等级}级：** {材料文字}")
    return "".join(网页), "\n".join(文字)


def 培养材料内容(干员: dict[str, object], 形态资料: dict[str, object]) -> tuple[str, str]:
    网页卡: list[str] = []
    Markdown卡: list[str] = []
    已见通用升级: set[str] = set()
    技能资料 = 干员.get("技能资料", {}) or {}
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if not isinstance(基础, dict):
            continue
        形态名 = str(基础.get("名称") or 干员.get("干员名称") or "干员")
        职业 = 显示值(基础.get("职业", ""))
        标题前缀 = f"{形态名} · {职业}" if len(形态资料) > 1 else ""
        def 添加(标题: str, 行: list[tuple[str, object]]) -> None:
            网页行: list[str] = []
            文本行: list[str] = []
            for 等级, 消耗 in 行:
                材料网页, 材料文字 = 材料清单(消耗)
                if 材料网页:
                    网页行.append(f"<div class='材料行'><span class='材料等级'>{转义(等级)}</span><div class='材料列表'>{材料网页}</div></div>")
                    文本行.append(f"- **{等级}：** {材料文字}")
            if 网页行:
                完整标题 = f"{标题前缀} · {标题}" if 标题前缀 else 标题
                网页卡.append(f"<article class='资料卡'><h3>{转义(完整标题)}</h3>{''.join(网页行)}</article>")
                Markdown卡.append(f"### {完整标题}\n\n" + "\n".join(文本行))
        精英化 = []
        for 序号, 阶段 in enumerate(基础.get("阶段资料", []) or []):
            if 序号 and isinstance(阶段, dict):
                精英化.append((f"精英{序号}", 阶段.get("精英化消耗材料")))
        添加("精英化材料", 精英化)
        通用 = 基础.get("全部技能升级资料")
        if isinstance(通用, list):
            指纹 = json.dumps(通用, ensure_ascii=False, sort_keys=True)
            if 指纹 not in 已见通用升级:
                已见通用升级.add(指纹)
                添加("技能升级材料", [(f"{序号}级", 项.get("等级升级消耗项")) for 序号, 项 in enumerate(通用, start=2) if isinstance(项, dict)])
        for 技能 in 基础.get("技能列表", []) or []:
            if not isinstance(技能, dict):
                continue
            技能编号 = 技能.get("技能编号")
            技能详情 = 技能资料.get(技能编号, {}) if isinstance(技能资料, dict) else {}
            等级详情 = 技能详情.get("多等级资料", []) if isinstance(技能详情, dict) else []
            技能名 = str(等级详情[0].get("名称") or "技能") if 等级详情 else "技能"
            专精 = 技能.get("等级提升消耗条件")
            if isinstance(专精, list):
                添加(f"{技能名} · 专精材料", [(f"专精{序号}", 项.get("等级提升消耗")) for 序号, 项 in enumerate(专精, start=1) if isinstance(项, dict)])
    return "".join(网页卡), "\n\n".join(Markdown卡)


def 语音内容(语音列表: list[object], 干员名: str, 追加: bool = False) -> tuple[str, str]:
    网页: list[str] = []
    Markdown: list[str] = []
    for 语音 in 语音列表 or []:
        if not isinstance(语音, dict):
            continue
        标题 = str(语音.get("语音标题") or "语音")
        台词 = 清理富文本(语音.get("语音台词", ""), 干员名=干员名)
        if not 台词.strip():
            continue
        解锁 = str(语音.get("未解锁说明") or "").strip()
        限定标记 = f"<span class='解锁标记'>{转义(解锁)}</span>" if 解锁 else ""
        网页.append(f"<article class='语音卡'><div class='语音标题'>{转义(标题)}{限定标记}</div><blockquote>{转义(台词)}</blockquote></article>")
        Markdown.append(f"### {标题}\n\n{'> ' + 解锁 + chr(10) + chr(10) if 解锁 else ''}> {台词.replace(chr(10), chr(10) + '> ')}")
    return "".join(网页), "\n\n".join(Markdown)


def 多语种语音内容(干员: dict[str, object], 干员名: str) -> tuple[str, str]:
    中文标题 = {str(项.get("干员语音条目编号")): str(项.get("语音标题") or "语音")
            for 字段 in ("语音台词", "追加语音台词") for 项 in (干员.get(字段) or []) if isinstance(项, dict)}
    形态编号 = set(干员.get("形态资料", {}))
    网页语种: list[str] = []
    Markdown语种: list[str] = []
    for 语种, 索引 in 干员语音索引.items():
        条目: list[tuple[str, str]] = []
        已匹配 = 0
        for 编号 in 形态编号:
            for 键, 台词, 原标题 in 索引.get(编号, []):
                正文 = 清理富文本(台词, 干员名=干员名)
                if 正文.strip():
                    if 键 in 中文标题:
                        已匹配 += 1
                    标题 = 中文标题.get(键) or (f"补充语音（{原标题}）" if 原标题 else "补充语音")
                    条目.append((标题, 正文))
        if not 条目:
            提示 = "来源数据未提供该语种台词。"
            网页语种.append(f"<details class='补充数据 语种折叠'><summary>{转义(语种)} · 暂无台词</summary><p class='语音缺项'>{提示}</p></details>")
            Markdown语种.append(f"### {语种}\n\n{提示}")
            continue
        说明 = f"来源收录 {len(条目)} 条台词，其中 {已匹配} 条与中文语音标题对应。"
        网页条目 = "".join(f"<article class='语音卡'><div class='语音标题'>{转义(标题)}</div><blockquote>{转义(台词)}</blockquote></article>" for 标题, 台词 in 条目)
        网页语种.append(f"<details class='补充数据 语种折叠'><summary>{转义(语种)} · {len(条目)} 条</summary><div class='语种内容'><p class='语音缺项'>{说明}</p>{网页条目}</div></details>")
        Markdown语种.append(f"### {语种}（{len(条目)} 条）\n\n{说明}\n\n" + "\n\n".join(f"**{标题}**\n\n> {台词.replace(chr(10), chr(10) + '> ')}" for 标题, 台词 in 条目))
    return "".join(网页语种), "\n\n".join(Markdown语种)


def 基本资料区块(干员: dict[str, object], 干员名: str, 形态资料: dict[str, object]) -> tuple[str, str]:
    标签: list[str] = []
    主要势力: list[str] = []
    其他势力: list[str] = []
    招募标签: list[str] = []
    简介: list[str] = []
    Markdown简介: list[str] = []
    已见简介: set[tuple[str, str]] = set()
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if not isinstance(基础, dict):
            continue
        职业 = 显示值(基础.get("职业", ""), 干员名=干员名)
        星级 = 干员星级(基础.get("稀有度", ""))
        部署位置 = 显示值(基础.get("部署位置", ""), 干员名=干员名)
        标签.extend([值 for 值 in [星级, 职业, 部署位置] if 值 and 值 not in 标签])
        for 名称 in 所属势力名称(基础.get("主要所属势力")):
            if 名称 not in 主要势力:
                主要势力.append(名称)
        for 来源 in 基础.get("其他所属势力") or []:
            for 名称 in 所属势力名称(来源):
                if 名称 not in 其他势力:
                    其他势力.append(名称)
        for 名称 in 基础.get("标签列表", []) or []:
            if isinstance(名称, str) and 名称 not in 招募标签:
                招募标签.append(名称)
        for 字段 in ["物品用途说明", "物品描述"]:
            内容 = 基础.get(字段)
            if isinstance(内容, str) and 内容.strip():
                展示字段 = 显示标签(字段)
                if (展示字段, 内容) in 已见简介:
                    continue
                已见简介.add((展示字段, 内容))
                网页, md = 文本段落(清理富文本(内容, 干员名=干员名))
                简介.append(f"<div class='简介项'><h3>{转义(展示字段)}</h3>{网页}</div>")
                Markdown简介.append(f"### {展示字段}\n\n{md}")
    标签HTML = "".join(f"<span class='标签'>{转义(值)}</span>" for 值 in 标签)
    势力HTML = f"<div class='资料行'><dt>所属势力</dt><dd>{转义('、'.join(主要势力) if 主要势力 else '来源未提供')}</dd></div>"
    其他势力HTML = f"<div class='资料行'><dt>其他所属势力</dt><dd>{转义('、'.join(其他势力))}</dd></div>" if 其他势力 else ""
    招募HTML = f"<div class='资料行'><dt>标签</dt><dd>{转义('、'.join(招募标签))}</dd></div>" if 招募标签 else ""
    网页 = f"<div class='简介卡'><div class='标签行'>{标签HTML}</div><dl>{势力HTML}{其他势力HTML}{招募HTML}</dl>{''.join(简介)}</div>"
    Markdown内容 = "\n".join(f"- **{标题}：** {内容}" for 标题, 内容 in [("星级、职业、部署位置", "、".join(标签)), ("所属势力", "、".join(主要势力) if 主要势力 else "来源未提供"), ("其他所属势力", "、".join(其他势力)), ("标签", "、".join(招募标签))] if 内容)
    Markdown内容 += "\n\n" + ("\n\n".join(Markdown简介) if Markdown简介 else "未提供简介文字。")
    return 网页, Markdown内容


def 清洁文件名(名称: str) -> str:
    名称 = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", 名称).strip(" .")
    名称 = re.sub(r"\s+", "_", 名称)
    return 名称 or "未命名档案"


def 生成文件名(原名: str, 已用: Counter[str]) -> str:
    基名 = 清洁文件名(原名)
    已用[基名] += 1
    return 基名 if 已用[基名] == 1 else f"{基名}_{已用[基名]}"


def 文档模板(标题: str, 正文: str, 样式路径: str, 首页路径: str, 干员名: str) -> str:
    导航项 = re.findall(r"<section class='档案区块' id='([^']+)'><div class='区块题头'><span>[^<]*</span><h2>([^<]+)</h2>", 正文)
    页内目录 = "".join(f"<a href='#{转义(锚点)}'>{转义(名称)}</a>" for 锚点, 名称 in 导航项)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{转义(标题)}｜明日方舟干员档案</title>
  <link rel="stylesheet" href="{转义(样式路径)}">
</head>
<body class="档案页面">
  <header class="页眉"><a class="返回首页" href="{转义(首页路径)}">返回档案索引</a><span>罗德岛资料终端 / 干员档案</span></header>
  <main class="档案主栏">
    <div class="页面标题"><div class="眉题">干员资料 · 档案记录</div><h1>{转义(标题)}</h1><p>档案文字按中文服资料原文呈现；专名保持来源写法。</p></div>
    <nav class="页内目录" aria-label="档案栏目导航">{页内目录}</nav>
    {正文}
    <footer class="页脚"><span>档案对象：{转义(干员名)}</span><span>本地离线页面 · 无外部图片或在线请求</span></footer>
  </main>
</body>
</html>
"""


def 生成干员页面(干员: dict[str, object], 页面名: str) -> tuple[str, str, dict[str, str]]:
    干员名 = str(干员.get("干员名称") or 页面名)
    形态资料 = 干员.get("形态资料", {})
    网页区块: list[str] = []
    Markdown区块: list[str] = [f"# {干员名}\n\n> 明日方舟干员档案 · 中文服资料展示"]

    网页, Markdown = 基本资料区块(干员, 干员名, 形态资料)
    h, m = 区块("干员信息", 网页, Markdown, "干员信息")
    网页区块.append(h); Markdown区块.append(m)

    特性网页: list[str] = []
    特性Markdown: list[str] = []
    for 形态编号, 形态 in (形态资料 or {}).items():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if not isinstance(基础, dict):
            continue
        分支编号 = str(基础.get("职业分支编号") or "")
        分支名称 = 职业分支名称表.get(分支编号)
        if 分支编号 and not 分支名称:
            raise ValueError(f"{干员名}：找不到职业分支 {分支编号}")
        职业 = 显示值(基础.get("职业", ""), 干员名=干员名)
        标题 = f"{基础.get('名称') or 干员名} · {职业}" if 职业 else str(基础.get("名称") or 干员名)
        描述 = 清理富文本(基础.get("描述", ""), 收集参数(基础.get("特性")), 干员名)
        主文网页 = f"<p>{转义(描述)}</p>" if 描述 else "<p>来源未提供特性描述。</p>"
        主文Markdown = 描述 or "来源未提供特性描述。"
        分支网页 = f"<p class='分支名称'><strong>职业分支：</strong>{转义(分支名称)}</p>" if 分支名称 else ""
        分支Markdown = f"**职业分支：** {分支名称}\n\n" if 分支名称 else ""
        额外网页 = 递归网页(基础.get("特性"), 干员名) if 基础.get("特性") else ""
        额外Markdown = "\n\n" + 递归Markdown(基础.get("特性"), 干员名) if 基础.get("特性") else ""
        特性网页.append(f"<article class='形态卡'><h3>{转义(标题)}</h3>{分支网页}{主文网页}{额外网页}</article>")
        特性Markdown.append(f"### {标题}\n\n{分支Markdown}{主文Markdown}{额外Markdown}")
    h, m = 区块("特性", "".join(特性网页), "\n\n".join(特性Markdown), "特性")
    网页区块.append(h); Markdown区块.append(m)

    获得网页: list[str] = []
    获得Markdown: list[str] = []
    上线信息 = 上线获得表.get(干员名)
    if not 上线信息:
        raise ValueError(f"{干员名}：缺少上线与获得方式资料")
    for 标题 in ("主要获得方式", "国服上线时间", "国服上线途径", "关联活动"):
        内容 = 上线信息.get(标题)
        if 内容:
            获得网页.append(f"<div class='资料行'><dt>{标题}</dt><dd>{转义(内容)}</dd></div>")
            获得Markdown.append(f"- **{标题}：** {内容}")
    for 形态名称, 信息 in 上线信息.get("形态上线", {}).items():
        for 标题 in ("国服上线时间", "国服上线途径", "主要获得方式", "关联活动"):
            内容 = 信息.get(标题)
            if 内容:
                完整标题 = f"{形态名称}形态 · {标题}"
                获得网页.append(f"<div class='资料行'><dt>{转义(完整标题)}</dt><dd>{转义(内容)}</dd></div>")
                获得Markdown.append(f"- **{完整标题}：** {内容}")
    已见获得: set[str] = set()
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        获取方式 = 基础.get("物品获取方式") if isinstance(基础, dict) else None
        if isinstance(获取方式, str) and 获取方式.strip() and 获取方式 not in 已见获得:
            已见获得.add(获取方式)
            获得网页.append(f"<div class='资料行'><dt>游戏内获取说明</dt><dd>{转义(清理富文本(获取方式, 干员名=干员名))}</dd></div>")
            _, 获取Markdown = 文本段落(清理富文本(获取方式, 干员名=干员名))
            获得Markdown.append(f"- **游戏内获取说明：** {获取Markdown}")
    h, m = 区块("获得方式", "<dl class='获得资料'>" + "".join(获得网页) + "</dl>", "\n".join(获得Markdown), "获得方式")
    网页区块.append(h); Markdown区块.append(m)

    属性网页, 属性Markdown, 属性详情 = 属性数据(形态资料, 干员名)
    h, m = 区块("属性", 属性网页 + 属性详情, 属性Markdown, "属性", "数值按精英阶段和等级列出；完整战斗参数可展开查看。")
    网页区块.append(h); Markdown区块.append(m)

    范围网页, 范围Markdown = 攻击范围内容(形态资料, 干员名)
    h, m = 区块("攻击范围", 范围网页, 范围Markdown, "攻击范围")
    网页区块.append(h); Markdown区块.append(m)

    天赋网页: list[str] = []
    天赋Markdown: list[str] = []
    潜能网页: list[str] = []
    潜能Markdown: list[str] = []
    基建网页: list[str] = []
    基建Markdown: list[str] = []
    for 形态 in (形态资料 or {}).values():
        if not isinstance(形态, dict):
            continue
        基础 = 形态.get("干员基础数据", {})
        if isinstance(基础, dict):
            if 基础.get("天赋列表"):
                天赋网页.append(递归网页(基础["天赋列表"], 干员名))
                天赋Markdown.append(递归Markdown(基础["天赋列表"], 干员名))
            if 基础.get("潜能提升资料"):
                潜能网页.append(递归网页(基础["潜能提升资料"], 干员名))
                潜能Markdown.append(递归Markdown(基础["潜能提升资料"], 干员名))
            if 基础.get("信赖成长节点"):
                潜能网页.append(f"<div class='嵌套字段'><h4>信赖加成</h4>{递归网页(基础['信赖成长节点'], 干员名)}</div>")
                潜能Markdown.append(f"**信赖加成**\n\n{递归Markdown(基础['信赖成长节点'], 干员名)}")
        if 形态.get("基建技能"):
            基建网页.append(递归网页(形态["基建技能"], 干员名))
            基建Markdown.append(递归Markdown(形态["基建技能"], 干员名))
    h, m = 区块("天赋", "".join(天赋网页), "\n\n".join(天赋Markdown), "天赋")
    网页区块.append(h); Markdown区块.append(m)
    h, m = 区块("潜能提升", "".join(潜能网页), "\n\n".join(潜能Markdown), "潜能提升")
    网页区块.append(h); Markdown区块.append(m)

    技能网页, 技能Markdown = 技能内容(干员.get("技能资料", {}), 干员名)
    h, m = 区块("技能", 技能网页, 技能Markdown, "技能")
    网页区块.append(h); Markdown区块.append(m)
    材料网页, 材料Markdown = 培养材料内容(干员, 形态资料)
    h, m = 区块("培养材料", 材料网页, 材料Markdown, "培养材料")
    网页区块.append(h); Markdown区块.append(m)
    h, m = 区块("基建技能", "".join(基建网页), "\n\n".join(基建Markdown), "基建技能")
    网页区块.append(h); Markdown区块.append(m)

    档案网页, 档案Markdown = 档案区块数据(干员.get("干员档案", {}), 干员名)
    h, m = 区块("干员档案", 档案网页, 档案Markdown, "干员档案")
    网页区块.append(h); Markdown区块.append(m)

    语音网页, 语音Markdown = 语音内容(干员.get("语音台词", []), 干员名)
    h, m = 区块("台词", 语音网页, 语音Markdown, "台词")
    网页区块.append(h); Markdown区块.append(m)
    追加网页, 追加Markdown = 语音内容(干员.get("追加语音台词", []), 干员名, True)
    h, m = 区块("追加台词", 追加网页, 追加Markdown, "追加台词")
    网页区块.append(h); Markdown区块.append(m)
    外语网页, 外语Markdown = 多语种语音内容(干员, 干员名)
    h, m = 区块("多语种台词", 外语网页, 外语Markdown, "多语种台词", "保留各语言版本的原文台词；项目标题优先采用中文服名称。")
    网页区块.append(h); Markdown区块.append(m)

    个人网页: list[str] = []
    个人Markdown: list[str] = []
    for 记录 in 干员.get("干员个人记录", []) or []:
        if not isinstance(记录, dict):
            continue
        名称 = str(记录.get("记录集名称") or "个人记录")
        简介 = str((记录.get("剧情索引") or {}).get("剧情简介") or "")
        脚本 = 清理富文本(记录.get("剧情脚本") or "", 干员名=干员名)
        if not 脚本.strip() and not 简介.strip():
            continue
        简介HTML, 简介MD = 文本段落(简介) if 简介 else ("", "")
        脚本HTML = "".join(f"<p>{转义(行) if 行 else '&nbsp;'}</p>" for 行 in 脚本.splitlines())
        简介HTML块 = "<div class='剧情简介'>" + 简介HTML + "</div>" if 简介HTML else ""
        个人网页.append(f"<article class='档案正文'><h3>{转义(名称)}</h3>{简介HTML块}<details class='剧情全文' open><summary>查看完整个人记录</summary><div class='对白正文'>{脚本HTML}</div></details></article>")
        个人Markdown.append(f"### {名称}\n\n{f'**剧情简介**\n\n{简介MD}\n\n' if 简介MD else ''}**完整记录**\n\n{'> ' + 脚本.replace(chr(10), chr(10) + '> ') if 脚本 else '原始资料未提供全文。'}")
    h, m = 区块("个人记录", "".join(个人网页), "\n\n".join(个人Markdown), "个人记录")
    网页区块.append(h); Markdown区块.append(m)

    for 字段, 标题 in [
        ("服装资料", "服装资料"),
        ("模组资料", "模组资料"),
        ("召唤物资料", "召唤物资料"),
        ("集成战略特设数据", "集成战略资料"),
        ("集成战略培养数据", "集成战略培养资料"),
    ]:
        值 = 干员.get(字段)
        内容网页 = 递归网页(值, 干员名)
        内容Markdown = 递归Markdown(值, 干员名)
        h, m = 区块(标题, 内容网页, 内容Markdown, 标题)
        网页区块.append(h); Markdown区块.append(m)

    页面正文 = "".join(项 for 项 in 网页区块 if 项)
    Markdown正文 = "\n\n".join(项 for 项 in Markdown区块 if 项)
    元信息 = {
        "名称": 干员名,
        "职业": "",
        "星级": "",
        "标签": "",
    }
    搜索词: list[str] = []
    for 形态 in (形态资料 or {}).values():
        if isinstance(形态, dict) and isinstance(形态.get("干员基础数据"), dict):
            基础 = 形态["干员基础数据"]
            职业 = 显示值(基础.get("职业", ""), 干员名=干员名)
            if not 元信息["职业"]:
                元信息["职业"] = 职业
                元信息["星级"] = 干员星级(基础.get("稀有度", ""))
            搜索词.extend([职业, *[str(项) for 项 in 基础.get("标签列表", []) or []]])
    元信息["标签"] = " ".join(dict.fromkeys(搜索词))
    return 页面正文, Markdown正文, 元信息


def 生成非干员页面(档案: dict[str, object], 页面名: str) -> tuple[str, str]:
    干员名 = str(档案.get("档案姓名") or 页面名)
    网页, Markdown = 档案区块数据(档案, 干员名)
    正文 = f"<section class='档案区块' id='档案资料'><div class='区块题头'><span>人物档案</span><h2>档案资料</h2></div>{网页}</section>"
    md = f"# {干员名}\n\n> 非干员人物档案\n\n## 档案资料\n\n{Markdown}"
    return 正文, md


def 写入网页(路径: Path, 标题: str, 正文: str, 样式路径: str, 首页路径: str, 对象名: str) -> None:
    页面 = 文档模板(标题, 正文, 样式路径, 首页路径, 对象名)
    页面 = "\n".join(行.rstrip() for 行 in 页面.split("\n"))
    for 尝试 in range(5):
        try:
            路径.write_text(页面, encoding="utf-8")
            return
        except OSError as 错误:
            if 错误.errno != 22 or 尝试 == 4:
                raise
            time.sleep(0.1 * (尝试 + 1))


def 提取检索栏目(正文: str, 标题: str) -> str:
    匹配 = re.search(rf"(?ms)^## {re.escape(标题)}\n(.*?)(?=^## |\Z)", 正文)
    if not 匹配:
        return ""
    内容 = html.unescape(匹配.group(1))
    内容 = re.sub(r"<br\s*/?>", " ", 内容)
    内容 = re.sub(r"[#*|`>]+", " ", 内容)
    return " ".join(内容.split())


def 建立干员检索内容(干员: dict[str, object], 正文: str, 干员名: str) -> list[str]:
    技能 = 提取检索栏目(正文, "技能")
    天赋 = 提取检索栏目(正文, "天赋")
    档案 = " ".join(项 for 项 in [提取检索栏目(正文, "干员档案"), 提取检索栏目(正文, "个人记录")] if 项)
    台词: list[str] = []
    for 字段 in ("语音台词", "追加语音台词"):
        for 条目 in 干员.get(字段, []) or []:
            if isinstance(条目, dict):
                文本 = 清理富文本(条目.get("语音台词", ""), 干员名=干员名)
                if 文本:
                    台词.append(文本)
    for 语种索引 in 干员语音索引.values():
        for 编号 in 干员.get("形态资料", {}):
            for _, 原文, _ in 语种索引.get(编号, []):
                文本 = 清理富文本(原文, 干员名=干员名)
                if 文本:
                    台词.append(文本)
    return [技能, " ".join(台词), 档案, 天赋]


def 生成首页(干员条目: list[dict[str, str]], 非干员条目: list[dict[str, str]], 统计: dict[str, int]) -> str:
    类别: dict[str, list[dict[str, str]]] = defaultdict(list)
    for 条目 in 干员条目:
        类别[条目.get("职业") or "其他"].append(条目)
    列表: list[str] = []
    for 职业 in 职业顺序 + [项 for 项 in 类别 if 项 not in 职业顺序]:
        条目组 = 类别.get(职业, [])
        if not 条目组:
            continue
        卡片 = []
        for 条目 in 条目组:
            href = quote("干员档案/" + 条目["文件"], safe="/")
            搜索词 = " ".join([条目["名称"], 条目.get("职业", ""), 条目.get("星级", ""), 条目.get("标签", "")])
            卡片.append(f"<a class='干员条目' data-search='{转义(搜索词).lower()}' data-key='{转义('干员档案/' + 条目['文件'])}' href='{转义(href)}'><span class='干员名'>{转义(条目['名称'])}</span><span class='干员副题'>{转义(条目.get('星级', ''))} · {转义(职业)}</span><span class='匹配提示' hidden></span></a>")
        列表.append(f"<section class='职业组'><h2>{转义(职业)}<span>{len(条目组)} 名</span></h2><div class='干员网格'>{''.join(卡片)}</div></section>")
    非干员HTML = ""
    if 非干员条目:
        项 = []
        for 条目 in 非干员条目:
            href = quote("非干员档案/" + 条目["文件"], safe="/")
            项.append(f"<a class='干员条目' data-search='{转义(条目['名称']).lower()}' data-key='{转义('非干员档案/' + 条目['文件'])}' href='{转义(href)}'><span class='干员名'>{转义(条目['名称'])}</span><span class='干员副题'>人物档案</span><span class='匹配提示' hidden></span></a>")
        非干员HTML = f"<section class='职业组'><h2>非干员档案<span>{len(项)} 份</span></h2><div class='干员网格'>{''.join(项)}</div></section>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>明日方舟干员档案展示版</title>
  <link rel="stylesheet" href="档案样式.css">
  <script src="检索索引.js" defer></script>
  <script src="检索功能.js" defer></script>
</head>
<body class="索引页面">
  <header class="索引页眉">
    <div class="终端标志">罗德岛 <span>资料终端</span></div>
    <div class="页眉说明">明日方舟 · 中文服干员资料</div>
  </header>
  <main class="索引主栏">
    <section class="索引介绍">
      <div class="眉题">资料终端 / 干员档案</div>
      <h1>档案索引</h1>
      <p>按玩家可读栏目整理干员资料。档案、台词、剧情和专名保留中文服源文；属性标签使用玩家熟悉的展示用语。</p>
      <div class="索引统计"><strong>{len(干员条目)}</strong><span>名干员</span><i></i><strong>{len(非干员条目)}</strong><span>份人物档案</span></div>
      <div class="索引补充统计">收录 {统计['语音条数']:,} 条台词、{统计['追加语音条数']:,} 条追加台词、{统计['个人记录篇数']:,} 篇个人记录</div>
      <label class="检索框"><span>检索干员</span><input id="档案检索" type="search" placeholder="输入代号、技能、台词、档案或天赋关键词" autocomplete="off"><span id="检索结果" aria-live="polite">{len(干员条目) + len(非干员条目)} 条档案</span></label>
    </section>
    <div id="档案列表">{''.join(列表)}{非干员HTML}</div>
    <footer class="页脚"><span>离线静态资料 · 无需网络</span><a href="使用说明.md">打开使用说明</a></footer>
  </main>
</body>
</html>
"""


def 主程序() -> None:
    global 物品名称表, 势力名称表, 多语种语音表, 干员语音索引, 职业分支名称表, 攻击范围表, 上线获得表
    if not 资料文件.exists():
        raise SystemExit(f"找不到资料文件：{资料文件}")
    for 名称 in ("物品名称.json", "多语种语音.json", "职业分支名称.json", "攻击范围.json", "上线与获得方式.json"):
        if not (映射目录 / 名称).exists():
            raise SystemExit(f"缺少展示映射：{映射目录 / 名称}。请先运行 准备展示映射.py。")
    物品名称表 = json.loads((映射目录 / "物品名称.json").read_text(encoding="utf-8"))
    多语种语音表 = json.loads((映射目录 / "多语种语音.json").read_text(encoding="utf-8"))
    职业分支名称表 = json.loads((映射目录 / "职业分支名称.json").read_text(encoding="utf-8"))
    攻击范围表 = json.loads((映射目录 / "攻击范围.json").read_text(encoding="utf-8"))
    上线获得表 = json.loads((映射目录 / "上线与获得方式.json").read_text(encoding="utf-8"))["干员"]
    势力源 = json.loads(势力文件.read_text(encoding="utf-8"))
    势力名称表 = {str(项["势力编号"]): str(项["势力名称"]) for 项 in 势力源.values() if isinstance(项, dict) and 项.get("势力编号") and 项.get("势力名称")}
    干员语音索引 = {}
    for 语种, 条目 in 多语种语音表.items():
        按干员: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for 键, 内容 in 条目.items():
            按干员[内容[0]].append((键, 内容[1], 内容[2]))
        if "char_002_amiya" in 按干员:
            if "char_1001_amiya2" not in 按干员:
                按干员["char_1001_amiya2"] = 按干员["char_002_amiya"]
            if "char_1037_amiya3" not in 按干员:
                按干员["char_1037_amiya3"] = 按干员["char_002_amiya"]
        干员语音索引[语种] = 按干员
    for 目录项 in [干员页目录, 非干员页目录, Markdown目录]:
        目录项.mkdir(parents=True, exist_ok=True)
    with 资料文件.open("r", encoding="utf-8") as 文件:
        数据 = json.load(文件)

    # 规范化：将阿米娅的三种形态彻底拆分为三个独立干员展示
    干员字典 = 数据.get("干员", {})
    if "char_002_amiya" in 干员字典:
        术师 = 干员字典["char_002_amiya"]
        近卫 = 干员字典.get("char_1001_amiya2")
        医疗 = 干员字典.get("char_1037_amiya3")
        模组池 = 术师.get("模组资料", []) or []

        # 术师专属模组（DWDB-221E 与 阿米娅证章）
        术师["模组资料"] = [m for m in 模组池 if (m.get("模组资料") or {}).get("模组编号") in {"uniequip_001_amiya", "uniequip_002_amiya"}]

        # 近卫专属模组（待调弦的怒火 与 阿米娅证章（近卫））
        if 近卫:
            近卫["模组资料"] = [m for m in 模组池 if (m.get("模组资料") or {}).get("模组编号") in {"uniequip_001_amiya2", "uniequip_002_amiya2"}]
            if not 近卫.get("语音台词") and 术师.get("语音台词"):
                近卫["语音台词"] = 术师["语音台词"]
                近卫["追加语音台词"] = 术师.get("追加语音台词", [])
            术师形态 = 术师.get("形态资料", {}).get("char_002_amiya", {})
            近卫形态 = 近卫.get("形态资料", {}).get("char_1001_amiya2", {})
            if 术师形态.get("基建技能") and not 近卫形态.get("基建技能"):
                近卫形态["基建技能"] = 术师形态["基建技能"]

        # 医疗专属模组（带有灼痕的裙子 与 阿米娅证章（医疗））
        if 医疗:
            医疗["模组资料"] = [m for m in 模组池 if (m.get("模组资料") or {}).get("模组编号") in {"uniequip_001_amiya3", "uniequip_002_amiya3"}]
            if not 医疗.get("语音台词") and 术师.get("语音台词"):
                医疗["语音台词"] = 术师["语音台词"]
                医疗["追加语音台词"] = 术师.get("追加语音台词", [])
            术师形态 = 术师.get("形态资料", {}).get("char_002_amiya", {})
            医疗形态 = 医疗.get("形态资料", {}).get("char_1037_amiya3", {})
            if 术师形态.get("基建技能") and not 医疗形态.get("基建技能"):
                医疗形态["基建技能"] = 术师形态["基建技能"]

    干员清单: list[dict[str, str]] = []
    检索索引: dict[str, list[str]] = {}
    Markdown已用: Counter[str] = Counter()
    HTML已用: Counter[str] = Counter()
    for 干员 in 数据.get("干员", {}).values():
        if not isinstance(干员, dict):
            continue
        干员名 = str(干员.get("干员名称") or "未命名干员")
        文件名 = 生成文件名(干员名, HTML已用)
        Markdown名 = 生成文件名(干员名, Markdown已用)
        网页正文, Markdown正文, 元信息 = 生成干员页面(干员, 干员名)
        写入网页(干员页目录 / f"{文件名}.html", 干员名, 网页正文, "../档案样式.css", "../首页.html", 干员名)
        (Markdown目录 / f"{Markdown名}.md").write_text(Markdown正文 + "\n", encoding="utf-8")
        干员清单.append({**元信息, "文件": f"{文件名}.html"})
        检索索引[f"干员档案/{文件名}.html"] = 建立干员检索内容(干员, Markdown正文, 干员名)

    非干员清单: list[dict[str, str]] = []
    非干员已用: Counter[str] = Counter()
    for 序号, (档案编号, 档案) in enumerate(数据.get("非干员档案", {}).items(), start=1):
        if not isinstance(档案, dict):
            continue
        原名 = str(档案.get("档案姓名") or "")
        展示名 = 原名 if 原名 and 原名 != "Unknown" else f"未公开人物档案{序号:02d}"
        文件名 = 生成文件名(展示名, 非干员已用)
        网页正文, Markdown正文 = 生成非干员页面(档案, 展示名)
        写入网页(非干员页目录 / f"{文件名}.html", 展示名, 网页正文, "../档案样式.css", "../首页.html", 展示名)
        (Markdown目录 / f"非干员档案_{文件名}.md").write_text(Markdown正文 + "\n", encoding="utf-8")
        非干员清单.append({"名称": 展示名, "文件": f"{文件名}.html"})
        检索索引[f"非干员档案/{文件名}.html"] = ["", "", " ".join(Markdown正文.split()), ""]

    统计 = {
        "语音条数": sum(len(干员.get("语音台词", []) or []) for 干员 in 数据.get("干员", {}).values()),
        "追加语音条数": sum(len(干员.get("追加语音台词", []) or []) for 干员 in 数据.get("干员", {}).values()),
        "个人记录篇数": sum(len(干员.get("干员个人记录", []) or []) for 干员 in 数据.get("干员", {}).values()),
    }
    索引脚本 = "window.档案检索索引 = " + json.dumps(检索索引, ensure_ascii=False, separators=(",", ":")).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") + ";\n"
    (目录 / "检索索引.js").write_text(索引脚本, encoding="utf-8")
    (目录 / "首页.html").write_text(生成首页(干员清单, 非干员清单, 统计), encoding="utf-8")
    (目录 / "生成结果.json").write_text(json.dumps({
        "说明": "此文件是展示页生成统计，不是原始游戏资料。",
        "干员页面数": len(干员清单),
        "非干员档案数": len(非干员清单),
        "Markdown档案数": len(list(Markdown目录.glob("*.md"))),
        **统计,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {len(干员清单)} 名干员的网页和 Markdown 档案。")
    print(f"另有 {len(非干员清单)} 份非干员档案。")
    print(f"首页：{目录 / '首页.html'}")


if __name__ == "__main__":
    主程序()
