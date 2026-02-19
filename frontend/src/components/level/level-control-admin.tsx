import {
  CalendarClock,
  Loader2,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import {
  getLevelControlOverview,
  getLevelControlUserHistory,
  runWeeklyLevelEvaluation,
  setLevelControlUserLevel,
  type LevelControlOverview,
  type LevelControlUserHistory,
  type ManualLevelSetResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LevelControlAdminProps = {
  accessToken: string;
  canManage: boolean;
};

type FeedbackState =
  | {
      type: "success" | "error";
      message: string;
    }
  | null;

const fieldClassName = "rm-input";

function toIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function defaultRange(): { dateFrom: string; dateTo: string } {
  const today = new Date();
  const from = new Date(today);
  from.setDate(today.getDate() - 6);
  return {
    dateFrom: toIsoDate(from),
    dateTo: toIsoDate(today),
  };
}

function previousMondayToken(): string {
  const now = new Date();
  const monday = new Date(now);
  const weekday = monday.getDay();
  const distanceToCurrentMonday = (weekday + 6) % 7;
  monday.setDate(monday.getDate() - distanceToCurrentMonday - 7);
  return toIsoDate(monday);
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function warningWeekChangeLabel(
  result: ManualLevelSetResult,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (!result.warning_active_before && result.warning_active_after) {
    return t("Warning week added");
  }
  if (result.warning_active_before && !result.warning_active_after) {
    return t("Warning week removed");
  }
  return result.warning_active_after
    ? t("Warning week unchanged (active)")
    : t("Warning week unchanged (not active)");
}

function levelChangeLabel(
  result: ManualLevelSetResult,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (result.new_level > result.previous_level) {
    return t("Levelling up: L{{from}} -> L{{to}}", {
      from: result.previous_level,
      to: result.new_level,
    });
  }
  if (result.new_level < result.previous_level) {
    return t("Levelling down: L{{from}} -> L{{to}}", {
      from: result.previous_level,
      to: result.new_level,
    });
  }
  return t("Level unchanged: L{{level}}", { level: result.new_level });
}

function manualLevelSuccessMessage(
  result: ManualLevelSetResult,
  note: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const normalizedNote = note.trim();
  return (
    t("{{name}}: {{warning}}. {{level}}. Comment: {{comment}}", {
      name: result.display_name,
      warning: warningWeekChangeLabel(result, t),
      level: levelChangeLabel(result, t),
      comment: normalizedNote || "-",
    })
  );
}

export function LevelControlAdmin({
  accessToken,
  canManage,
}: LevelControlAdminProps) {
  const { t } = useI18n();
  const [dateFromInput, setDateFromInput] = useState(defaultRange().dateFrom);
  const [dateToInput, setDateToInput] = useState(defaultRange().dateTo);
  const [appliedRange, setAppliedRange] = useState(defaultRange());
  const [evaluationWeekStart, setEvaluationWeekStart] = useState(previousMondayToken);

  const [overview, setOverview] = useState<LevelControlOverview | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserHistory, setSelectedUserHistory] = useState<LevelControlUserHistory | null>(
    null,
  );

  const [levelInput, setLevelInput] = useState("1");
  const [levelNote, setLevelNote] = useState("");
  const [clearWarningInput, setClearWarningInput] = useState(false);

  const [isLoadingOverview, setIsLoadingOverview] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSettingLevel, setIsSettingLevel] = useState(false);
  const [isRunningEvaluation, setIsRunningEvaluation] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const selectedRow = useMemo(
    () => overview?.rows.find((row) => row.user_id === selectedUserId) ?? null,
    [overview, selectedUserId],
  );

  const loadOverview = useCallback(async () => {
    if (!canManage) {
      setOverview(null);
      return;
    }
    setIsLoadingOverview(true);
    try {
      const payload = await getLevelControlOverview(accessToken, {
        date_from: appliedRange.dateFrom,
        date_to: appliedRange.dateTo,
      });
      setOverview(payload);
      setSelectedUserId((previous) => {
        if (previous && payload.rows.some((row) => row.user_id === previous)) {
          return previous;
        }
        return payload.rows[0]?.user_id ?? null;
      });
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load level overview.")),
      });
    } finally {
      setIsLoadingOverview(false);
    }
  }, [accessToken, appliedRange.dateFrom, appliedRange.dateTo, canManage, t]);

  const loadUserHistory = useCallback(
    async (userId: number | null) => {
      if (!userId || !canManage) {
        setSelectedUserHistory(null);
        return;
      }
      setIsLoadingHistory(true);
      try {
        const history = await getLevelControlUserHistory(accessToken, userId, {
          date_from: appliedRange.dateFrom,
          date_to: appliedRange.dateTo,
          limit: 1000,
        });
        setSelectedUserHistory(history);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load user history.")),
        });
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [accessToken, appliedRange.dateFrom, appliedRange.dateTo, canManage, t],
  );

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    void loadUserHistory(selectedUserId);
  }, [loadUserHistory, selectedUserId]);

  useEffect(() => {
    if (selectedRow) {
      setLevelInput(String(selectedRow.current_level));
      setClearWarningInput(false);
    }
  }, [selectedRow]);

  const handleApplyRange = () => {
    setFeedback(null);
    if (!dateFromInput || !dateToInput) {
      setFeedback({
        type: "error",
        message: t("Both from and to dates are required."),
      });
      return;
    }
    if (dateFromInput > dateToInput) {
      setFeedback({
        type: "error",
        message: t("From date must be less than or equal to To date."),
      });
      return;
    }
    setAppliedRange({ dateFrom: dateFromInput, dateTo: dateToInput });
  };

  const handleManualLevelSet = async () => {
    if (!selectedRow) {
      setFeedback({
        type: "error",
        message: t("Select a technician first."),
      });
      return;
    }

    const parsedLevel = Number(levelInput);
    if (!Number.isInteger(parsedLevel) || parsedLevel < 1 || parsedLevel > 5) {
      setFeedback({
        type: "error",
        message: t("Level must be between L1 and L5."),
      });
      return;
    }

    setIsSettingLevel(true);
    setFeedback(null);
    try {
      const normalizedNote = levelNote.trim();
      const result = await setLevelControlUserLevel(accessToken, selectedRow.user_id, {
        level: parsedLevel,
        note: normalizedNote,
        clear_warning: clearWarningInput,
      });
      setFeedback({
        type: "success",
        message: manualLevelSuccessMessage(result, normalizedNote, t),
      });
      setLevelNote("");
      setClearWarningInput(false);
      await Promise.all([loadOverview(), loadUserHistory(selectedRow.user_id)]);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to update user level.")),
      });
    } finally {
      setIsSettingLevel(false);
    }
  };

  const handleRunWeeklyEvaluation = async () => {
    setIsRunningEvaluation(true);
    setFeedback(null);
    try {
      const summary = await runWeeklyLevelEvaluation(accessToken, {
        week_start: evaluationWeekStart || undefined,
      });
      setFeedback({
        type: "success",
        message: t(
          "Weekly evaluation completed for {{from}}..{{to}}. created={{created}}, warnings={{warnings}}, resets={{resets}}.",
          {
            from: summary.week_start,
            to: summary.week_end,
            created: summary.evaluations_created,
            warnings: summary.warnings_created,
            resets: summary.levels_reset_to_l1,
          },
        ),
      });
      await loadOverview();
      if (selectedUserId) {
        await loadUserHistory(selectedUserId);
      }
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to run weekly level evaluation.")),
      });
    } finally {
      setIsRunningEvaluation(false);
    }
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{t("Level Control")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {t(
                "Weekly XP target tracking, warning-week suggestions, manual level edits, and full per-user progression history.",
              )}
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            className="h-10 w-full sm:w-auto"
            onClick={() => {
              void loadOverview();
            }}
            disabled={isLoadingOverview || !canManage}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            {t("Refresh")}
          </Button>
        </div>
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

      {!canManage ? (
        <p className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-600">
          {t("Level control is available only for Super Admin and Ops Manager.")}
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_1fr_auto]">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("From date")}
              </label>
              <input
                type="date"
                className={cn(fieldClassName, "mt-1")}
                value={dateFromInput}
                onChange={(event) => setDateFromInput(event.target.value)}
                disabled={isLoadingOverview}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("To date")}
              </label>
              <input
                type="date"
                className={cn(fieldClassName, "mt-1")}
                value={dateToInput}
                onChange={(event) => setDateToInput(event.target.value)}
                disabled={isLoadingOverview}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Current weekly target")}
              </label>
              <p className="mt-1 inline-flex h-10 w-full items-center rounded-xl border border-slate-300/80 bg-slate-50 px-3 text-sm text-slate-700">
                {overview ? `${overview.weekly_target_xp} XP` : "-"}
              </p>
            </div>
            <div className="grid gap-2 self-end">
              <Button
                type="button"
                className="h-10"
                onClick={handleApplyRange}
                disabled={isLoadingOverview}
              >
                {t("Apply")}
              </Button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Technicians")}</p>
              <p className="mt-1 text-xl font-semibold text-slate-900">
                {overview?.summary.technicians_total ?? 0}
              </p>
            </div>
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Met target")}</p>
              <p className="mt-1 text-xl font-semibold text-emerald-700">
                {overview?.summary.met_target ?? 0}
              </p>
            </div>
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Below target")}</p>
              <p className="mt-1 text-xl font-semibold text-amber-700">
                {overview?.summary.below_target ?? 0}
              </p>
            </div>
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Warning active")}</p>
              <p className="mt-1 text-xl font-semibold text-rose-700">
                {overview?.summary.warning_active ?? 0}
              </p>
            </div>
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Suggest warning")}</p>
              <p className="mt-1 text-xl font-semibold text-orange-700">
                {overview?.summary.suggested_warning ?? 0}
              </p>
            </div>
            <div className="rm-subpanel p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Suggest reset")}</p>
              <p className="mt-1 text-xl font-semibold text-rose-700">
                {overview?.summary.suggested_reset_to_l1 ?? 0}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white/70 p-3">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-900">
                  {t("Technician Weekly XP")}
                </p>
                <p className="text-xs text-slate-500">
                  {overview?.date_from} to {overview?.date_to}
                </p>
              </div>
              {isLoadingOverview ? (
                <p className="flex items-center gap-2 px-1 py-5 text-sm text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading level overview...")}
                </p>
              ) : overview?.rows.length ? (
                <div className="space-y-2">
                  {overview.rows.map((row) => (
                    <article
                      key={row.user_id}
                      className={cn(
                        "rounded-lg border px-3 py-3 transition",
                        selectedUserId === row.user_id
                          ? "border-slate-900 bg-slate-100/90"
                          : "border-slate-200 bg-white/80 hover:border-slate-400",
                      )}
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            {row.display_name}
                          </p>
                          <p className="text-xs text-slate-500">@{row.username}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                            L{row.current_level}
                          </span>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5",
                              row.meets_target
                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                : "border-amber-200 bg-amber-50 text-amber-700",
                            )}
                          >
                            {row.range_xp}/{row.range_target_xp} XP
                          </span>
                          {row.warning_active ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-rose-700">
                              <ShieldAlert className="h-3.5 w-3.5" />
                              {t("Warning")}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-emerald-700">
                              <ShieldCheck className="h-3.5 w-3.5" />
                              {t("Normal")}
                            </span>
                          )}
                        </div>
                      </div>

                      {(row.suggested_warning || row.suggested_reset_to_l1) ? (
                        <p className="mt-2 text-xs text-slate-700">
                          {row.suggested_reset_to_l1
                            ? t(
                              "Suggested action: second miss while in warning period, reset to L1.",
                            )
                            : t("Suggested action: move to warning week.")}
                        </p>
                      ) : null}

                      <div className="mt-2 flex justify-end">
                        <Button
                          type="button"
                          variant="outline"
                          className="h-8"
                          onClick={() => setSelectedUserId(row.user_id)}
                        >
                          <UserRound className="mr-1 h-4 w-4" />
                          {t("Open details")}
                        </Button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="px-1 py-6 text-sm text-slate-600">
                  {t("No technicians found for this range.")}
                </p>
              )}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white/70 p-3">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-900">{t("Selected User")}</p>
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    className={cn(fieldClassName, "h-9 w-[150px]")}
                    value={evaluationWeekStart}
                    onChange={(event) => setEvaluationWeekStart(event.target.value)}
                    disabled={isRunningEvaluation}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="h-9"
                    onClick={() => {
                      void handleRunWeeklyEvaluation();
                    }}
                    disabled={isRunningEvaluation}
                  >
                    <CalendarClock className="mr-1 h-4 w-4" />
                    {t("Evaluate")}
                  </Button>
                </div>
              </div>

              {selectedRow ? (
                <div className="space-y-3">
                  <div className="rm-subpanel p-3">
                    <p className="text-sm font-semibold text-slate-900">
                      {selectedRow.display_name}
                    </p>
                    <p className="text-xs text-slate-500">@{selectedRow.username}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("Current L{{level}}", { level: selectedRow.current_level })}
                      </span>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("Suggested L{{level}}", {
                          level: selectedRow.suggested_level_by_xp,
                        })}
                      </span>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("XP {{xp}}/{{target}}", {
                          xp: selectedRow.range_xp,
                          target: selectedRow.range_target_xp,
                        })}
                      </span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      {t("Manual level update")}
                    </p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <select
                        className={fieldClassName}
                        value={levelInput}
                        onChange={(event) => setLevelInput(event.target.value)}
                        disabled={isSettingLevel}
                      >
                        {[1, 2, 3, 4, 5].map((level) => (
                          <option key={level} value={level}>
                            L{level}
                          </option>
                        ))}
                      </select>
                      <label className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={clearWarningInput}
                          onChange={(event) => setClearWarningInput(event.target.checked)}
                          disabled={isSettingLevel}
                        />
                        {t("Clear warning")}
                      </label>
                    </div>
                    <textarea
                      className={cn(fieldClassName, "mt-2 min-h-[88px] resize-y py-2")}
                      value={levelNote}
                      onChange={(event) => setLevelNote(event.target.value)}
                      placeholder={t("Optional note")}
                      disabled={isSettingLevel}
                    />
                    <div className="mt-2 flex justify-end">
                      <Button
                        type="button"
                        className="h-9"
                        onClick={() => {
                          void handleManualLevelSet();
                        }}
                        disabled={isSettingLevel}
                      >
                        <Sparkles className="mr-1 h-4 w-4" />
                        {t("Save level")}
                      </Button>
                    </div>
                  </div>

                  {isLoadingHistory ? (
                    <p className="flex items-center gap-2 text-sm text-slate-600">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {t("Loading full user history...")}
                    </p>
                  ) : selectedUserHistory ? (
                    <div className="space-y-3">
                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                          {t("XP history ({{count}})", {
                            count: selectedUserHistory.xp_history.length,
                          })}
                        </p>
                        <div className="mt-2 max-h-44 space-y-1 overflow-auto text-xs">
                          {selectedUserHistory.xp_history.length ? (
                            selectedUserHistory.xp_history.map((row) => (
                              <div key={row.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
                                <p className="font-medium text-slate-800">
                                  {row.amount > 0 ? `+${row.amount}` : row.amount} XP | {row.entry_type}
                                </p>
                                <p className="text-slate-500">{new Date(row.created_at).toLocaleString()}</p>
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500">{t("No XP rows in selected period.")}</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                          {t("Level history ({{count}})", {
                            count: selectedUserHistory.level_history.length,
                          })}
                        </p>
                        <div className="mt-2 max-h-44 space-y-1 overflow-auto text-xs">
                          {selectedUserHistory.level_history.length ? (
                            selectedUserHistory.level_history.map((row) => (
                              <div key={row.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
                                <p className="font-medium text-slate-800">
                                  {row.source} | {row.status} | L{row.previous_level} {"->"} L{row.new_level}
                                </p>
                                <p className="text-slate-500">
                                  {new Date(row.created_at).toLocaleString()} | {t("by")}{" "}
                                  {row.actor_username || t("system")}
                                </p>
                                {row.warning_active_after ? (
                                  <p className="text-rose-700">{t("Warning active after this event")}</p>
                                ) : null}
                                {row.note ? (
                                  <p className="text-slate-600">{t("Comment")}: {row.note}</p>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500">{t("No level history rows in selected period.")}</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                          {t("Weekly evaluations ({{count}})", {
                            count: selectedUserHistory.weekly_evaluations.length,
                          })}
                        </p>
                        <div className="mt-2 max-h-44 space-y-1 overflow-auto text-xs">
                          {selectedUserHistory.weekly_evaluations.length ? (
                            selectedUserHistory.weekly_evaluations.map((row) => (
                              <div key={row.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
                                <p className="font-medium text-slate-800">
                                  {row.week_start}..{row.week_end} | {row.target_status || "n/a"}
                                </p>
                                <p className="text-slate-500">
                                  XP {row.weekly_xp}/{row.weekly_target_xp} | L{row.previous_level} {"->"} L{row.new_level}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500">{t("No weekly evaluations in selected period.")}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">{t("Select a technician to load history.")}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  {t("No user selected. Pick a technician from the list.")}
                </p>
              )}
            </section>
          </div>

        </>
      )}
    </section>
  );
}
