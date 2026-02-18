from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any

from django.core.cache import cache
from django.db import transaction

from core.api.exceptions import DomainValidationError
from core.utils.constants import EmployeeLevel
from rules.models import RulesConfigAction, RulesConfigState, RulesConfigVersion


class RulesService:
    """Central rules registry with validation, versioning, rollback, and caching."""

    RULES_CONFIG_CACHE_PREFIX = "rules:active-config:"

    @staticmethod
    def default_rules_config() -> dict[str, Any]:
        return {
            "ticket_xp": {
                "base_divisor": 20,
                "first_pass_bonus": 1,
                "qc_status_update_xp": 1,
                "flag_green_max_minutes": 30,
                "flag_yellow_max_minutes": 60,
            },
            "attendance": {
                "on_time_xp": 2,
                "grace_xp": 0,
                "late_xp": -1,
                "on_time_cutoff": "10:00",
                "grace_cutoff": "10:20",
                "timezone": "Asia/Tashkent",
            },
            "work_session": {
                "daily_pause_limit_minutes": 30,
                "timezone": "Asia/Tashkent",
            },
            "progression": {
                "level_thresholds": {
                    str(int(EmployeeLevel.L1)): 0,
                    str(int(EmployeeLevel.L2)): 200,
                    str(int(EmployeeLevel.L3)): 450,
                    str(int(EmployeeLevel.L4)): 750,
                    str(int(EmployeeLevel.L5)): 1100,
                },
                "weekly_coupon_amount": 100_000,
                "weekly_target_xp": 100,
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
            raise DomainValidationError(f"{field} must be an integer.")
        if not allow_negative and value < 0:
            raise DomainValidationError(f"{field} must be >= 0.")
        return value

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
            raise DomainValidationError("config must be a JSON object.")

        allowed_keys = {"ticket_xp", "attendance", "work_session", "progression"}
        unknown_keys = sorted(set(raw_config.keys()) - allowed_keys)
        if unknown_keys:
            raise DomainValidationError(
                f"Unknown config keys: {', '.join(unknown_keys)}."
            )

        defaults = cls.default_rules_config()
        ticket_xp = raw_config.get("ticket_xp")
        attendance = raw_config.get("attendance")
        work_session = raw_config.get("work_session")
        progression = raw_config.get("progression", defaults["progression"])

        if not isinstance(ticket_xp, dict):
            raise DomainValidationError("ticket_xp must be an object.")
        if not isinstance(attendance, dict):
            raise DomainValidationError("attendance must be an object.")
        if not isinstance(work_session, dict):
            raise DomainValidationError("work_session must be an object.")
        if not isinstance(progression, dict):
            raise DomainValidationError("progression must be an object.")

        base_divisor = cls._require_int(
            ticket_xp.get("base_divisor"), field="ticket_xp.base_divisor"
        )
        if base_divisor <= 0:
            raise DomainValidationError("ticket_xp.base_divisor must be > 0.")
        first_pass_bonus = cls._require_int(
            ticket_xp.get("first_pass_bonus"), field="ticket_xp.first_pass_bonus"
        )
        qc_status_update_xp = cls._require_int(
            ticket_xp.get("qc_status_update_xp", 1),
            field="ticket_xp.qc_status_update_xp",
        )
        flag_green_max_minutes = cls._require_int(
            ticket_xp.get("flag_green_max_minutes", 30),
            field="ticket_xp.flag_green_max_minutes",
        )
        flag_yellow_max_minutes = cls._require_int(
            ticket_xp.get("flag_yellow_max_minutes", 60),
            field="ticket_xp.flag_yellow_max_minutes",
        )
        if flag_yellow_max_minutes < flag_green_max_minutes:
            raise DomainValidationError(
                "ticket_xp.flag_yellow_max_minutes must be >= ticket_xp.flag_green_max_minutes."
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
            raise DomainValidationError(
                "attendance.on_time_cutoff must be in HH:MM format."
            )
        if (
            not isinstance(grace_cutoff, str)
            or len(grace_cutoff) != 5
            or grace_cutoff[2] != ":"
        ):
            raise DomainValidationError(
                "attendance.grace_cutoff must be in HH:MM format."
            )
        if on_time_cutoff > grace_cutoff:
            raise DomainValidationError(
                "attendance.on_time_cutoff must be <= attendance.grace_cutoff."
            )
        if not isinstance(timezone_value, str) or not timezone_value.strip():
            raise DomainValidationError(
                "attendance.timezone must be a non-empty string."
            )

        daily_pause_limit_minutes = cls._require_int(
            work_session.get("daily_pause_limit_minutes"),
            field="work_session.daily_pause_limit_minutes",
        )
        work_session_timezone = work_session.get("timezone")
        if (
            not isinstance(work_session_timezone, str)
            or not work_session_timezone.strip()
        ):
            raise DomainValidationError(
                "work_session.timezone must be a non-empty string."
            )

        default_progression = defaults["progression"]
        thresholds_raw = progression.get(
            "level_thresholds", default_progression["level_thresholds"]
        )
        if not isinstance(thresholds_raw, dict):
            raise DomainValidationError("progression.level_thresholds must be an object.")

        normalized_thresholds: dict[str, int] = {}
        last_threshold = 0
        for level in EmployeeLevel.values:
            level_int = int(level)
            default_threshold = int(default_progression["level_thresholds"][str(level_int)])
            raw_threshold = thresholds_raw.get(str(level_int), thresholds_raw.get(level_int))
            if raw_threshold is None:
                parsed_threshold = default_threshold
            else:
                try:
                    parsed_threshold = int(raw_threshold)
                except (TypeError, ValueError) as exc:
                    raise DomainValidationError(
                        f"progression.level_thresholds.{level_int} must be an integer."
                    ) from exc

            if parsed_threshold < 0:
                raise DomainValidationError(
                    f"progression.level_thresholds.{level_int} must be >= 0."
                )
            if level_int == int(EmployeeLevel.L1):
                parsed_threshold = 0
            if parsed_threshold < last_threshold:
                parsed_threshold = last_threshold
            normalized_thresholds[str(level_int)] = parsed_threshold
            last_threshold = parsed_threshold

        weekly_coupon_amount = cls._require_int(
            progression.get(
                "weekly_coupon_amount", default_progression["weekly_coupon_amount"]
            ),
            field="progression.weekly_coupon_amount",
        )
        weekly_target_xp = cls._require_int(
            progression.get("weekly_target_xp", default_progression["weekly_target_xp"]),
            field="progression.weekly_target_xp",
        )

        return {
            "ticket_xp": {
                "base_divisor": base_divisor,
                "first_pass_bonus": first_pass_bonus,
                "qc_status_update_xp": qc_status_update_xp,
                "flag_green_max_minutes": flag_green_max_minutes,
                "flag_yellow_max_minutes": flag_yellow_max_minutes,
            },
            "attendance": {
                "on_time_xp": on_time_xp,
                "grace_xp": grace_xp,
                "late_xp": late_xp,
                "on_time_cutoff": on_time_cutoff,
                "grace_cutoff": grace_cutoff,
                "timezone": timezone_value,
            },
            "work_session": {
                "daily_pause_limit_minutes": daily_pause_limit_minutes,
                "timezone": work_session_timezone,
            },
            "progression": {
                "level_thresholds": normalized_thresholds,
                "weekly_coupon_amount": weekly_coupon_amount,
                "weekly_target_xp": weekly_target_xp,
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
            raise DomainValidationError("No config changes detected.")

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
            raise DomainValidationError("Target version does not exist.")
        if target_version.id == current_version.id:
            raise DomainValidationError("Target version is already active.")

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
