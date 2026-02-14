from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import date
from typing import Any

from django.core.cache import cache
from django.db import transaction

from core.utils.constants import EmployeeLevel
from rules.models import RulesConfigAction, RulesConfigState, RulesConfigVersion


class RulesService:
    """Central rules registry with validation, versioning, rollback, and caching."""

    RULES_CONFIG_CACHE_PREFIX = "rules:active-config:"

    @staticmethod
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
            "progression": {
                "level_thresholds": {
                    str(EmployeeLevel.L1): 0,
                    str(EmployeeLevel.L2): 200,
                    str(EmployeeLevel.L3): 450,
                    str(EmployeeLevel.L4): 750,
                    str(EmployeeLevel.L5): 1_100,
                },
                "weekly_coupon_amount": 100_000,
            },
            "sla": {
                "stockout": {
                    "timezone": "Asia/Tashkent",
                    "business_start_hour": 10,
                    "business_end_hour": 20,
                    "working_weekdays": [1, 2, 3, 4, 5, 6],
                    "holiday_dates": [],
                },
                "allowance_gate": {
                    "enabled": True,
                    "gated_levels": [str(EmployeeLevel.L5)],
                    "min_first_pass_rate_percent": 85,
                    "max_stockout_minutes": 0,
                },
                "automation": {
                    "enabled": True,
                    "cooldown_minutes": 30,
                    "max_open_stockout_minutes": 15,
                    "max_backlog_black_plus_count": 3,
                    "min_first_pass_rate_percent": 85,
                    "min_qc_done_tickets": 5,
                },
                "escalation": {
                    "enabled": True,
                    "default_channels": ["telegram", "email", "ops_webhook"],
                    "routes": [],
                },
            },
        }

    @staticmethod
    def _as_stable_json(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    @classmethod
    def _checksum(cls, payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls._as_stable_json(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _require_int(value: Any, *, field: str, allow_negative: bool = False) -> int:
        if not isinstance(value, int):
            raise ValueError(f"{field} must be an integer.")
        if not allow_negative and value < 0:
            raise ValueError(f"{field} must be >= 0.")
        return value

    @classmethod
    def _normalize_level_map(cls, value: Any, *, field: str) -> dict[str, int]:
        if not isinstance(value, dict):
            raise ValueError(f"{field} must be an object.")

        normalized: dict[str, int] = {}
        for level in EmployeeLevel.values:
            level_key = str(level)
            raw_value = value.get(level_key, value.get(level))
            if raw_value is None:
                raise ValueError(f"{field}.{level_key} is required.")
            normalized[level_key] = cls._require_int(
                raw_value, field=f"{field}.{level_key}"
            )
        return normalized

    @staticmethod
    def _validate_level_thresholds(level_thresholds: dict[str, int]) -> None:
        previous_threshold: int | None = None
        for level in EmployeeLevel.values:
            level_key = str(level)
            current_threshold = int(level_thresholds[level_key])
            if level == int(EmployeeLevel.L1) and current_threshold != 0:
                raise ValueError("progression.level_thresholds.1 must be 0.")
            if (
                previous_threshold is not None
                and current_threshold < previous_threshold
            ):
                raise ValueError(
                    "progression.level_thresholds must be non-decreasing by level."
                )
            previous_threshold = current_threshold

    @staticmethod
    def _normalize_sla_gated_levels(value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("sla.allowance_gate.gated_levels must be an array.")

        normalized: set[int] = set()
        for raw_level in value:
            try:
                parsed_level = int(raw_level)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "sla.allowance_gate.gated_levels values must be valid levels."
                ) from exc
            if parsed_level not in EmployeeLevel.values:
                raise ValueError(
                    "sla.allowance_gate.gated_levels values must be valid levels."
                )
            normalized.add(parsed_level)
        return [str(level) for level in sorted(normalized)]

    @staticmethod
    def _normalize_stockout_working_weekdays(value: Any) -> list[int]:
        if not isinstance(value, list):
            raise ValueError("sla.stockout.working_weekdays must be an array.")

        normalized: set[int] = set()
        for raw_day in value:
            try:
                parsed_day = int(raw_day)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "sla.stockout.working_weekdays values must be integers in 1..7."
                ) from exc
            if parsed_day < 1 or parsed_day > 7:
                raise ValueError(
                    "sla.stockout.working_weekdays values must be integers in 1..7."
                )
            normalized.add(parsed_day)

        if not normalized:
            raise ValueError("sla.stockout.working_weekdays must not be empty.")
        return sorted(normalized)

    @staticmethod
    def _normalize_stockout_holiday_dates(value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("sla.stockout.holiday_dates must be an array.")

        normalized: set[str] = set()
        for raw_date in value:
            if not isinstance(raw_date, str):
                raise ValueError(
                    "sla.stockout.holiday_dates values must be YYYY-MM-DD strings."
                )
            candidate = raw_date.strip()
            try:
                parsed_date = date.fromisoformat(candidate)
            except ValueError as exc:
                raise ValueError(
                    "sla.stockout.holiday_dates values must be YYYY-MM-DD strings."
                ) from exc
            normalized.add(parsed_date.isoformat())
        return sorted(normalized)

    @staticmethod
    def _normalize_sla_escalation_channels(value: Any, *, field: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{field} must be an array.")

        allowed = {"telegram", "email", "ops_webhook"}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, str):
                raise ValueError(f"{field} values must be strings.")
            candidate = raw.strip().lower()
            if candidate not in allowed:
                raise ValueError(
                    f"{field} values must be one of: {', '.join(sorted(allowed))}."
                )
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized

    @classmethod
    def _normalize_sla_escalation_routes(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError("sla.escalation.routes must be an array.")

        allowed_keys = {"rule_keys", "severities", "statuses", "repeat", "channels"}
        allowed_statuses = {"triggered", "resolved"}
        allowed_severities = {"warning", "critical"}

        normalized_routes: list[dict[str, Any]] = []
        for idx, raw in enumerate(value):
            if not isinstance(raw, dict):
                raise ValueError(f"sla.escalation.routes[{idx}] must be an object.")
            unknown = sorted(set(raw.keys()) - allowed_keys)
            if unknown:
                raise ValueError(
                    f"sla.escalation.routes[{idx}] has unknown keys: {', '.join(unknown)}."
                )

            raw_channels = raw.get("channels")
            channels = cls._normalize_sla_escalation_channels(
                raw_channels, field=f"sla.escalation.routes[{idx}].channels"
            )

            rule_keys: list[str] | None = None
            if "rule_keys" in raw:
                raw_rule_keys = raw.get("rule_keys")
                if not isinstance(raw_rule_keys, list):
                    raise ValueError(
                        f"sla.escalation.routes[{idx}].rule_keys must be an array."
                    )
                cleaned: list[str] = []
                for rk in raw_rule_keys:
                    if not isinstance(rk, str):
                        raise ValueError(
                            f"sla.escalation.routes[{idx}].rule_keys values must be strings."
                        )
                    candidate = rk.strip()
                    if candidate:
                        cleaned.append(candidate)
                rule_keys = cleaned

            severities: list[str] | None = None
            if "severities" in raw:
                raw_severities = raw.get("severities")
                if not isinstance(raw_severities, list):
                    raise ValueError(
                        f"sla.escalation.routes[{idx}].severities must be an array."
                    )
                cleaned_severities: list[str] = []
                for sev in raw_severities:
                    if not isinstance(sev, str):
                        raise ValueError(
                            f"sla.escalation.routes[{idx}].severities values must be strings."
                        )
                    candidate = sev.strip().lower()
                    if candidate and candidate not in allowed_severities:
                        raise ValueError(
                            f"sla.escalation.routes[{idx}].severities values must be one of: "
                            f"{', '.join(sorted(allowed_severities))}."
                        )
                    if candidate:
                        cleaned_severities.append(candidate)
                severities = cleaned_severities

            statuses: list[str] | None = None
            if "statuses" in raw:
                raw_statuses = raw.get("statuses")
                if not isinstance(raw_statuses, list):
                    raise ValueError(
                        f"sla.escalation.routes[{idx}].statuses must be an array."
                    )
                cleaned_statuses: list[str] = []
                for st in raw_statuses:
                    if not isinstance(st, str):
                        raise ValueError(
                            f"sla.escalation.routes[{idx}].statuses values must be strings."
                        )
                    candidate = st.strip().lower()
                    if candidate and candidate not in allowed_statuses:
                        raise ValueError(
                            f"sla.escalation.routes[{idx}].statuses values must be one of: "
                            f"{', '.join(sorted(allowed_statuses))}."
                        )
                    if candidate:
                        cleaned_statuses.append(candidate)
                statuses = cleaned_statuses

            repeat: bool | None = None
            if "repeat" in raw:
                raw_repeat = raw.get("repeat")
                if not isinstance(raw_repeat, bool):
                    raise ValueError(
                        f"sla.escalation.routes[{idx}].repeat must be boolean."
                    )
                repeat = raw_repeat

            # Only explicit filters are persisted so route matching stays predictable.
            normalized_route: dict[str, Any] = {
                "channels": channels,
            }
            if rule_keys is not None:
                normalized_route["rule_keys"] = rule_keys
            if severities is not None:
                normalized_route["severities"] = severities
            if statuses is not None:
                normalized_route["statuses"] = statuses
            if repeat is not None:
                normalized_route["repeat"] = repeat
            normalized_routes.append(normalized_route)

        return normalized_routes

    @classmethod
    def _cache_storage_key(cls, state_cache_key: str) -> str:
        return f"{cls.RULES_CONFIG_CACHE_PREFIX}{state_cache_key}"

    @classmethod
    def _set_cached_active_config(
        cls, *, state_cache_key: str, config_payload: dict[str, Any]
    ) -> None:
        cache.set(
            cls._cache_storage_key(state_cache_key),
            copy.deepcopy(config_payload),
            timeout=None,
        )

    @classmethod
    def _invalidate_cached_active_config(cls, *, state_cache_key: str) -> None:
        cache.delete(cls._cache_storage_key(state_cache_key))

    @classmethod
    def validate_and_normalize_rules_config(cls, raw_config: Any) -> dict[str, Any]:
        if not isinstance(raw_config, dict):
            raise ValueError("config must be a JSON object.")

        allowed_keys = {"ticket_xp", "attendance", "payroll", "progression", "sla"}
        unknown_keys = sorted(set(raw_config.keys()) - allowed_keys)
        if unknown_keys:
            raise ValueError(f"Unknown config keys: {', '.join(unknown_keys)}.")

        ticket_xp = raw_config.get("ticket_xp")
        attendance = raw_config.get("attendance")
        payroll = raw_config.get("payroll")
        progression = raw_config.get("progression")
        default_sla_config = cls.default_rules_config()["sla"]
        sla = raw_config.get("sla", default_sla_config)

        if not isinstance(ticket_xp, dict):
            raise ValueError("ticket_xp must be an object.")
        if not isinstance(attendance, dict):
            raise ValueError("attendance must be an object.")
        if not isinstance(payroll, dict):
            raise ValueError("payroll must be an object.")
        if not isinstance(progression, dict):
            raise ValueError("progression must be an object.")
        if not isinstance(sla, dict):
            raise ValueError("sla must be an object.")

        base_divisor = cls._require_int(
            ticket_xp.get("base_divisor"), field="ticket_xp.base_divisor"
        )
        if base_divisor <= 0:
            raise ValueError("ticket_xp.base_divisor must be > 0.")
        first_pass_bonus = cls._require_int(
            ticket_xp.get("first_pass_bonus"), field="ticket_xp.first_pass_bonus"
        )

        on_time_xp = cls._require_int(
            attendance.get("on_time_xp"),
            field="attendance.on_time_xp",
            allow_negative=True,
        )
        grace_xp = cls._require_int(
            attendance.get("grace_xp"),
            field="attendance.grace_xp",
            allow_negative=True,
        )
        late_xp = cls._require_int(
            attendance.get("late_xp"), field="attendance.late_xp", allow_negative=True
        )

        on_time_cutoff = attendance.get("on_time_cutoff")
        grace_cutoff = attendance.get("grace_cutoff")
        timezone_value = attendance.get("timezone")
        if (
            not isinstance(on_time_cutoff, str)
            or len(on_time_cutoff) != 5
            or on_time_cutoff[2] != ":"
        ):
            raise ValueError("attendance.on_time_cutoff must be in HH:MM format.")
        if (
            not isinstance(grace_cutoff, str)
            or len(grace_cutoff) != 5
            or grace_cutoff[2] != ":"
        ):
            raise ValueError("attendance.grace_cutoff must be in HH:MM format.")
        if on_time_cutoff > grace_cutoff:
            raise ValueError(
                "attendance.on_time_cutoff must be <= attendance.grace_cutoff."
            )
        if not isinstance(timezone_value, str) or not timezone_value.strip():
            raise ValueError("attendance.timezone must be a non-empty string.")

        fix_salary = cls._require_int(
            payroll.get("fix_salary"), field="payroll.fix_salary"
        )
        bonus_rate = cls._require_int(
            payroll.get("bonus_rate"), field="payroll.bonus_rate"
        )
        level_caps = cls._normalize_level_map(
            payroll.get("level_caps"), field="payroll.level_caps"
        )
        level_allowances = cls._normalize_level_map(
            payroll.get("level_allowances"), field="payroll.level_allowances"
        )
        level_thresholds = cls._normalize_level_map(
            progression.get("level_thresholds"), field="progression.level_thresholds"
        )
        cls._validate_level_thresholds(level_thresholds)
        weekly_coupon_amount = cls._require_int(
            progression.get("weekly_coupon_amount"),
            field="progression.weekly_coupon_amount",
        )

        stockout = sla.get("stockout", default_sla_config["stockout"])
        if not isinstance(stockout, dict):
            raise ValueError("sla.stockout must be an object.")
        default_stockout = default_sla_config["stockout"]
        stockout_timezone = stockout.get("timezone")
        if not isinstance(stockout_timezone, str) or not stockout_timezone.strip():
            raise ValueError("sla.stockout.timezone must be a non-empty string.")
        stockout_start_hour = cls._require_int(
            stockout.get(
                "business_start_hour",
                default_stockout["business_start_hour"],
            ),
            field="sla.stockout.business_start_hour",
        )
        stockout_end_hour = cls._require_int(
            stockout.get(
                "business_end_hour",
                default_stockout["business_end_hour"],
            ),
            field="sla.stockout.business_end_hour",
        )
        if stockout_start_hour < 0 or stockout_start_hour > 23:
            raise ValueError("sla.stockout.business_start_hour must be in 0..23.")
        if stockout_end_hour < 1 or stockout_end_hour > 24:
            raise ValueError("sla.stockout.business_end_hour must be in 1..24.")
        if stockout_start_hour >= stockout_end_hour:
            raise ValueError(
                "sla.stockout.business_start_hour must be < business_end_hour."
            )
        stockout_working_weekdays = cls._normalize_stockout_working_weekdays(
            stockout.get("working_weekdays", default_stockout["working_weekdays"])
        )
        stockout_holiday_dates = cls._normalize_stockout_holiday_dates(
            stockout.get("holiday_dates", default_stockout["holiday_dates"])
        )

        allowance_gate = sla.get("allowance_gate", default_sla_config["allowance_gate"])
        if not isinstance(allowance_gate, dict):
            raise ValueError("sla.allowance_gate must be an object.")
        allowance_gate_enabled = allowance_gate.get("enabled")
        if not isinstance(allowance_gate_enabled, bool):
            raise ValueError("sla.allowance_gate.enabled must be boolean.")
        allowance_gate_levels = cls._normalize_sla_gated_levels(
            allowance_gate.get("gated_levels", [])
        )
        min_first_pass_rate_percent = cls._require_int(
            allowance_gate.get("min_first_pass_rate_percent"),
            field="sla.allowance_gate.min_first_pass_rate_percent",
        )
        if min_first_pass_rate_percent < 0 or min_first_pass_rate_percent > 100:
            raise ValueError(
                "sla.allowance_gate.min_first_pass_rate_percent must be in 0..100."
            )
        max_stockout_minutes = cls._require_int(
            allowance_gate.get("max_stockout_minutes"),
            field="sla.allowance_gate.max_stockout_minutes",
        )

        automation = sla.get("automation", default_sla_config.get("automation", {}))
        if not isinstance(automation, dict):
            raise ValueError("sla.automation must be an object.")
        automation_enabled = automation.get("enabled")
        if not isinstance(automation_enabled, bool):
            raise ValueError("sla.automation.enabled must be boolean.")
        automation_cooldown_minutes = cls._require_int(
            automation.get("cooldown_minutes"),
            field="sla.automation.cooldown_minutes",
        )
        max_open_stockout_minutes = cls._require_int(
            automation.get("max_open_stockout_minutes"),
            field="sla.automation.max_open_stockout_minutes",
        )
        max_backlog_black_plus_count = cls._require_int(
            automation.get("max_backlog_black_plus_count"),
            field="sla.automation.max_backlog_black_plus_count",
        )
        automation_min_first_pass_rate_percent = cls._require_int(
            automation.get("min_first_pass_rate_percent"),
            field="sla.automation.min_first_pass_rate_percent",
        )
        if (
            automation_min_first_pass_rate_percent < 0
            or automation_min_first_pass_rate_percent > 100
        ):
            raise ValueError(
                "sla.automation.min_first_pass_rate_percent must be in 0..100."
            )
        min_qc_done_tickets = cls._require_int(
            automation.get("min_qc_done_tickets"),
            field="sla.automation.min_qc_done_tickets",
        )

        escalation = sla.get("escalation", default_sla_config.get("escalation", {}))
        if not isinstance(escalation, dict):
            raise ValueError("sla.escalation must be an object.")
        escalation_enabled = escalation.get("enabled")
        if not isinstance(escalation_enabled, bool):
            raise ValueError("sla.escalation.enabled must be boolean.")
        default_channels = cls._normalize_sla_escalation_channels(
            escalation.get(
                "default_channels",
                default_sla_config.get("escalation", {}).get("default_channels", []),
            ),
            field="sla.escalation.default_channels",
        )
        routes = cls._normalize_sla_escalation_routes(escalation.get("routes", []))

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
            "progression": {
                "level_thresholds": level_thresholds,
                "weekly_coupon_amount": weekly_coupon_amount,
            },
            "sla": {
                "stockout": {
                    "timezone": stockout_timezone.strip(),
                    "business_start_hour": stockout_start_hour,
                    "business_end_hour": stockout_end_hour,
                    "working_weekdays": stockout_working_weekdays,
                    "holiday_dates": stockout_holiday_dates,
                },
                "allowance_gate": {
                    "enabled": allowance_gate_enabled,
                    "gated_levels": allowance_gate_levels,
                    "min_first_pass_rate_percent": min_first_pass_rate_percent,
                    "max_stockout_minutes": max_stockout_minutes,
                },
                "automation": {
                    "enabled": automation_enabled,
                    "cooldown_minutes": automation_cooldown_minutes,
                    "max_open_stockout_minutes": max_open_stockout_minutes,
                    "max_backlog_black_plus_count": max_backlog_black_plus_count,
                    "min_first_pass_rate_percent": (
                        automation_min_first_pass_rate_percent
                    ),
                    "min_qc_done_tickets": min_qc_done_tickets,
                },
                "escalation": {
                    "enabled": escalation_enabled,
                    "default_channels": default_channels,
                    "routes": routes,
                },
            },
        }

    @classmethod
    def _diff_rules(cls, before: Any, after: Any, *, path: str = "") -> dict[str, Any]:
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
                    nested = cls._diff_rules(before[key], after[key], path=child_path)
                    changed.update(nested.get("changes", {}))
            return {"changes": changed}

        if before != after:
            return {"changes": {path or "root": {"before": before, "after": after}}}
        return {"changes": {}}

    @classmethod
    @transaction.atomic
    def ensure_rules_state(cls) -> RulesConfigState:
        state = RulesConfigState.domain.get_singleton_for_update()
        if state:
            return state

        config = cls.default_rules_config()
        version = RulesConfigVersion.domain.create_version_entry(
            action=RulesConfigAction.BOOTSTRAP,
            config=config,
            diff={"changes": {}},
            checksum=cls._checksum(config),
            reason="Bootstrap default rules",
            created_by_id=None,
            source_version=None,
        )
        state = RulesConfigState.domain.create_singleton(
            active_version=version,
            cache_key=uuid.uuid4().hex,
        )
        cls._set_cached_active_config(
            state_cache_key=state.cache_key,
            config_payload=version.config,
        )
        return state

    @classmethod
    def get_active_rules_state(cls) -> RulesConfigState:
        with transaction.atomic():
            state = cls.ensure_rules_state()
        return RulesConfigState.domain.get_with_related(state_id=state.pk)

    @classmethod
    def get_active_rules_config(cls) -> dict[str, Any]:
        state = cls.get_active_rules_state()
        cached = cache.get(cls._cache_storage_key(state.cache_key))
        if isinstance(cached, dict):
            return copy.deepcopy(cached)

        active_config = copy.deepcopy(state.active_version.config)
        cls._set_cached_active_config(
            state_cache_key=state.cache_key,
            config_payload=active_config,
        )
        return copy.deepcopy(active_config)

    @classmethod
    @transaction.atomic
    def update_rules_config(
        cls, *, config: Any, actor_user_id: int, reason: str | None = None
    ) -> RulesConfigState:
        normalized = cls.validate_and_normalize_rules_config(config)
        state = cls.ensure_rules_state()
        previous_cache_key = state.cache_key
        current_version = state.active_version

        if normalized == current_version.config:
            raise ValueError("No config changes detected.")

        diff = cls._diff_rules(current_version.config, normalized)
        new_version = RulesConfigVersion.domain.create_version_entry(
            action=RulesConfigAction.UPDATE,
            config=normalized,
            diff=diff,
            checksum=cls._checksum(normalized),
            reason=reason or "",
            created_by_id=actor_user_id,
            source_version=current_version,
        )

        state.activate_version(active_version=new_version, cache_key=uuid.uuid4().hex)
        cls._invalidate_cached_active_config(state_cache_key=previous_cache_key)
        cls._set_cached_active_config(
            state_cache_key=state.cache_key,
            config_payload=new_version.config,
        )
        return RulesConfigState.domain.get_with_related(state_id=state.pk)

    @classmethod
    @transaction.atomic
    def rollback_rules_config(
        cls,
        *,
        target_version_number: int,
        actor_user_id: int,
        reason: str | None = None,
    ) -> RulesConfigState:
        state = cls.ensure_rules_state()
        previous_cache_key = state.cache_key
        current_version = state.active_version
        target_version = RulesConfigVersion.domain.get_by_version_number(
            version_number=target_version_number
        )
        if not target_version:
            raise ValueError("Target version does not exist.")
        if target_version.id == current_version.id:
            raise ValueError("Target version is already active.")

        restored_config = copy.deepcopy(target_version.config)
        diff = cls._diff_rules(current_version.config, restored_config)
        new_version = RulesConfigVersion.domain.create_version_entry(
            action=RulesConfigAction.ROLLBACK,
            config=restored_config,
            diff=diff,
            checksum=cls._checksum(restored_config),
            reason=reason or f"Rollback to version {target_version.version}",
            created_by_id=actor_user_id,
            source_version=target_version,
        )

        state.activate_version(active_version=new_version, cache_key=uuid.uuid4().hex)
        cls._invalidate_cached_active_config(state_cache_key=previous_cache_key)
        cls._set_cached_active_config(
            state_cache_key=state.cache_key,
            config_payload=new_version.config,
        )
        return RulesConfigState.domain.get_with_related(state_id=state.pk)

    @staticmethod
    def list_rules_versions(*, limit: int = 50) -> list[RulesConfigVersion]:
        return RulesConfigVersion.domain.latest_versions(limit=limit)
