"""养护计划业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "plan"
REQUIRED_FIELDS = ["计划编号", "养护类型", "养护对象"]
# 提交审批前必须补齐的字段：金额或工期漏填的计划不许提交
SUBMIT_REQUIRED_FIELDS = REQUIRED_FIELDS + ["计划开始日期", "计划工期", "预算金额"]
EDITABLE_FIELDS = ["养护类型", "养护对象", "计划开始日期", "计划工期", "预算金额", "编制人员"]
STATUS_ORDER = ["待编制", "待审批", "已批复", "已驳回", "已作废"]
ACTION_RULES = {"提交审批": "待审批", "确认批复": "已批复", "作废计划": "已作废"}
NEGATIVE_ACTIONS = ["作废计划"]
# 只有编制中的草稿和被驳回的计划能（重新）提交审批
SUBMITTABLE_STATUSES = {"待编制", "已驳回"}
# 被驳回与编制中的计划允许修改，改完回到待编制接着报
EDITABLE_STATUSES = {"待编制", "已驳回"}
# 占用养护对象时间段的状态：已驳回、已作废的不占
OCCUPYING_STATUSES = {"待编制", "待审批", "已批复"}

# 判定口径：按养护类型限定预算金额（万元）与计划工期（天）的可接受范围；
# 日均费用（万元/天）用来拦「金额和工期对不上」的计划。
TYPE_RULES: dict[str, dict[str, tuple[float, float]]] = {
    "日常养护": {"预算金额": (1, 50), "计划工期": (1, 90), "日均费用": (0.05, 5)},
    "小修保养": {"预算金额": (10, 200), "计划工期": (7, 180), "日均费用": (0.1, 10)},
    "中修工程": {"预算金额": (50, 800), "计划工期": (30, 365), "日均费用": (0.2, 20)},
    "大修工程": {"预算金额": (200, 3000), "计划工期": (90, 730), "日均费用": (0.5, 30)},
    "应急抢修": {"预算金额": (5, 300), "计划工期": (1, 30), "日均费用": (0.5, 50)},
}
# 没列入口径表的养护类型按默认范围把关
DEFAULT_RULE = {"预算金额": (1, 500), "计划工期": (1, 365), "日均费用": (0.05, 20)}


def _parse_amount(raw: Any) -> float | None:
    """把预算金额解析成万元数值；填的不是数字时返回 None。"""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or "").strip().replace(",", "")
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(万元|万|元)?", text)
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2) == "元":
        value /= 10000
    return value


def _parse_days(raw: Any) -> int | None:
    """把计划工期解析成天；接受 30、"30"、"30天" 这类写法。"""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw) if float(raw) > 0 else None
    match = re.fullmatch(r"(\d+)\s*天?", str(raw or "").strip())
    return int(match.group(1)) if match else None


def _parse_date(raw: Any) -> date | None:
    """把计划开始日期解析成 date；只认 YYYY-MM-DD。"""
    try:
        return date.fromisoformat(str(raw or "").strip())
    except ValueError:
        return None


def _fmt_range(rule: tuple[float, float], unit: str) -> str:
    def fmt(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    return f"{fmt(rule[0])}~{fmt(rule[1])} {unit}".strip()


def rule_book() -> list[dict[str, Any]]:
    """把判定口径整理成前端可直接展示的条目。"""
    book = [
        {
            "养护类型": name,
            "预算金额范围": _fmt_range(rule["预算金额"], "万元"),
            "计划工期范围": _fmt_range(rule["计划工期"], "天"),
            "日均费用范围": _fmt_range(rule["日均费用"], "万元/天"),
        }
        for name, rule in TYPE_RULES.items()
    ]
    book.append({
        "养护类型": "其他类型（默认口径）",
        "预算金额范围": _fmt_range(DEFAULT_RULE["预算金额"], "万元"),
        "计划工期范围": _fmt_range(DEFAULT_RULE["计划工期"], "天"),
        "日均费用范围": _fmt_range(DEFAULT_RULE["日均费用"], "万元/天"),
    })
    return book


class PlanService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("计划编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + EDITABLE_FIELDS:
            if values.get(field) is not None:
                entry[field] = values.get(field)
        entry["审批人员"] = values.get("审批人员") or ""
        entry["驳回理由"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        self._normalize(entry)
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """修改计划内容；被驳回的计划改完回到待编制，可以接着提交审批。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护计划 {entry_id} 不存在或已归档"
        if entry.get("status") not in EDITABLE_STATUSES:
            return None, f"当前状态「{entry.get('status')}」的计划不能修改，只有待编制或已驳回的可以改"
        for field in EDITABLE_FIELDS:
            if values.get(field) is not None:
                entry[field] = values.get(field)
        missing = [field for field in REQUIRED_FIELDS if not str(entry.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        entry["驳回理由"] = ""
        entry["status"] = "待编制"
        entry["pending"] = True
        entry["abnormal"] = False
        self._normalize(entry)
        return entry, "养护计划已修改并回到待编制，可重新提交审批"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str, bool]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护计划 {entry_id} 不存在或已归档", False
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护计划可执行范围", False
        if action == "提交审批":
            return self._submit(entry)
        if action == "确认批复" and entry.get("status") != "待审批":
            return None, f"当前状态「{entry.get('status')}」不能直接批复，需先提交审批并通过口径校验", False
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里", False
        entry["status"] = target
        entry["驳回理由"] = ""
        entry["pending"] = target not in ("已批复", "已作废")
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        self._normalize(entry)
        return entry, f"养护计划已{action}", True

    def _submit(self, entry: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
        """提交审批：先过判定口径，越界或冲突的拦成已驳回并写清理由。"""
        if entry.get("status") not in SUBMITTABLE_STATUSES:
            return entry, f"当前状态「{entry.get('status')}」不能提交审批", False
        problems = self.validate_submission(entry)
        if problems:
            entry["status"] = "已驳回"
            entry["驳回理由"] = "；".join(problems)
            entry["pending"] = True
            entry["abnormal"] = False
            self._normalize(entry)
            return entry, f"养护计划未通过提交校验，已拦下：{entry['驳回理由']}", False
        entry["status"] = "待审批"
        entry["驳回理由"] = ""
        entry["pending"] = True
        entry["abnormal"] = False
        self._normalize(entry)
        return entry, "养护计划已提交审批", True

    def validate_submission(self, entry: dict[str, Any]) -> list[str]:
        """按判定口径检查一条计划，返回问题清单；空清单表示可以提交。"""
        problems: list[str] = []
        missing = [field for field in SUBMIT_REQUIRED_FIELDS if not str(entry.get(field) or "").strip()]
        if missing:
            problems.append(f"{'、'.join(missing)}未填写，金额或工期漏填的计划不许提交")
            return problems

        plan_type = str(entry.get("养护类型") or "").strip()
        rule = TYPE_RULES.get(plan_type, DEFAULT_RULE)
        amount = _parse_amount(entry.get("预算金额"))
        days = _parse_days(entry.get("计划工期"))
        start = _parse_date(entry.get("计划开始日期"))

        if amount is None:
            problems.append(f"预算金额「{entry.get('预算金额')}」不是有效金额（单位：万元）")
        if days is None:
            problems.append(f"计划工期「{entry.get('计划工期')}」不是有效工期（单位：天）")
        if start is None:
            problems.append(f"计划开始日期「{entry.get('计划开始日期')}」格式应为 YYYY-MM-DD")
        if problems:
            return problems

        assert amount is not None and days is not None and start is not None
        low, high = rule["预算金额"]
        if not low <= amount <= high:
            problems.append(
                f"预算金额 {amount:g} 万元越出「{plan_type}」可接受范围（{_fmt_range(rule['预算金额'], '万元')}）"
            )
        low, high = rule["计划工期"]
        if not low <= days <= high:
            problems.append(
                f"计划工期 {days} 天越出「{plan_type}」可接受范围（{_fmt_range(rule['计划工期'], '天')}）"
            )
        if not problems:
            daily = amount / days
            low, high = rule["日均费用"]
            if not low <= daily <= high:
                problems.append(
                    f"预算金额与计划工期不匹配：日均费用 {daily:.2f} 万元/天，"
                    f"越出「{plan_type}」可接受范围（{_fmt_range(rule['日均费用'], '万元/天')}）"
                )

        conflict = self._find_conflict(entry, start, days)
        if conflict is not None:
            problems.append(
                f"养护对象「{entry.get('养护对象')}」在 {conflict['计划开始日期']} 起已有计划 "
                f"{conflict.get('计划编号')}（{conflict.get('status')}），同一时间段只能有一条计划"
            )
        return problems

    def _find_conflict(self, entry: dict[str, Any], start: date, days: int) -> dict[str, Any] | None:
        """找同一养护对象时间段重叠的在册计划；没有重叠返回 None。"""
        end = start + timedelta(days=days)
        target = str(entry.get("养护对象") or "").strip()
        for other in store.rows(MODULE):
            if other is entry or int(other.get("id", 0)) == int(entry.get("id", 0)):
                continue
            if other.get("status") not in OCCUPYING_STATUSES:
                continue
            if str(other.get("养护对象") or "").strip() != target:
                continue
            other_start = _parse_date(other.get("计划开始日期"))
            other_days = _parse_days(other.get("计划工期"))
            if other_start is None or other_days is None:
                continue
            other_end = other_start + timedelta(days=other_days)
            if start < other_end and other_start < end:
                return other
        return None

    @staticmethod
    def _normalize(entry: dict[str, Any]) -> None:
        """把派生字段对齐：计划状态跟着流转状态走，金额工期统一口径。"""
        entry["计划状态"] = entry.get("status", "")
        amount = _parse_amount(entry.get("预算金额"))
        if amount is not None:
            entry["预算金额"] = amount
        days = _parse_days(entry.get("计划工期"))
        if days is not None:
            entry["计划工期"] = f"{days}天"
        entry.setdefault("驳回理由", "")
