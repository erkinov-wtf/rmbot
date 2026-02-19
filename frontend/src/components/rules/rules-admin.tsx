import {
  History,
  RefreshCcw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import {
  getRulesConfigState,
  listRulesConfigHistory,
  rollbackRulesConfigState,
  updateRulesConfigState,
  type RulesConfig,
  type RulesConfigState,
  type RulesConfigVersion,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type RulesAdminProps = {
  accessToken: string;
  canRead: boolean;
  canWrite: boolean;
  roleSlugs: string[];
};

type FeedbackState =
  | {
      type: "success" | "error";
      message: string;
    }
  | null;

const fieldClassName = "rm-input";
const fieldLabelClassName =
  "flex min-h-[2.25rem] items-end text-xs font-semibold uppercase tracking-wide text-slate-600";

const LEVEL_KEYS = ["1", "2", "3", "4", "5"] as const;

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function toInt(value: unknown, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.trunc(parsed);
}

const defaultRulesConfig: RulesConfig = {
  ticket_xp: {
    base_divisor: 20,
    first_pass_bonus: 1,
    qc_status_update_xp: 1,
    flag_green_max_minutes: 30,
    flag_yellow_max_minutes: 60,
  },
  attendance: {
    on_time_xp: 2,
    grace_xp: 0,
    late_xp: -1,
    on_time_cutoff: "10:00",
    grace_cutoff: "10:20",
    timezone: "Asia/Tashkent",
  },
  work_session: {
    daily_pause_limit_minutes: 30,
    timezone: "Asia/Tashkent",
  },
  progression: {
    level_thresholds: {
      "1": 0,
      "2": 200,
      "3": 450,
      "4": 750,
      "5": 1100,
    },
    weekly_coupon_amount: 100000,
    weekly_target_xp: 100,
  },
};

function normalizeRulesConfig(config: unknown): RulesConfig {
  const root = config && typeof config === "object"
    ? (config as Partial<RulesConfig>)
    : {};
  const ticketXp: Partial<RulesConfig["ticket_xp"]> = (
    root.ticket_xp && typeof root.ticket_xp === "object"
      ? root.ticket_xp
      : {}
  ) as Partial<RulesConfig["ticket_xp"]>;
  const attendance: Partial<RulesConfig["attendance"]> = (
    root.attendance && typeof root.attendance === "object"
      ? root.attendance
      : {}
  ) as Partial<RulesConfig["attendance"]>;
  const workSession: Partial<RulesConfig["work_session"]> = (
    root.work_session && typeof root.work_session === "object"
      ? root.work_session
      : {}
  ) as Partial<RulesConfig["work_session"]>;
  const progression: Partial<NonNullable<RulesConfig["progression"]>> = (
    root.progression && typeof root.progression === "object"
      ? root.progression
      : defaultRulesConfig.progression!
  ) as Partial<NonNullable<RulesConfig["progression"]>>;
  const normalizedThresholds = LEVEL_KEYS.reduce<Record<string, number>>(
    (accumulator, levelKey) => {
      const fallbackValue =
        defaultRulesConfig.progression?.level_thresholds?.[levelKey] ?? 0;
      accumulator[levelKey] = toInt(
        progression.level_thresholds?.[levelKey],
        fallbackValue,
      );
      return accumulator;
    },
    {},
  );
  normalizedThresholds["1"] = 0;

  return {
    ticket_xp: {
      base_divisor: toInt(
        ticketXp.base_divisor,
        defaultRulesConfig.ticket_xp.base_divisor,
      ),
      first_pass_bonus: toInt(
        ticketXp.first_pass_bonus,
        defaultRulesConfig.ticket_xp.first_pass_bonus,
      ),
      qc_status_update_xp: toInt(
        ticketXp.qc_status_update_xp,
        defaultRulesConfig.ticket_xp.qc_status_update_xp,
      ),
      flag_green_max_minutes: toInt(
        ticketXp.flag_green_max_minutes,
        defaultRulesConfig.ticket_xp.flag_green_max_minutes,
      ),
      flag_yellow_max_minutes: toInt(
        ticketXp.flag_yellow_max_minutes,
        defaultRulesConfig.ticket_xp.flag_yellow_max_minutes,
      ),
    },
    attendance: {
      on_time_xp: toInt(
        attendance.on_time_xp,
        defaultRulesConfig.attendance.on_time_xp,
      ),
      grace_xp: toInt(
        attendance.grace_xp,
        defaultRulesConfig.attendance.grace_xp,
      ),
      late_xp: toInt(
        attendance.late_xp,
        defaultRulesConfig.attendance.late_xp,
      ),
      on_time_cutoff:
        attendance.on_time_cutoff ?? defaultRulesConfig.attendance.on_time_cutoff,
      grace_cutoff:
        attendance.grace_cutoff ?? defaultRulesConfig.attendance.grace_cutoff,
      timezone: attendance.timezone ?? defaultRulesConfig.attendance.timezone,
    },
    work_session: {
      daily_pause_limit_minutes: toInt(
        workSession.daily_pause_limit_minutes,
        defaultRulesConfig.work_session.daily_pause_limit_minutes,
      ),
      timezone:
        workSession.timezone ?? defaultRulesConfig.work_session.timezone,
    },
    progression: {
      level_thresholds: normalizedThresholds,
      weekly_coupon_amount: toInt(
        progression.weekly_coupon_amount,
        defaultRulesConfig.progression!.weekly_coupon_amount!,
      ),
      weekly_target_xp: toInt(
        progression.weekly_target_xp,
        defaultRulesConfig.progression!.weekly_target_xp!,
      ),
    },
  };
}

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function diffChangePaths(version: RulesConfigVersion): string[] {
  const diff = version.diff;
  if (!diff || typeof diff !== "object" || !("changes" in diff)) {
    return [];
  }
  const changes = (diff as { changes?: unknown }).changes;
  if (!changes || typeof changes !== "object") {
    return [];
  }
  return Object.keys(changes);
}

function parseIntegerInput(rawValue: string, fallback: number): number {
  if (!rawValue.trim()) {
    return fallback;
  }
  return toInt(rawValue, fallback);
}

export function RulesAdmin({
  accessToken,
  canRead,
  canWrite,
  roleSlugs,
}: RulesAdminProps) {
  const { t } = useI18n();
  const [rulesState, setRulesState] = useState<RulesConfigState | null>(null);
  const [draftConfig, setDraftConfig] = useState<RulesConfig>(defaultRulesConfig);
  const [history, setHistory] = useState<RulesConfigVersion[]>([]);

  const [saveReason, setSaveReason] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [rollbackVersionInput, setRollbackVersionInput] = useState("");

  const [isLoadingState, setIsLoadingState] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRollingBack, setIsRollingBack] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const rollbackOptions = useMemo(() => {
    if (!rulesState) {
      return history;
    }
    return history.filter((row) => row.version !== rulesState.active_version);
  }, [history, rulesState]);

  useEffect(() => {
    if (rollbackOptions.length === 0) {
      setRollbackVersionInput("");
      return;
    }
    setRollbackVersionInput((previous) => {
      const selected = Number(previous);
      if (
        Number.isInteger(selected)
        && rollbackOptions.some((row) => row.version === selected)
      ) {
        return previous;
      }
      return String(rollbackOptions[0].version);
    });
  }, [rollbackOptions]);

  const loadRulesState = useCallback(async () => {
    if (!canRead) {
      setRulesState(null);
      setDraftConfig(defaultRulesConfig);
      return;
    }
    setIsLoadingState(true);
    try {
      const state = await getRulesConfigState(accessToken);
      const normalizedConfig = normalizeRulesConfig(state.config);
      setRulesState({
        ...state,
        config: normalizedConfig,
      });
      setDraftConfig(normalizedConfig);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load active rules config.")),
      });
    } finally {
      setIsLoadingState(false);
    }
  }, [accessToken, canRead, t]);

  const loadRulesHistory = useCallback(async () => {
    if (!canRead) {
      setHistory([]);
      return;
    }
    setIsLoadingHistory(true);
    try {
      const rows = await listRulesConfigHistory(accessToken, {
        per_page: 100,
        ordering: "-version",
      });
      setHistory(rows);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load rules config history.")),
      });
    } finally {
      setIsLoadingHistory(false);
    }
  }, [accessToken, canRead, t]);

  useEffect(() => {
    void Promise.all([loadRulesState(), loadRulesHistory()]);
  }, [loadRulesState, loadRulesHistory]);

  const updateTicketXp = (key: keyof RulesConfig["ticket_xp"], value: string) => {
    setDraftConfig((previous) => ({
      ...previous,
      ticket_xp: {
        ...previous.ticket_xp,
        [key]: parseIntegerInput(value, previous.ticket_xp[key]),
      },
    }));
  };

  const updateAttendance = (key: keyof RulesConfig["attendance"], value: string) => {
    setDraftConfig((previous) => {
      if (key === "on_time_cutoff" || key === "grace_cutoff" || key === "timezone") {
        return {
          ...previous,
          attendance: {
            ...previous.attendance,
            [key]: value,
          },
        };
      }
      const numericKey = key as "on_time_xp" | "grace_xp" | "late_xp";
      return {
        ...previous,
        attendance: {
          ...previous.attendance,
          [numericKey]: parseIntegerInput(value, previous.attendance[numericKey]),
        },
      };
    });
  };

  const updateWorkSession = (
    key: keyof RulesConfig["work_session"],
    value: string,
  ) => {
    setDraftConfig((previous) => {
      if (key === "timezone") {
        return {
          ...previous,
          work_session: {
            ...previous.work_session,
            timezone: value,
          },
        };
      }
      return {
        ...previous,
        work_session: {
          ...previous.work_session,
          daily_pause_limit_minutes: parseIntegerInput(
            value,
            previous.work_session.daily_pause_limit_minutes,
          ),
        },
      };
    });
  };

  const updateProgressionScalar = (
    key: "weekly_target_xp" | "weekly_coupon_amount",
    value: string,
  ) => {
    setDraftConfig((previous) => {
      const progression = previous.progression ?? defaultRulesConfig.progression!;
      return {
        ...previous,
        progression: {
          ...progression,
          [key]: parseIntegerInput(value, progression[key] ?? 0),
        },
      };
    });
  };

  const updateProgressionThreshold = (levelKey: string, value: string) => {
    if (levelKey === "1") {
      return;
    }
    setDraftConfig((previous) => {
      const progression = previous.progression ?? defaultRulesConfig.progression!;
      const currentThresholds =
        progression.level_thresholds ?? defaultRulesConfig.progression!.level_thresholds!;
      return {
        ...previous,
        progression: {
          ...progression,
          level_thresholds: {
            ...currentThresholds,
            [levelKey]: parseIntegerInput(value, currentThresholds[levelKey] ?? 0),
          },
        },
      };
    });
  };

  const handleSaveConfig = async () => {
    if (!canWrite) {
      setFeedback({
        type: "error",
        message: t("Only Super Admin can update rules config."),
      });
      return;
    }
    setIsSaving(true);
    setFeedback(null);
    try {
      const state = await updateRulesConfigState(accessToken, {
        config: draftConfig,
        reason: saveReason.trim() || undefined,
      });
      setFeedback({
        type: "success",
        message: t("Rules config updated. Active version is now v{{version}}.", {
          version: state.active_version,
        }),
      });
      setSaveReason("");
      await Promise.all([loadRulesState(), loadRulesHistory()]);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to update rules config.")),
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRollback = async () => {
    if (!canWrite) {
      setFeedback({
        type: "error",
        message: t("Only Super Admin can rollback rules config."),
      });
      return;
    }
    const targetVersion = Number(rollbackVersionInput);
    if (!Number.isInteger(targetVersion) || targetVersion < 1) {
      setFeedback({
        type: "error",
        message: t("Select a valid target version for rollback."),
      });
      return;
    }

    setIsRollingBack(true);
    setFeedback(null);
    try {
      const state = await rollbackRulesConfigState(accessToken, {
        target_version: targetVersion,
        reason: rollbackReason.trim() || undefined,
      });
      setFeedback({
        type: "success",
        message: t("Rollback completed. Active version is now v{{version}}.", {
          version: state.active_version,
        }),
      });
      setRollbackReason("");
      await Promise.all([loadRulesState(), loadRulesHistory()]);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to rollback rules config.")),
      });
    } finally {
      setIsRollingBack(false);
    }
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Rules Config")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Manage business values from DB-backed rules versions without code changes.")}
          </p>
          {!canRead ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot view rules config.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : !canWrite ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Read-only mode. Only Super Admin can update or rollback.")}
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-10 w-full sm:w-auto"
          disabled={
            !canRead
            || isLoadingState
            || isLoadingHistory
            || isSaving
            || isRollingBack
          }
          onClick={() => {
            setFeedback(null);
            void Promise.all([loadRulesState(), loadRulesHistory()]);
          }}
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          {t("Refresh")}
        </Button>
      </div>

      {feedback ? (
        <p
          className={cn(
            "mt-4 rounded-xl border px-3 py-2 text-sm",
            feedback.type === "error"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700",
          )}
        >
          {feedback.message}
        </p>
      ) : null}

      {!canRead ? (
        <p className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-600">
          {t("Rules config is available only for Super Admin and Ops Manager.")}
        </p>
      ) : (
        <div className="mt-4 space-y-5">
          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rm-subpanel p-4 sm:p-5">
              <p className="rm-card-title">{t("Ticket XP")}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <label className={fieldLabelClassName}>
                    {t("Base divisor")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.ticket_xp.base_divisor}
                    onChange={(event) => {
                      updateTicketXp("base_divisor", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>

                <div>
                  <label className={fieldLabelClassName}>
                    {t("First-pass bonus")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.ticket_xp.first_pass_bonus}
                    onChange={(event) => {
                      updateTicketXp("first_pass_bonus", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>

                <div>
                  <label className={fieldLabelClassName}>
                    {t("QC status XP")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.ticket_xp.qc_status_update_xp}
                    onChange={(event) => {
                      updateTicketXp("qc_status_update_xp", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>

                <div>
                  <label className={fieldLabelClassName}>
                    {t("Green max minutes")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.ticket_xp.flag_green_max_minutes}
                    onChange={(event) => {
                      updateTicketXp("flag_green_max_minutes", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>

                <div>
                  <label className={fieldLabelClassName}>
                    {t("Yellow max minutes")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.ticket_xp.flag_yellow_max_minutes}
                    onChange={(event) => {
                      updateTicketXp("flag_yellow_max_minutes", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>
              </div>
            </div>

            <div className="rm-subpanel p-4 sm:p-5">
              <p className="rm-card-title">{t("Work Session")}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={fieldLabelClassName}>
                    {t("Daily pause limit (minutes)")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.work_session.daily_pause_limit_minutes}
                    onChange={(event) => {
                      updateWorkSession("daily_pause_limit_minutes", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>

                <div>
                  <label className={fieldLabelClassName}>
                    {t("Timezone")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    value={draftConfig.work_session.timezone}
                    onChange={(event) => {
                      updateWorkSession("timezone", event.target.value);
                    }}
                    disabled={!canWrite || isSaving || isRollingBack}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="rm-subpanel p-4 sm:p-5">
            <p className="rm-card-title">{t("Attendance")}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div>
                <label className={fieldLabelClassName}>
                  {t("On-time XP")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="number"
                  value={draftConfig.attendance.on_time_xp}
                  onChange={(event) => {
                    updateAttendance("on_time_xp", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
              <div>
                <label className={fieldLabelClassName}>
                  {t("Grace XP")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="number"
                  value={draftConfig.attendance.grace_xp}
                  onChange={(event) => {
                    updateAttendance("grace_xp", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
              <div>
                <label className={fieldLabelClassName}>
                  {t("Late XP")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="number"
                  value={draftConfig.attendance.late_xp}
                  onChange={(event) => {
                    updateAttendance("late_xp", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
              <div>
                <label className={fieldLabelClassName}>
                  {t("On-time cutoff (HH:MM)")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={draftConfig.attendance.on_time_cutoff}
                  onChange={(event) => {
                    updateAttendance("on_time_cutoff", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
              <div>
                <label className={fieldLabelClassName}>
                  {t("Grace cutoff (HH:MM)")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={draftConfig.attendance.grace_cutoff}
                  onChange={(event) => {
                    updateAttendance("grace_cutoff", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
              <div>
                <label className={fieldLabelClassName}>
                  {t("Timezone")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={draftConfig.attendance.timezone}
                  onChange={(event) => {
                    updateAttendance("timezone", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
            </div>
          </div>

          <div className="rm-subpanel p-4 sm:p-5">
            <p className="rm-card-title">{t("Progression")}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <label className={fieldLabelClassName}>
                  {t("Weekly target XP")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="number"
                  value={draftConfig.progression?.weekly_target_xp ?? 0}
                  onChange={(event) => {
                    updateProgressionScalar("weekly_target_xp", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>

              <div>
                <label className={fieldLabelClassName}>
                  {t("Weekly coupon amount")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  type="number"
                  value={draftConfig.progression?.weekly_coupon_amount ?? 0}
                  onChange={(event) => {
                    updateProgressionScalar("weekly_coupon_amount", event.target.value);
                  }}
                  disabled={!canWrite || isSaving || isRollingBack}
                />
              </div>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {LEVEL_KEYS.map((levelKey) => (
                <div key={levelKey}>
                  <label className={fieldLabelClassName}>
                    {t("L{{level}} threshold", { level: levelKey })}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    type="number"
                    value={draftConfig.progression?.level_thresholds?.[levelKey] ?? 0}
                    onChange={(event) => {
                      updateProgressionThreshold(levelKey, event.target.value);
                    }}
                    disabled={
                      levelKey === "1"
                      || !canWrite
                      || isSaving
                      || isRollingBack
                    }
                  />
                </div>
              ))}
            </div>

            <p className="mt-2 text-xs text-slate-500">
              {t("Level thresholds are normalized by backend validation. L1 always stays 0.")}
            </p>
          </div>

          <div className="rm-subpanel p-4 sm:p-5">
            <p className="rm-card-title">{t("Publish New Version")}</p>
            <label className={cn("mt-3", fieldLabelClassName)}>
              {t("Change reason (optional)")}
            </label>
            <textarea
              className={cn(fieldClassName, "mt-1 min-h-[96px] resize-y py-2")}
              value={saveReason}
              onChange={(event) => setSaveReason(event.target.value)}
              placeholder={t("What changed and why?")}
              disabled={!canWrite || isSaving || isRollingBack}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!canWrite || isSaving || isRollingBack || isLoadingState}
                onClick={() => {
                  void handleSaveConfig();
                }}
              >
                {canWrite ? <ShieldCheck className="mr-2 h-4 w-4" /> : <ShieldAlert className="mr-2 h-4 w-4" />}
                {isSaving ? t("Saving...") : t("Save rules config")}
              </Button>
            </div>
          </div>

          <div className="rm-subpanel p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                <History className="h-4 w-4" />
                {t("Version History")}
              </p>
              {isLoadingHistory ? (
                <p className="text-xs text-slate-500">{t("Loading...")}</p>
              ) : (
                <p className="text-xs text-slate-500">
                  {t("{{count}} versions loaded", { count: history.length })}
                </p>
              )}
            </div>

            <div className="mt-3 grid gap-2">
              {history.length === 0 ? (
                <p className="text-sm text-slate-500">{t("No history entries found.")}</p>
              ) : (
                history.map((version) => {
                  const changePaths = diffChangePaths(version);
                  return (
                    <div
                      key={version.id}
                      className="rounded-lg border border-slate-200/80 bg-white/70 px-3 py-2"
                    >
                      <p className="text-sm font-semibold text-slate-900">
                        v{version.version} | {version.action}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {formatDateTime(version.created_at)} |{" "}
                        {version.created_by_username || t("system")} |{" "}
                        {t("{{count}} change(s)", { count: changePaths.length })}
                      </p>
                      {version.reason ? (
                        <p className="mt-1 text-xs text-slate-600">
                          {t("Reason")}: {version.reason}
                        </p>
                      ) : null}
                      {changePaths.length ? (
                        <p className="mt-1 text-xs text-slate-500">
                          {changePaths.slice(0, 5).join(", ")}
                          {changePaths.length > 5 ? " ..." : ""}
                        </p>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="rm-subpanel p-4 sm:p-5">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <RotateCcw className="h-4 w-4" />
              {t("Rollback to Previous Version")}
            </p>
            {rollbackOptions.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">
                {t("No rollback target is available.")}
              </p>
            ) : (
              <>
                <div className="mt-3 grid gap-3 sm:grid-cols-[260px_1fr]">
                  <div>
                    <label className={fieldLabelClassName}>
                      {t("Target version")}
                    </label>
                    <select
                      className={cn(fieldClassName, "mt-1")}
                      value={rollbackVersionInput}
                      onChange={(event) => setRollbackVersionInput(event.target.value)}
                      disabled={!canWrite || isRollingBack || isSaving}
                    >
                      {rollbackOptions.map((row) => (
                        <option key={row.id} value={row.version}>
                          v{row.version} | {row.action}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className={fieldLabelClassName}>
                      {t("Rollback reason (optional)")}
                    </label>
                    <input
                      className={cn(fieldClassName, "mt-1")}
                      value={rollbackReason}
                      onChange={(event) => setRollbackReason(event.target.value)}
                      placeholder={t("Reason for rollback")}
                      disabled={!canWrite || isRollingBack || isSaving}
                    />
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canWrite || isRollingBack || isSaving}
                    onClick={() => {
                      void handleRollback();
                    }}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    {isRollingBack ? t("Rolling back...") : t("Rollback config")}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
