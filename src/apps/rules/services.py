from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.db.models import Max

from core.utils.constants import EmployeeLevel
from rules.models import RulesConfigAction, RulesConfigState, RulesConfigVersion


def default_rules_config() -> dict[str, Any]:
    level_caps = {
        str(EmployeeLevel.L1): 167,
        str(EmployeeLevel.L2): 267,
        str(EmployeeLevel.L3): 400,
        str(EmployeeLevel.L4): 433,
        str(EmployeeLevel.L5): 500,
    }
    level_allowances = {
        str(EmployeeLevel.L1): 0,
        str(EmployeeLevel.L2): 200_000,
        str(EmployeeLevel.L3): 1_300_000,
        str(EmployeeLevel.L4): 2_200_000,
        str(EmployeeLevel.L5): 4_000_000,
    }
    return {
        "ticket_xp": {
            "base_divisor": 20,
            "first_pass_bonus": 1,
        },
        "attendance": {
            "on_time_xp": 2,
            "grace_xp": 0,
            "late_xp": -1,
            "on_time_cutoff": "10:00",
            "grace_cutoff": "10:20",
            "timezone": "Asia/Tashkent",
        },
        "payroll": {
            "fix_salary": 3_000_000,
            "bonus_rate": 3_000,
            "level_caps": level_caps,
            "level_allowances": level_allowances,
        },
    }


def _as_stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _checksum(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_as_stable_json(payload).encode("utf-8")).hexdigest()


def _require_int(value: Any, *, field: str, allow_negative: bool = False) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer.")
    if not allow_negative and value < 0:
        raise ValueError(f"{field} must be >= 0.")
    return value


def _normalize_level_map(value: Any, *, field: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")

    normalized: dict[str, int] = {}
    for level in EmployeeLevel.values:
        level_key = str(level)
        raw_value = value.get(level_key, value.get(level))
        if raw_value is None:
            raise ValueError(f"{field}.{level_key} is required.")
        normalized[level_key] = _require_int(raw_value, field=f"{field}.{level_key}")
    return normalized


def validate_and_normalize_rules_config(raw_config: Any) -> dict[str, Any]:
    if not isinstance(raw_config, dict):
        raise ValueError("config must be a JSON object.")

    allowed_keys = {"ticket_xp", "attendance", "payroll"}
    unknown_keys = sorted(set(raw_config.keys()) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"Unknown config keys: {', '.join(unknown_keys)}.")

    ticket_xp = raw_config.get("ticket_xp")
    attendance = raw_config.get("attendance")
    payroll = raw_config.get("payroll")

    if not isinstance(ticket_xp, dict):
        raise ValueError("ticket_xp must be an object.")
    if not isinstance(attendance, dict):
        raise ValueError("attendance must be an object.")
    if not isinstance(payroll, dict):
        raise ValueError("payroll must be an object.")

    base_divisor = _require_int(ticket_xp.get("base_divisor"), field="ticket_xp.base_divisor")
    if base_divisor <= 0:
        raise ValueError("ticket_xp.base_divisor must be > 0.")
    first_pass_bonus = _require_int(ticket_xp.get("first_pass_bonus"), field="ticket_xp.first_pass_bonus")

    on_time_xp = _require_int(attendance.get("on_time_xp"), field="attendance.on_time_xp", allow_negative=True)
    grace_xp = _require_int(attendance.get("grace_xp"), field="attendance.grace_xp", allow_negative=True)
    late_xp = _require_int(attendance.get("late_xp"), field="attendance.late_xp", allow_negative=True)

    on_time_cutoff = attendance.get("on_time_cutoff")
    grace_cutoff = attendance.get("grace_cutoff")
    timezone_value = attendance.get("timezone")
    if not isinstance(on_time_cutoff, str) or len(on_time_cutoff) != 5 or on_time_cutoff[2] != ":":
        raise ValueError("attendance.on_time_cutoff must be in HH:MM format.")
    if not isinstance(grace_cutoff, str) or len(grace_cutoff) != 5 or grace_cutoff[2] != ":":
        raise ValueError("attendance.grace_cutoff must be in HH:MM format.")
    if on_time_cutoff > grace_cutoff:
        raise ValueError("attendance.on_time_cutoff must be <= attendance.grace_cutoff.")
    if not isinstance(timezone_value, str) or not timezone_value.strip():
        raise ValueError("attendance.timezone must be a non-empty string.")

    fix_salary = _require_int(payroll.get("fix_salary"), field="payroll.fix_salary")
    bonus_rate = _require_int(payroll.get("bonus_rate"), field="payroll.bonus_rate")
    level_caps = _normalize_level_map(payroll.get("level_caps"), field="payroll.level_caps")
    level_allowances = _normalize_level_map(payroll.get("level_allowances"), field="payroll.level_allowances")

    return {
        "ticket_xp": {
            "base_divisor": base_divisor,
            "first_pass_bonus": first_pass_bonus,
        },
        "attendance": {
            "on_time_xp": on_time_xp,
            "grace_xp": grace_xp,
            "late_xp": late_xp,
            "on_time_cutoff": on_time_cutoff,
            "grace_cutoff": grace_cutoff,
            "timezone": timezone_value,
        },
        "payroll": {
            "fix_salary": fix_salary,
            "bonus_rate": bonus_rate,
            "level_caps": level_caps,
            "level_allowances": level_allowances,
        },
    }


def _diff_rules(before: Any, after: Any, *, path: str = "") -> dict[str, Any]:
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before.keys()) | set(after.keys()))
        changed: dict[str, Any] = {}
        for key in keys:
            child_path = f"{path}.{key}" if path else str(key)
            if key not in before:
                changed[child_path] = {"before": None, "after": after[key]}
            elif key not in after:
                changed[child_path] = {"before": before[key], "after": None}
            else:
                nested = _diff_rules(before[key], after[key], path=child_path)
                changed.update(nested.get("changes", {}))
        return {"changes": changed}

    if before != after:
        return {"changes": {path or "root": {"before": before, "after": after}}}
    return {"changes": {}}


def _next_version_number() -> int:
    current = RulesConfigVersion.objects.aggregate(max_version=Max("version")).get("max_version") or 0
    return int(current) + 1


@transaction.atomic
def ensure_rules_state() -> RulesConfigState:
    state = RulesConfigState.objects.select_for_update().select_related("active_version").first()
    if state:
        return state

    config = default_rules_config()
    version = RulesConfigVersion.objects.create(
        version=1,
        action=RulesConfigAction.BOOTSTRAP,
        config=config,
        diff={"changes": {}},
        checksum=_checksum(config),
        reason="Bootstrap default rules",
        created_by=None,
        source_version=None,
    )
    return RulesConfigState.objects.create(
        singleton=True,
        active_version=version,
        cache_key=uuid.uuid4().hex,
    )


def get_active_rules_state() -> RulesConfigState:
    with transaction.atomic():
        state = ensure_rules_state()
    return RulesConfigState.objects.select_related("active_version", "active_version__created_by").get(pk=state.pk)


def get_active_rules_config() -> dict[str, Any]:
    state = get_active_rules_state()
    return copy.deepcopy(state.active_version.config)


@transaction.atomic
def update_rules_config(*, config: Any, actor_user_id: int, reason: str | None = None) -> RulesConfigState:
    normalized = validate_and_normalize_rules_config(config)
    state = ensure_rules_state()
    current_version = state.active_version

    if normalized == current_version.config:
        raise ValueError("No config changes detected.")

    diff = _diff_rules(current_version.config, normalized)
    new_version = RulesConfigVersion.objects.create(
        version=_next_version_number(),
        action=RulesConfigAction.UPDATE,
        config=normalized,
        diff=diff,
        checksum=_checksum(normalized),
        reason=reason or "",
        created_by_id=actor_user_id,
        source_version=current_version,
    )

    state.active_version = new_version
    state.cache_key = uuid.uuid4().hex
    state.save(update_fields=["active_version", "cache_key", "updated_at"])
    return RulesConfigState.objects.select_related("active_version", "active_version__created_by").get(pk=state.pk)


@transaction.atomic
def rollback_rules_config(*, target_version_number: int, actor_user_id: int, reason: str | None = None) -> RulesConfigState:
    state = ensure_rules_state()
    current_version = state.active_version
    target_version = RulesConfigVersion.objects.filter(version=target_version_number).first()
    if not target_version:
        raise ValueError("Target version does not exist.")
    if target_version.id == current_version.id:
        raise ValueError("Target version is already active.")

    restored_config = copy.deepcopy(target_version.config)
    diff = _diff_rules(current_version.config, restored_config)
    new_version = RulesConfigVersion.objects.create(
        version=_next_version_number(),
        action=RulesConfigAction.ROLLBACK,
        config=restored_config,
        diff=diff,
        checksum=_checksum(restored_config),
        reason=reason or f"Rollback to version {target_version.version}",
        created_by_id=actor_user_id,
        source_version=target_version,
    )

    state.active_version = new_version
    state.cache_key = uuid.uuid4().hex
    state.save(update_fields=["active_version", "cache_key", "updated_at"])
    return RulesConfigState.objects.select_related("active_version", "active_version__created_by").get(pk=state.pk)


def list_rules_versions(*, limit: int = 50) -> list[RulesConfigVersion]:
    capped_limit = max(1, min(limit, 200))
    return list(
        RulesConfigVersion.objects.select_related("created_by", "source_version").order_by("-version")[:capped_limit]
    )
