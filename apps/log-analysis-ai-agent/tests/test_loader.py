"""tests/test_loader.py — core/loader.py 단위 테스트"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.loader import load_from_text

SAMPLE = """\
[2024-01-15 09:00:01] [AuthService] [INFO] [Thread-1] [Security] [User admin logged in successfully]
[2024-01-15 09:00:05] [AuthService] [ERROR] [Thread-2] [Security] [Login failed for user guest from IP 192.168.1.10]
[2024-01-15 09:00:12] [AuthService] [ERROR] [Thread-3] [Security] [Login failed for user root from IP 10.0.0.5]
[2024-01-15 09:01:00] [DBService] [INFO] [Thread-5] [Database] [Connection established to host db-01 port 5432]
[2024-01-15 09:01:10] [DBService] [WARN] [Thread-7] [Database] [Query execution time exceeded 500ms on table orders]
"""


def test_returns_four_values():
    result = load_from_text(SAMPLE)
    assert len(result) == 4


def test_log_df_row_count():
    log_df, _, _, _ = load_from_text(SAMPLE)
    assert len(log_df) == 5


def test_log_df_columns():
    log_df, _, _, _ = load_from_text(SAMPLE)
    expected = {"line_number", "datetime", "system", "level", "thread", "category", "message", "raw"}
    assert expected.issubset(set(log_df.columns))


def test_template_df_unique_template_id():
    _, template_df, _, _ = load_from_text(SAMPLE)
    assert template_df["template_id"].is_unique


def test_merged_df_has_all_columns():
    log_df, template_df, merged_df, _ = load_from_text(SAMPLE)
    for col in log_df.columns:
        assert col in merged_df.columns
    for col in template_df.columns:
        assert col in merged_df.columns


def test_merged_df_same_row_count_as_log():
    log_df, _, merged_df, _ = load_from_text(SAMPLE)
    assert len(merged_df) == len(log_df)


def test_template_tree_is_nonempty_string():
    _, _, _, template_tree = load_from_text(SAMPLE)
    assert isinstance(template_tree, str)
    assert len(template_tree) > 0


def test_empty_input_returns_empty_dataframes():
    log_df, template_df, merged_df, template_tree = load_from_text("")
    assert len(log_df) == 0
    assert len(template_df) == 0
    assert template_tree == ""
