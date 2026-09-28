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
            "target:elite_first": ("酒神",),
            "attack:5_hits": ("纯烬艾雅法拉",),
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
            "target:elite_first": ("黑键",),
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
            "target:high_def_first": ("丰川祥子",),
            "range:two_skills_outside": ("澄闪", "莱伊", "逻各斯", "玛恩纳"),
        }
        for fact_id, names in expected.items():
            for name in names:
                with self.subTest(fact=fact_id, operator=name):
                    self.assertIn(fact_id, self.clues(name))

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


if __name__ == "__main__":
    unittest.main()
