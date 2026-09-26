"""养护计划业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "plan"
REQUIRED_FIELDS = ["计划编号", "养护类型", "养护对象"]
STATUS_ORDER = ["待编制", "待审批", "已批复", "已驳回", "已作废"]
ACTION_RULES = {"提交审批": "待审批", "确认批复": "已批复", "作废计划": "已作废"}
NEGATIVE_ACTIONS = ["作废计划"]

# 只有编制中或被驳回的计划能（重新）提交审批
SUBMIT_SOURCES = {"待编制", "已驳回"}
# 只有还没进入审批流的计划允许修改
EDITABLE_STATUSES = {"待编制", "已驳回"}
# 已提交或已批复的计划会占用养护对象的时间段，用来拦同期重复计划
OCCUPYING_STATUSES = {"待审批", "已批复"}
# 登记与修改时允许写入的字段
EDITABLE_FIELDS = [
    "计划编号", "养护类型", "养护对象", "计划开始日期",
    "计划工期", "预算金额", "编制人员", "审批人员",
]

# 判定口径：按养护类型给出预算金额（万元）与计划工期（天）的可接受范围；
# 日均费用（万元/天）用来拦金额与工期单看都合格、合在一起却彼此冲突的计划。
PLAN_RULES: dict[str, dict[str, float]] = {
    "日常保洁": {"预算下限": 0.5, "预算上限": 5.0, "工期下限": 1, "工期上限": 15, "日均下限": 0.05, "日均上限": 2.0},
    "坑槽修补": {"预算下限": 1.0, "预算上限": 20.0, "工期下限": 3, "工期上限": 30, "日均下限": 0.1, "日均上限": 3.0},
    "裂缝处置": {"预算下限": 0.5, "预算上限": 10.0, "工期下限": 1, "工期上限": 20, "日均下限": 0.05, "日均上限": 2.0},
    "桥梁检测": {"预算下限": 5.0, "预算上限": 50.0, "工期下限": 7, "工期上限": 60, "日均下限": 0.2, "日均上限": 5.0},
    "专项大修": {"预算下限": 20.0, "预算上限": 500.0, "工期下限": 30, "工期上限": 180, "日均下限": 0.5, "日均上限": 10.0},
}


def _is_blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _parse_amount(value: Any) -> float | None:
    """把预算金额解析成万元数值；接受「12.5」「12.5万」「12.5万元」等写法。"""
    if _is_blank(value):
        return None
    text = str(value).strip().replace(",", "").removesuffix("万元").removesuffix("万").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_days(value: Any) -> int | None:
    """把计划工期解析成天数；接受「20」「20天」等写法。"""
    if _is_blank(value):
        return None
    text = str(value).strip().removesuffix("天").strip()
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    """把计划开始日期解析成日期；接受 2026-10-08 或 2026/10/08。"""
    if _is_blank(value):
        return None
    try:
        return date.fromisoformat(str(value).strip().replace("/", "-"))
    except ValueError:
        return None


def _period_end(start: date, days: int) -> date:
    return start + timedelta(days=days)


def validate_submission(entry: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    """提交审批前的判定口径：返回拦下原因列表，空列表表示可以进入审批。

    每条原因都要说清是哪一头不合适：金额、工期、两者冲突，还是时间段撞车。
    """
    problems: list[str] = []
    plan_type = str(entry.get("养护类型") or "").strip()
    rule = PLAN_RULES.get(plan_type)
    if rule is None:
        problems.append(f"养护类型「{plan_type or '未填写'}」未配置判定口径，无法判定预算与工期是否合适")

    amount_raw = entry.get("预算金额")
    amount: float | None = None
    if _is_blank(amount_raw):
        problems.append("预算金额未填写，金额漏填的计划不许提交")
    else:
        amount = _parse_amount(amount_raw)
        if amount is None:
            problems.append(f"预算金额「{amount_raw}」不是有效金额（单位：万元）")

    days_raw = entry.get("计划工期")
    days: int | None = None
    if _is_blank(days_raw):
        problems.append("计划工期未填写，工期漏填的计划不许提交")
    else:
        days = _parse_days(days_raw)
        if days is None:
            problems.append(f"计划工期「{days_raw}」不是有效天数（单位：天）")

    start_raw = entry.get("计划开始日期")
    start: date | None = None
    if _is_blank(start_raw):
        problems.append("计划开始日期未填写，无法判定计划所处的时间段")
    else:
        start = _parse_date(start_raw)
        if start is None:
            problems.append(f"计划开始日期「{start_raw}」格式应为 YYYY-MM-DD")

    if rule is not None and amount is not None and not rule["预算下限"] <= amount <= rule["预算上限"]:
        problems.append(
            f"预算金额 {amount:g} 万元越出「{plan_type}」口径"
            f"（{rule['预算下限']:g}–{rule['预算上限']:g} 万元）"
        )
    if rule is not None and days is not None and not rule["工期下限"] <= days <= rule["工期上限"]:
        problems.append(
            f"计划工期 {days:g} 天越出「{plan_type}」口径"
            f"（{rule['工期下限']:g}–{rule['工期上限']:g} 天）"
        )
    if rule is not None and amount is not None and days is not None and days > 0:
        daily = amount / days
        if not rule["日均下限"] <= daily <= rule["日均上限"]:
            problems.append(
                f"预算金额与计划工期彼此冲突：日均 {daily:.2f} 万元/天，"
                f"越出「{plan_type}」日均口径（{rule['日均下限']:g}–{rule['日均上限']:g} 万元/天）"
            )

    if start is not None and days is not None:
        problems.extend(_period_conflicts(entry, rows, start, days))
    return problems


def _period_conflicts(
    entry: dict[str, Any],
    rows: list[dict[str, Any]],
    start: date,
    days: int,
) -> list[str]:
    """同一养护对象在同一时间段只允许一条在途计划（待审批、已批复）。"""
    target = str(entry.get("养护对象") or "").strip()
    end = _period_end(start, days)
    conflicts: list[str] = []
    for other in rows:
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
        other_end = _period_end(other_start, other_days)
        if start < other_end and other_start < end:
            conflicts.append(
                f"养护对象「{target}」在 {other_start.isoformat()}~{other_end.isoformat()} "
                f"已有计划「{other.get('计划编号', '')}」（{other.get('status')}），"
                "同一时间段只能有一条计划"
            )
    return conflicts


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

    def get_detail(self, entry_id: int) -> dict[str, Any] | None:
        """详情页数据：在原始字段上补出计划结束日期、日均预算与命中口径，

        详情页展示的工期、状态、驳回理由都取自同一条记录，保证处处对得上。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        detail = dict(entry)
        start = _parse_date(entry.get("计划开始日期"))
        days = _parse_days(entry.get("计划工期"))
        amount = _parse_amount(entry.get("预算金额"))
        detail["计划结束日期"] = _period_end(start, days).isoformat() if start and days else ""
        detail["日均预算"] = round(amount / days, 2) if amount is not None and days else None
        detail["判定口径"] = PLAN_RULES.get(str(entry.get("养护类型") or "").strip())
        return detail

    def list_rules(self) -> list[dict[str, Any]]:
        """把判定口径摊开给前端，登记时照着范围填，少被拦。"""
        return [{"养护类型": name, **rule} for name, rule in PLAN_RULES.items()]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if _is_blank(values.get(field))]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in EDITABLE_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["计划状态"] = STATUS_ORDER[0]
        entry["驳回理由"] = ""
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """修改计划：被拦下的计划改完回到待编制，可以接着重新提交审批。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护计划 {entry_id} 不存在或已归档"
        if entry.get("status") not in EDITABLE_STATUSES:
            return None, f"计划当前状态为「{entry.get('status')}」，只有待编制或已驳回的计划允许修改"
        merged = dict(entry)
        merged.update({field: values[field] for field in EDITABLE_FIELDS if field in values})
        missing = [field for field in REQUIRED_FIELDS if _is_blank(merged.get(field))]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        entry.update({field: merged[field] for field in EDITABLE_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["计划状态"] = STATUS_ORDER[0]
        entry["驳回理由"] = ""
        entry["pending"] = True
        entry["abnormal"] = False
        return entry, "养护计划已修改并回到待编制，可重新提交审批"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护计划 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护计划可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if action == "提交审批":
            if entry.get("status") not in SUBMIT_SOURCES:
                return None, f"计划当前状态为「{entry.get('status')}」，只有待编制或已驳回的计划能提交审批"
            problems = validate_submission(entry, store.rows(MODULE))
            if problems:
                # 先拦下：状态置为已驳回，理由写清是哪一头不合适，不进审批流
                entry["status"] = "已驳回"
                entry["计划状态"] = "已驳回"
                entry["驳回理由"] = "；".join(problems)
                entry["pending"] = True
                entry["abnormal"] = True
                return entry, f"养护计划未通过提交校验，已拦下：{entry['驳回理由']}"
        entry["status"] = target
        entry["计划状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        # 驳回理由只跟着已驳回状态走，其余状态一律清空，保证状态与理由对得上
        entry["驳回理由"] = ""
        return entry, f"养护计划已{action}"
