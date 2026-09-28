"""Regression checks for material names in generated operator archives."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import 生成展示档案 as archive


class ArchiveAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive.物品名称表 = json.loads(
            (archive.映射目录 / "物品名称.json").read_text(encoding="utf-8"))

    def test_module_materials_show_names_and_counts_in_both_formats(self):
        module_info = {"物品消耗": {"1": [
            {"编号": "mod_unlock_token", "计数": 4, "类型": "MATERIAL"},
            {"编号": "4001", "计数": 80000, "类型": "GOLD"},
        ]}}
        html = archive.递归网页(module_info, "测试干员")
        markdown = archive.递归Markdown(module_info, "测试干员")
        for text in (html, markdown):
            self.assertIn("模组数据块", text)
            self.assertIn("龙门币", text)
            self.assertIn("4", text)
            self.assertIn("80000", text)

    def test_page_write_recovers_from_transient_windows_open_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "测试.html"
            real_write = Path.write_text
            attempts = 0

            def intermittent_write(target, data, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError(22, "Invalid argument")
                return real_write(target, data, **kwargs)

            with patch.object(Path, "write_text", intermittent_write):
                archive.写入网页(path, "测试", "<p>内容</p>", "style.css", "index.html", "测试")
            self.assertEqual(attempts, 2)
            self.assertIn("<p>内容</p>", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
