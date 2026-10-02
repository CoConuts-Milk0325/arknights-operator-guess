"""Source-backed regressions for the reviewed clue index."""

import json
import unittest

import 生成游戏数据 as game


class AuditCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(game.SOURCE.read_text(encoding="utf-8"))
        cls.records = {record["干员名称"]: record for record in raw["干员"].values()}

    def clues(self, name):
        profile = game.make_profile(self.records[name])
        return {fact[0]: fact[4] for fact in game.facts_for(
            profile, {profile["branch"]: {profile["rarity"]}})}

    def test_false_support_and_self_effects_are_excluded(self):
        excluded = {
            "ally:output:attack": ("仇白", "卡涅利安", "夜半", "灰烬", "猎蜂",
                                   "瑕光", "维什戴尔", "维娜·维多利亚", "莱伊", "慑砂"),
            "ally:output:penetration": ("伺夜", "战车", "罗小黑", "艾拉"),
            "ally:survival:max_hp": ("史尔特尔",),
            "ally:survival_nonheal": ("史尔特尔",),
            "heal:hunger": ("绮良", "塞雷娅"),
            "heal:attack_self": ("伺夜",),
            "mechanic:stop_attack": ("渡桥",),
            "target:high_def_first": ("丰川祥子",),
            "attack:5_hits": ("纯烬艾雅法拉",),
            "range:can_shrink": ("远牙",),
            "range:expand": ("灰烬", "和弦", "戴菲恩", "深靛", "爱丽丝", "黑键", "玫拉"),
            "debuff:fragile": ("石英",),
            "control:one": ("可颂",),
            "control:can:teleport": ("珊比",),
            "control:can:stun": ("断罪者",),
            "ally:survival:shelter": ("亚叶", "齐尔查克"),
            "attack:extra_arts": ("焰影苇草", "霍尔海雅"),
        }
        for fact_id, names in excluded.items():
            for name in names:
                with self.subTest(fact=fact_id, operator=name):
                    self.assertNotIn(fact_id, set(self.clues(name)))

    def test_missing_source_backed_clues_are_included(self):
        included = {
            "range:two_skills_outside": ("远牙",),
            "air:normal_attack": ("埃癸斯", "天空盒"),
            "ally:block_up": ("桃金娘", "极境", "琴柳", "万顷", "嘉辛塔", "帕拉斯", "娜斯提"),
            "ally:output:attack": ("华法琳", "空构", "娜斯提"),
            "ally:output:speed": ("空构",),
            "ally:survival:defense": ("娜斯提", "砾"),
            "ally:survival:shield": ("娜斯提",),
            "ally:survival:max_hp": ("蜜莓", "万顷", "淬羽赫默", "魔王", "海蒂"),
            "ally:survival:shelter": ("维娜·维多利亚", "歌蕾蒂娅", "魔王"),
            "ally:output:penetration": ("丰川祥子",),
            "ally:sp_support": ("陈", "炎狱炎熔", "归溟幽灵鲨"),
            "control:can:push": ("可颂",),
            "control:exact:2": ("可颂",),
            "combo:skill_two_controls:push:stun": ("可颂",),
            "combo:skill_damage_control:physical:push": ("可颂",),
            "combo:aoe_control:push": ("可颂",),
            "combo:skill_two_controls:silence:slow": ("波登可",),
            "talent:on_deploy_global_heal": ("末药",),
            "attack:arts_switch": ("布洛卡", "年", "余", "芳汀"),
            "attack:physical_switch": ("特米米",),
            "attack:splash": ("奥达",),
            "range:can_shrink": ("特米米",),
            "target:blocked_first": ("和弦", "歌蕾蒂娅"),
            "target:elite_first": ("黑键", "酒神"),
            "skill:passive_active": ("令", "结城理", "赫德雷", "乌有"),
            "skill:redeploy_reduction": ("莱伊",),
            "skill:refresh": ("史尔特尔",),
            "mechanic:stop_attack": ("乌有",),
            "attack:bonus_arts_hit": ("雷狼龙S空爆",),
            "combo:skill_damage_control:physical:levitate": ("奥达",),
            "combo:skill_damage_control:arts:cold": ("耶拉",),
            "combo:skill_damage_control:physical:cold": ("极光",),
            "damage:only:true": ("浊心斯卡蒂",),
            "damage:only_one": ("浊心斯卡蒂",),
            "attack:skill_targets:3": ("左乐", "斩业星熊", "崖心"),
            "attack:skill_targets:4": ("山", "裁度", "棘刺", "异客"),
            "attack:skill_targets:5": ("安洁莉娜",),
            "attack:skill_targets:6": ("嵯峨",),
        }
        for fact_id, names in included.items():
            for name in names:
                with self.subTest(fact=fact_id, operator=name):
                    self.assertIn(fact_id, set(self.clues(name)))

    def test_target_limit_does_not_count_status_only_or_extra_chain_targets(self):
        for name, fact_id in (("极境", "attack:skill_targets:4"),
                              ("水月", "attack:skill_targets:3"),
                              ("溯光星源", "attack:skill_targets:3")):
            with self.subTest(operator=name):
                self.assertNotIn(fact_id, set(self.clues(name)))

    def test_extra_attack_targets_count_toward_the_total(self):
        for name, fact_id in (("蓝毒", "attack:skill_targets:3"),
                              ("铅踝", "attack:skill_targets:3"),
                              ("仇白", "attack:skill_targets:3"),
                              ("云迹", "attack:skill_targets:3"),
                              ("予愿安洁莉娜", "attack:skill_targets:4")):
            with self.subTest(operator=name):
                self.assertIn(fact_id, self.clues(name))
        self.assertNotIn("attack:skill_targets:3", self.clues("予愿安洁莉娜"))

    def test_locking_counts_when_the_skill_attacks_locked_targets(self):
        attacking = {"params": {}, "text": "锁定周围最多4名敌人并持续攻击这些目标"}
        status_only = {"params": {}, "text": "停止攻击，锁定周围最多4名敌人并降低其防御力"}
        self.assertEqual(game.capped_damage_targets(attacking), 4)
        self.assertEqual(game.capped_damage_targets(status_only), 0)

    def test_index_evidence_has_no_unresolved_value_markers(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        facts, _ = game.build_facts(profiles)
        for fact in facts:
            for evidence in fact["evidence"].values():
                with self.subTest(fact=fact["id"], operator=evidence[2]):
                    self.assertNotIn("数值未标注", evidence[1])
                    self.assertNotIn("{", evidence[1])
                    self.assertNotIn("}", evidence[1])

    def test_evidence_uses_source_values_not_placeholder_text(self):
        self.assertIn("每秒恢复70点生命", self.clues("暴雨")["mechanic:charge:2"])
        self.assertIn("持续4秒", self.clues("暴雨")["mechanic:charge:2"])
        self.assertIn("每秒恢复最大生命的7%", self.clues("山")["heal:max_hp_ratio"])
        self.assertIn("40秒", self.clues("司霆惊蛰")["attack:normal_none"])
        self.assertIn("10%攻击力的法术伤害", self.clues("银灰")["damage:can:arts"])

    def test_related_team_buffs_become_visible_when_parameters_are_expanded(self):
        self.assertIn("ally:output:attack", self.clues("祐天寺若麦"))
        self.assertIn("ally:survival:max_hp", self.clues("若叶睦"))
        self.assertIn("attack:skill_targets:3", self.clues("遥"))

    def test_elemental_fragile_requires_its_own_effect(self):
        for name in ("凛御银灰", "琴柳", "艾拉"):
            with self.subTest(operator=name):
                clues = self.clues(name)
                self.assertIn("debuff:fragile", clues)
                self.assertNotIn("debuff:elemental_fragile", clues)
        for name in ("塑心", "PhonoR-0"):
            with self.subTest(operator=name):
                self.assertIn("元素脆弱", self.clues(name)["debuff:elemental_fragile"])
                self.assertNotIn("debuff:fragile", self.clues(name))

    def test_specific_fragile_types_do_not_become_generic_fragile(self):
        for name, fact_id in (("W", "debuff:physical_fragile"),
                              ("慑砂", "debuff:physical_fragile"),
                              ("百炼嘉维尔", "debuff:physical_fragile"),
                              ("濯尘芙蓉", "debuff:arts_fragile"),
                              ("焰影苇草", "debuff:arts_fragile"),
                              ("史尔特尔", "debuff:arts_fragile"),
                              ("PhonoR-0", "debuff:arts_fragile")):
            with self.subTest(operator=name):
                clues = self.clues(name)
                self.assertIn(fact_id, clues)
                self.assertNotIn("debuff:fragile", clues)
        for fact_id in ("debuff:arts_fragile", "debuff:physical_fragile"):
            self.assertIn(fact_id, self.clues("艾拉"))
            self.assertNotIn(fact_id, self.clues("塑心"))
            self.assertNotIn(fact_id, self.clues("石英"))

    def test_physical_fragile_effect_is_separate_from_physical_damage_amplification(self):
        profile = game.make_profile(self.records["百炼嘉维尔"])
        facts = {fact[0]: fact for fact in game.facts_for(
            profile, {profile["branch"]: {profile["rarity"]}})}
        self.assertIn("debuff:physical_fragile_effect", facts)
        effect = facts["debuff:physical_fragile_effect"]
        self.assertEqual(effect[3], "能使敌人获得物理脆弱（仅物理伤害增加）")
        self.assertIn("好锯多磨", effect[4])
        self.assertIn("物理脆弱", effect[4])
        for name in ("W", "慑砂", "艾拉", "铃兰", "琴柳", "塑心", "石英"):
            with self.subTest(operator=name):
                self.assertNotIn("debuff:physical_fragile_effect", self.clues(name))
        for name in ("W", "慑砂", "艾拉", "铃兰", "琴柳", "百炼嘉维尔"):
            with self.subTest(operator=name):
                self.assertIn("debuff:physical_fragile", self.clues(name))
        self.assertIn("debuff:physical_fragile", game.implied_fact_ids(
            "debuff:physical_fragile_effect"))

    def test_every_explicit_elemental_fragile_source_is_indexed(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        expected = set()
        for profile in profiles:
            if any("元素脆弱" in phrase
                   for module in profile["modules"]
                   for skill in [None, *profile["skills"]]
                   for _, phrase in game.sources_for(profile, module, skill)):
                expected.add(profile["name"])
        facts, _ = game.build_facts(profiles)
        actual = next(set(fact["memberNames"]) for fact in facts
                      if fact["id"] == "debuff:elemental_fragile")
        self.assertEqual(expected, actual)

    def test_only_specific_hunger_regeneration_clue_remains(self):
        for name in self.records:
            with self.subTest(operator=name):
                self.assertNotIn("heal:regen_other", self.clues(name))
        self.assertIn("heal:hunger", self.clues("暴雨"))

    def test_two_damage_one_control_uses_all_operator_abilities(self):
        for name in ("缄默德克萨斯", "结城理", "刻俄柏", "老鲤", "仇白",
                     "忍冬", "杏仁", "焰狐龙梓兰", "崖心"):
            with self.subTest(operator=name):
                self.assertNotIn("combo:two_damage_one_control", self.clues(name))
        self.assertIn("combo:two_damage_one_control", self.clues("暗索"))

    def test_reviewed_skill_text_omissions_are_indexed(self):
        expected = {
            "attack:10_hits": ("陈", "阿米娅（近卫）"),
            "attack:three_hits": ("鸿雪",),
            "attack:extra_arts": ("苇草",),
            "ally:prevent_death": ("缇缇", "丰川祥子", "斩业星熊"),
            "target:high_def_first": ("史都华德", "刻俄柏"),
            "range:two_skills_outside": ("澄闪", "莱伊", "逻各斯", "玛恩纳"),
        }
        for fact_id, names in expected.items():
            for name in names:
                with self.subTest(fact=fact_id, operator=name):
                    self.assertIn(fact_id, self.clues(name))

    def test_seven_disputed_clue_mechanisms(self):
        lin = self.clues("林")
        self.assertIn("combo:aoe_control:stun", lin)
        self.assertIn("流光乍裂", lin["combo:aoe_control:stun"])
        self.assertIn("计出万全", lin["combo:aoe_control:stun"])

        roberta = self.clues("罗比菈塔")
        for fact_id in ("self:shield", "ally:survival_nonheal", "damage:only_one",
                        "combo:one_damage_no_control"):
            self.assertIn(fact_id, roberta)

        for name in ("小满", "但书", "伯塔尼", "凛视", "波卜"):
            with self.subTest(operator=name):
                self.assertNotIn("attack:arts_switch", self.clues(name))
        self.assertIn("range:two_skills_outside", self.clues("结城理"))
        self.assertIn("control:one", self.clues("伊内丝"))
        self.assertIn("heal:no_direct", self.clues("伊桑"))

        for name, skill_name in (("可露希尔", "模型扩展"), ("缪尔赛思", "生态耦合")):
            with self.subTest(operator=name):
                profile = game.make_profile(self.records[name])
                facts = game.facts_for(profile, {profile["branch"]: {profile["rarity"]}})
                direct = next(fact for fact in facts if fact[0] == "mechanic:deployment_cost")
                gradual = next(fact for fact in facts if fact[0] == "skill:dp_over_time")
                self.assertIn(skill_name, direct[4])
                self.assertEqual(direct[2], gradual[2])

    def test_range_grid_expansion_includes_thorns_second_skill(self):
        self.assertEqual(game.range_extra_cells("3-12", "3-1"), {(1, 2), (-1, 2)})
        for name, skills in (("棘刺", ("护身尖刺", "至高之术")),
                             ("结城理", ("俄耳甫斯的竖琴", "塔纳托斯的囚锁", "开辟明日的剑刃"))):
            with self.subTest(operator=name):
                clues = self.clues(name)
                self.assertIn("range:expand", clues)
                self.assertIn("range:two_skills_outside", clues)
                for skill_name in skills:
                    self.assertIn(skill_name, clues["range:two_skills_outside"])
        for name in ("暴雨", "古米", "塞雷娅"):
            with self.subTest(operator=name):
                self.assertNotIn("range:two_skills_outside", self.clues(name))

    def test_every_structured_range_id_has_a_grid(self):
        missing = set()
        for record in self.records.values():
            profile = game.make_profile(record)
            for range_id in (profile["base_range_id"], *(skill["range_id"] for skill in profile["skills"])):
                if range_id and range_id not in game.RANGE_GRIDS:
                    missing.add(range_id)
        self.assertEqual(missing, set())

    def test_no_direct_heal_never_conflicts_with_direct_heal(self):
        for name, record in self.records.items():
            with self.subTest(operator=name):
                profile = game.make_profile(record)
                ids = {fact[0] for fact in game.facts_for(
                    profile, {profile["branch"]: {profile["rarity"]}})}
                self.assertFalse({"heal:no_direct", "heal:direct_other"} <= ids)

    def test_disputed_original_questions_are_not_unique(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        profiles.sort(key=lambda profile: (profile["name"].casefold(), profile["id"]))
        facts, _ = game.build_facts(profiles)
        by_id = {fact["id"]: fact for fact in facts}
        cases = {
            "蜜蜡": ({"attack:normal_none", "profession:exact:术师", "range:expand",
                    "combo:aoe_control:stun"}, {"蜜蜡", "林"}),
            "砾": ({"self:shield", "ally:survival_nonheal", "combo:one_damage_no_control",
                   "rarity:exact:4"}, {"砾", "罗比菈塔"}),
            "司霆惊蛰": ({"range:two_skills_outside", "attack:skill_targets:4", "rarity:exact:6",
                      "combo:skill_two_damage:arts:physical"}, {"司霆惊蛰", "结城理"}),
            "冬时": ({"cost:maxpot:one_digit", "skill:activation:auto",
                    "mechanic:deployment_cost", "control:one"}, {"冬时", "伊内丝"}),
            "绮良": ({"profession:exact:特种", "attack:extra_arts", "damage:exact_two",
                    "heal:no_direct"}, {"绮良", "伊桑"}),
        }
        for target, (clue_ids, expected) in cases.items():
            with self.subTest(answer=target):
                possible = set(range(len(profiles)))
                for clue_id in clue_ids:
                    fact = by_id[clue_id]
                    possible &= set(fact.get("possibleMembers", fact["members"]))
                self.assertEqual({profiles[index]["name"] for index in possible}, expected)

    def test_branch_backed_normal_air_attack(self):
        for name in ("艾雅法拉", "伊芙利特", "澄闪", "银灰", "棘刺",
                     "早露", "提丰", "黑", "鸿雪", "豆苗", "初雪",
                     "刺玫", "濯尘芙蓉", "焰影苇草", "缇缇", "阿米娅（医疗）",
                     "引星棘刺", "锡人", "予愿安洁莉娜", "云迹", "蒂比",
                     "战车", "贝娜"):
            with self.subTest(operator=name):
                self.assertIn("air:normal_attack", self.clues(name))
        for name in ("星熊", "泥岩", "塞雷娅"):
            with self.subTest(operator=name):
                self.assertNotIn("air:normal_attack", self.clues(name))

    def test_confirmed_normal_air_members_are_excluded_from_no_air_candidates(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        facts, _ = game.build_facts(profiles)
        by_id = {fact["id"]: fact for fact in facts}
        confirmed_air = set(by_id["air:normal_attack"]["members"])
        possible_no_air = set(by_id["air:solo_none"]["possibleMembers"])
        self.assertFalse(confirmed_air & possible_no_air)
        for name in ("星熊", "年", "泡泡"):
            with self.subTest(operator=name, fact="air:solo_none"):
                index = next(index for index, profile in enumerate(profiles) if profile["name"] == name)
                self.assertNotIn(index, possible_no_air)

    def test_no_air_count_uses_all_damage_abilities(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        facts, _ = game.build_facts(profiles)
        by_id = {fact["id"]: fact for fact in facts}
        normal_air = set(by_id["air:normal_attack"]["members"])
        confirmed_no_air = set(by_id["air:solo_none"]["members"])
        special_air = {index for index, profile in enumerate(profiles)
                       if game.AUDITED.get(profile["id"], {}).get("air_damage")}
        self.assertFalse(normal_air & confirmed_no_air)
        self.assertFalse(special_air & confirmed_no_air)
        self.assertEqual((209, 49, 173),
                         (len(normal_air), len(special_air), len(confirmed_no_air)))
        self.assertEqual(set(range(len(profiles))),
                         normal_air | special_air | confirmed_no_air)
        self.assertEqual(confirmed_no_air, set(by_id["air:solo_none"]["possibleMembers"]))
        self.assertLess(len(profiles) - len(normal_air | special_air), 200)
        self.assertEqual(set(by_id["air:solo_none"]["possibleMembers"]),
                         set(range(len(profiles))) - normal_air - special_air)

        for name in ("安赛尔", "白面鸮", "明椒", "风絮", "海蒂",
                     "桃金娘", "芬", "风笛", "古米", "圣约送葬人",
                     "阿兰娜", "火神", "孑", "野鬃", "食铁兽",
                     "归溟幽灵鲨", "若叶睦"):
            with self.subTest(operator=name, fact="air:solo_none"):
                self.assertIn("air:solo_none", self.clues(name))
        for name in ("刻刀", "重岳", "德克萨斯", "卡夫卡", "温蒂",
                     "老鲤", "煌", "风丸", "维什戴尔", "白铁", "司霆惊蛰",
                     "焰尾", "凛御银灰", "余", "坚雷", "赫德雷", "斥罪",
                     "锏", "双月", "柏喙"):
            with self.subTest(operator=name, fact="air:solo_none"):
                self.assertNotIn("air:solo_none", self.clues(name))

    def test_user_confirmed_air_partition_resolves_previous_33(self):
        air_names = {"艾丽妮", "火龙S黑角"}
        no_air_names = {
            "奥达", "阿斯卡纶", "八幡海铃", "暴行", "裁度", "承曦格雷伊",
            "哈蒂娅", "号角", "灰毫", "虎狼丸", "火哨", "杰克", "可颂",
            "雷狼龙S空爆", "琳琅诗怀雅", "迷迭香", "怒潮凛冬", "佩佩",
            "绮良", "山", "狮蝎", "水月", "泰拉大陆调查团", "推进之王",
            "维荻", "乌尔比安", "洋灰", "耀骑士临光", "伊桑",
            "祐天寺若麦", "阿米娅（近卫）",
        }
        self.assertEqual(2, len(air_names))
        self.assertEqual(31, len(no_air_names))
        by_name = {name: game.make_profile(record)["id"]
                   for name, record in self.records.items()}
        self.assertEqual({by_name[name] for name in no_air_names},
                         game.NO_AIR_USER_CONFIRMED_IDS)
        for name in air_names:
            with self.subTest(operator=name):
                self.assertTrue(game.AUDITED[by_name[name]]["air_damage"])
                self.assertNotIn("air:solo_none", self.clues(name))
        for name in no_air_names:
            with self.subTest(operator=name):
                self.assertIn("air:solo_none", self.clues(name))

    def test_no_air_requires_review_of_the_whole_damage_kit(self):
        for name in ("塞雷娅", "泥岩", "蛇屠箱", "拜松", "斑点",
                     "黑角", "角峰", "缠丸", "芙兰卡", "斯卡蒂",
                     "可颂", "耀骑士临光"):
            with self.subTest(operator=name):
                self.assertIn("air:solo_none", self.clues(name))
        for name in ("年", "泡泡"):
            with self.subTest(operator=name):
                self.assertNotIn("air:solo_none", self.clues(name))

    def test_random_one_of_controls_do_not_form_impossible_pairs(self):
        clues = self.clues("傀影")
        for left, right in (("root", "slow"), ("root", "stun"), ("slow", "stun")):
            self.assertNotIn(f"combo:skill_two_controls:{left}:{right}", clues)
        for control in ("root", "slow", "stun"):
            self.assertIn(f"combo:skill_two_controls:push:{control}", clues)

    def test_second_gemini_audit_confirmed_errors(self):
        self.assertNotIn("heal:all_allies", self.clues("桑葚"))
        for name in ("嘉维尔", "清流", "铃兰", "纯烬艾雅法拉"):
            with self.subTest(operator=name, fact="heal:all_allies"):
                self.assertIn("heal:all_allies", self.clues(name))
        self.assertIn("云霭荫佑", self.clues("纯烬艾雅法拉")["heal:all_allies"])
        self.assertNotIn("heal:hunger", self.clues("嘉维尔"))

        muelsyse = self.clues("缪尔赛思")
        for pair in ("pull:root", "root:stun"):
            self.assertNotIn(f"combo:skill_two_controls:{pair}", muelsyse)
        self.assertIn("combo:skill_two_controls:pull:stun", muelsyse)

        self.assertNotIn("air:solo_none", self.clues("星熊"))
        self.assertNotIn("air:normal_attack", self.clues("星熊"))
        for name in ("孑", "乌有", "老鲤", "琳琅诗怀雅", "裁度"):
            with self.subTest(operator=name, fact="air:normal_attack"):
                self.assertNotIn("air:normal_attack", self.clues(name))

    def test_specific_bonus_arts_damage_implies_extra_arts(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        facts, _ = game.build_facts(profiles)
        by_id = {fact["id"]: fact for fact in facts}
        specific = by_id["attack:bonus_arts_hit"]
        general = by_id["attack:extra_arts"]
        self.assertLessEqual(set(specific["members"]), set(general["members"]))
        self.assertIn("attack:extra_arts", specific.get("implies", []))

    def test_chilchuck_random_lump_sum_dp_uses_first_skill(self):
        skills = game.make_profile(self.records["齐尔查克"])["skills"]
        self.assertEqual(game.direct_dp_skill([skills[0]]),
                         ("开锁工具", "停止攻击，技能结束后随机获得4-10点部署费用"))
        self.assertIsNone(game.direct_dp_skill([skills[1]]))
        evidence = self.clues("齐尔查克")["mechanic:deployment_cost"]
        self.assertIn("开锁工具", evidence)
        self.assertIn("技能结束后随机获得4-10点部署费用", evidence)
        self.assertNotIn("随机应变", evidence)

    def test_repeated_dp_is_excluded_but_next_attack_lump_sum_is_kept(self):
        ines = game.make_profile(self.records["伊内丝"])["skills"]
        self.assertIsNotNone(game.direct_dp_skill([ines[0]]))
        self.assertIsNone(game.direct_dp_skill([ines[2]]))
        qingzhi = game.make_profile(self.records["青枳"])["skills"][1]
        periodic_clause = qingzhi["text"].split("，")[-2]
        self.assertIsNone(game.direct_dp_skill([
            {"name": qingzhi["name"], "text": periodic_clause}]))
        self.assertEqual(game.direct_dp_skill([qingzhi])[0], qingzhi["name"])
        for name in ("冬时", "谜图"):
            skills = game.make_profile(self.records[name])["skills"]
            self.assertIsNotNone(game.direct_dp_skill([skills[0]]))
            self.assertIsNone(game.direct_dp_skill([skills[1]]))

    def test_round_16_fixes(self):
        for name in ("锡兰", "絮雨", "诺威尔"):
            self.assertIn("heal:direct_other", self.clues(name))
            self.assertNotIn("heal:no_direct", self.clues(name))

        for name in ("弑君者", "红", "杰西卡", "猎蜂"):
            self.assertIn("survival:physical_dodge", self.clues(name))

        for name in ("寻澜", "晓歌"):
            self.assertNotIn("mechanic:deployment_cost", self.clues(name))

        for name in ("黑键", "薇薇安娜", "酒神"):
            self.assertIn("target:elite_first", self.clues(name))

        self.assertIn("target:high_def_first", self.clues("史都华德"))
        self.assertIn("target:high_def_first", self.clues("刻俄柏"))
        self.assertNotIn("target:high_def_first", self.clues("丰川祥子"))

    def test_fever_two_hits_keep_their_condition(self):
        profile = game.make_profile(self.records["丰川祥子"])
        skill = next(s for s in profile["skills"] if s["name"] == "满月的舞会")
        self.assertEqual({2}, game.skill_hit_counts(skill["text"]))
        self.assertIn("Fever期间", self.clues("丰川祥子")["attack:two_hits"])

    def test_unrelated_talent_probability_does_not_hide_three_hits(self):
        profile = game.make_profile(self.records["薇薇安娜"])
        self.assertEqual({2, 3}, game.skill_hit_counts(profile["skills"][2]["text"]))
        # “可以”涵盖概率触发；该条件必须出现在支持该事实的技能文本中。
        self.assertEqual({2}, game.skill_hit_counts(profile["skills"][1]["text"]))

    def test_removed_allied_trigger_is_not_used_as_a_clue(self):
        for name in ("烈夏", "丰川祥子", "八幡海铃", "三角初华", "祐天寺若麦", "若叶睦"):
            with self.subTest(operator=name):
                self.assertNotIn("skill:allied_skill_trigger", set(self.clues(name)))

    def test_fever_candidates_are_retained_for_unique_rounds(self):
        profiles = [game.make_profile(record) for record in self.records.values()]
        facts, _ = game.build_facts(profiles)
        by_id = {f["id"]: f for f in facts}
        index = {p["name"]: i for i, p in enumerate(profiles)}
        hits = by_id["attack:two_hits"]
        self.assertIn(index["丰川祥子"], hits.get("possibleMembers", hits["members"]))
        self.assertNotIn("skill:allied_skill_trigger", by_id)

    def test_body_subset_range_is_shrinking_but_summon_effects_are_not(self):
        clues = self.clues("Mon3tr")
        self.assertIn("range:can_shrink", clues)
        self.assertIn("策略：熔毁", clues["range:can_shrink"])
        for name in ("梅尔", "渡桥", "远牙", "灰烬", "爱丽丝"):
            with self.subTest(operator=name):
                self.assertNotIn("range:can_shrink", self.clues(name))

    def test_clean_preserves_sentence_boundaries_without_extra_commas(self):
        cases = {
            "演奏：\\n钢琴：": "演奏：钢琴：",
            "技能。\\nFever期间": "技能。Fever期间",
            "连续攻击两次；\n蓄力额外效果：": "连续攻击两次；蓄力额外效果：",
            "减缓 ，Fever": "减缓，Fever",
            "第一句\r\n第二句": "第一句，第二句",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(expected, game.clean(raw))


if __name__ == "__main__":
    unittest.main()
