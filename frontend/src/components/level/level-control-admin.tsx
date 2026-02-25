import {
  AlertTriangle,
  Loader2,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { useI18n } from "@/i18n";
import {
  getInventoryItem,
  getLevelControlOverview,
  getLevelControlUserHistory,
  getTicket,
  setLevelControlUserLevel,
  type InventoryItem,
  type LevelControlOverview,
  type LevelControlOverviewRow,
  type LevelControlUserHistory,
  type ManualLevelSetResult,
  type Ticket,
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

type TicketContext = {
  ticketId: number;
  inventoryItemId: number | null;
  serialNumber: string | null;
};

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
  return t("{{name}}: {{warning}}. {{level}}. Comment: {{comment}}", {
    name: result.display_name,
    warning: warningWeekChangeLabel(result, t),
    level: levelChangeLabel(result, t),
    comment: normalizedNote || "-",
  });
}

function entryTicketId(
  row: LevelControlUserHistory["xp_history"][number],
): number | null {
  const payload = row.payload as Record<string, unknown>;
  const fromPayload = payload?.ticket_id;
  if (typeof fromPayload === "number" && Number.isInteger(fromPayload) && fromPayload > 0) {
    return fromPayload;
  }
  if (typeof fromPayload === "string") {
    const parsed = Number.parseInt(fromPayload, 10);
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed;
    }
  }
  const match = row.reference.match(/^ticket_[a-z_]+:(\d+)(?::\d+)?$/i);
  if (!match) {
    return null;
  }
  const parsed = Number.parseInt(match[1], 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function rowPriority(row: LevelControlOverviewRow): number {
  if (row.suggested_reset_to_l1) {
    return 0;
  }
  if (row.suggested_warning) {
    return 1;
  }
  if (!row.meets_target) {
    return 2;
  }
  if (row.warning_active) {
    return 3;
  }
  return 4;
}

function suggestionToneClass(
  tone: "good" | "warn" | "danger" | "neutral",
): string {
  if (tone === "good") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (tone === "warn") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (tone === "danger") {
    return "border-rose-200 bg-rose-50 text-rose-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function suggestionForRow(
  row: LevelControlOverviewRow,
  t: (key: string, params?: Record<string, string | number>) => string,
): { tone: "good" | "warn" | "danger" | "neutral"; text: string } {
  if (row.suggested_reset_to_l1) {
    return {
      tone: "danger",
      text: t(
        "User is in warning week and missed KPI again. Suggested action: set level to L1.",
      ),
    };
  }
  if (row.suggested_warning) {
    return {
      tone: "warn",
      text: t("User missed weekly KPI. Suggested action: set warning week."),
    };
  }
  if (row.warning_active && row.meets_target) {
    return {
      tone: "good",
      text: t(
        "User met weekly KPI while in warning week. Suggested action: remove warning week.",
      ),
    };
  }
  if (row.meets_target) {
    return {
      tone: "good",
      text: t("Weekly KPI achieved. No mandatory action."),
    };
  }
  return {
    tone: "neutral",
    text: t("Below weekly KPI."),
  };
}

export function LevelControlAdmin({
  accessToken,
  canManage,
}: LevelControlAdminProps) {
  const { t } = useI18n();
  const [dateFromInput, setDateFromInput] = useState(() => defaultRange().dateFrom);
  const [dateToInput, setDateToInput] = useState(() => defaultRange().dateTo);
  const [appliedRange, setAppliedRange] = useState(defaultRange);

  const [overview, setOverview] = useState<LevelControlOverview | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserHistory, setSelectedUserHistory] =
    useState<LevelControlUserHistory | null>(null);
  const [ticketContextById, setTicketContextById] = useState<
    Record<number, TicketContext>
  >({});

  const [levelInput, setLevelInput] = useState("1");
  const [actionNote, setActionNote] = useState("");
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [isLoadingOverview, setIsLoadingOverview] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  const selectedRow = useMemo(
    () => overview?.rows.find((row) => row.user_id === selectedUserId) ?? null,
    [overview, selectedUserId],
  );

  const sortedRows = useMemo(() => {
    if (!overview) {
      return [];
    }
    return [...overview.rows].sort((left, right) => {
      const priorityDelta = rowPriority(left) - rowPriority(right);
      if (priorityDelta !== 0) {
        return priorityDelta;
      }
      const xpDelta = left.range_xp - right.range_xp;
      if (xpDelta !== 0) {
        return xpDelta;
      }
      return left.display_name.localeCompare(right.display_name);
    });
  }, [overview]);

  const hydrateTicketContexts = useCallback(
    async (entries: LevelControlUserHistory["xp_history"]) => {
      const ticketIds = [...new Set(entries.map(entryTicketId).filter((id): id is number => id !== null))]
        .slice(0, 80);
      if (!ticketIds.length) {
        return;
      }

      const missingTicketIds = ticketIds.filter((id) => !ticketContextById[id]);
      if (!missingTicketIds.length) {
        return;
      }

      const ticketResults = await Promise.all(
        missingTicketIds.map(async (ticketId) => {
          try {
            const ticket = await getTicket(accessToken, ticketId);
            return { ticketId, ticket };
          } catch {
            return null;
          }
        }),
      );
      const validTickets = ticketResults.filter(
        (row): row is { ticketId: number; ticket: Ticket } => row !== null,
      );
      const uniqueInventoryIds = [
        ...new Set(
          validTickets
            .map((row) => row.ticket.inventory_item)
            .filter((id) => Number.isInteger(id) && id > 0),
        ),
      ];

      const inventoryById: Record<number, InventoryItem> = {};
      await Promise.all(
        uniqueInventoryIds.map(async (inventoryItemId) => {
          try {
            inventoryById[inventoryItemId] = await getInventoryItem(
              accessToken,
              inventoryItemId,
            );
          } catch {
            // ignore one-off fetch errors
          }
        }),
      );

      setTicketContextById((prev) => {
        const next = { ...prev };
        validTickets.forEach(({ ticketId, ticket }) => {
          const inventoryItemId =
            Number.isInteger(ticket.inventory_item) && ticket.inventory_item > 0
              ? ticket.inventory_item
              : null;
          next[ticketId] = {
            ticketId,
            inventoryItemId,
            serialNumber:
              inventoryItemId && inventoryById[inventoryItemId]
                ? inventoryById[inventoryItemId].serial_number
                : null,
          };
        });
        missingTicketIds.forEach((ticketId) => {
          if (!next[ticketId]) {
            next[ticketId] = {
              ticketId,
              inventoryItemId: null,
              serialNumber: null,
            };
          }
        });
        return next;
      });
    },
    [accessToken, ticketContextById],
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
          limit: 500,
        });
        setSelectedUserHistory(history);
        await hydrateTicketContexts(history.xp_history);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load user history.")),
        });
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [
      accessToken,
      appliedRange.dateFrom,
      appliedRange.dateTo,
      canManage,
      hydrateTicketContexts,
      t,
    ],
  );

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    void loadUserHistory(selectedUserId);
  }, [loadUserHistory, selectedUserId]);

  useEffect(() => {
    if (!selectedRow) {
      return;
    }
    setLevelInput(String(selectedRow.current_level));
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
    setAppliedRange({
      dateFrom: dateFromInput,
      dateTo: dateToInput,
    });
  };

  const applyUserUpdate = useCallback(
    async (payload: { level: number; warningActive?: boolean }) => {
      if (!selectedRow) {
        setFeedback({
          type: "error",
          message: t("Select a technician first."),
        });
        return;
      }

      const normalizedNote = actionNote.trim();

      setIsApplying(true);
      setFeedback(null);
      try {
        const result = await setLevelControlUserLevel(accessToken, selectedRow.user_id, {
          level: payload.level,
          note: normalizedNote || undefined,
          warning_active: payload.warningActive,
        });
        setFeedback({
          type: "success",
          message: manualLevelSuccessMessage(result, normalizedNote, t),
        });
        setActionNote("");
        await Promise.all([loadOverview(), loadUserHistory(selectedRow.user_id)]);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to update user level.")),
        });
      } finally {
        setIsApplying(false);
      }
    },
    [accessToken, actionNote, loadOverview, loadUserHistory, selectedRow, t],
  );

  const handleSetWarning = () => {
    if (!selectedRow) {
      return;
    }
    void applyUserUpdate({
      level: selectedRow.current_level,
      warningActive: true,
    });
  };

  const handleUnsetWarning = () => {
    if (!selectedRow) {
      return;
    }
    void applyUserUpdate({
      level: selectedRow.current_level,
      warningActive: false,
    });
  };

  const handleSetLevel = () => {
    if (!selectedRow) {
      setFeedback({
        type: "error",
        message: t("Select a technician first."),
      });
      return;
    }
    const parsedLevel = Number.parseInt(levelInput, 10);
    if (!Number.isInteger(parsedLevel) || parsedLevel < 1 || parsedLevel > 5) {
      setFeedback({
        type: "error",
        message: t("Level must be between L1 and L5."),
      });
      return;
    }
    void applyUserUpdate({
      level: parsedLevel,
    });
  };

  const handleSetL1 = () => {
    if (!selectedRow) {
      return;
    }
    void applyUserUpdate({
      level: 1,
    });
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{t("Level Control")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {t(
                "Weekly KPI helper: review technician XP, set warning week manually, and apply level decisions with clear suggestions.",
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

      <FeedbackToast feedback={feedback} />

      {!canManage ? (
        <p className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-600">
          {t("Level control is available only for Super Admin and Ops Manager.")}
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
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
                {t("Weekly KPI target")}
              </label>
              <p className="mt-1 inline-flex h-10 w-full items-center rounded-xl border border-slate-300/80 bg-slate-50 px-3 text-sm text-slate-700">
                {overview ? `${overview.weekly_target_xp} XP` : "-"}
              </p>
            </div>
            <div className="self-end">
              <Button
                type="button"
                className="h-10 w-full"
                onClick={handleApplyRange}
                disabled={isLoadingOverview}
              >
                {t("Apply")}
              </Button>
            </div>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-4">
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
              <p className="text-xs uppercase tracking-wide text-slate-500">
                {t("Warning active")}
              </p>
              <p className="mt-1 text-xl font-semibold text-rose-700">
                {overview?.summary.warning_active ?? 0}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white/70 p-3">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-900">
                  {t("Technician Weekly XP")}
                </p>
                <p className="text-xs text-slate-500">
                  {overview?.date_from} {t("to")} {overview?.date_to}
                </p>
              </div>

              {isLoadingOverview ? (
                <p className="flex items-center gap-2 px-1 py-5 text-sm text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading level overview...")}
                </p>
              ) : sortedRows.length ? (
                <div className="space-y-2">
                  {sortedRows.map((row) => {
                    const suggestion = suggestionForRow(row, t);
                    return (
                      <button
                        key={row.user_id}
                        type="button"
                        onClick={() => setSelectedUserId(row.user_id)}
                        className={cn(
                          "w-full rounded-lg border px-3 py-3 text-left transition",
                          selectedUserId === row.user_id
                            ? "border-slate-900 bg-slate-100/90"
                            : "border-slate-200 bg-white/80 hover:border-slate-400",
                        )}
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">
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

                        {!row.meets_target || row.warning_active ? (
                          <p className={cn("mt-2 rounded-md border px-2 py-1 text-xs", suggestionToneClass(suggestion.tone))}>
                            {suggestion.text}
                          </p>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="px-1 py-6 text-sm text-slate-600">
                  {t("No technicians found for this range.")}
                </p>
              )}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white/70 p-3">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900">{t("Selected User")}</p>
              </div>

              {selectedRow ? (
                <div className="space-y-3">
                  <div className="rm-subpanel p-3">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <UserRound className="h-4 w-4" />
                      {selectedRow.display_name}
                    </p>
                    <p className="text-xs text-slate-500">@{selectedRow.username}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("Current L{{level}}", { level: selectedRow.current_level })}
                      </span>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("XP {{xp}}/{{target}}", {
                          xp: selectedRow.range_xp,
                          target: selectedRow.range_target_xp,
                        })}
                      </span>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                        {t("Cumulative XP")}: {selectedRow.cumulative_xp}
                      </span>
                    </div>
                  </div>

                  <div
                    className={cn(
                      "rounded-lg border px-3 py-2 text-sm",
                      suggestionToneClass(suggestionForRow(selectedRow, t).tone),
                    )}
                  >
                    {suggestionForRow(selectedRow, t).text}
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      {t("Admin actions")}
                    </p>
                    <textarea
                      className={cn(fieldClassName, "mt-2 min-h-[82px] resize-y py-2")}
                      value={actionNote}
                      onChange={(event) => setActionNote(event.target.value)}
                      placeholder={t("Optional note")}
                      disabled={isApplying}
                    />

                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {!selectedRow.warning_active ? (
                        <Button
                          type="button"
                          className="h-9"
                          onClick={handleSetWarning}
                          disabled={isApplying}
                        >
                          <ShieldAlert className="mr-1 h-4 w-4" />
                          {t("Set warning week")}
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="outline"
                          className="h-9"
                          onClick={handleUnsetWarning}
                          disabled={isApplying}
                        >
                          <ShieldCheck className="mr-1 h-4 w-4" />
                          {t("Unset warning week")}
                        </Button>
                      )}

                      <Button
                        type="button"
                        variant={selectedRow.suggested_reset_to_l1 ? "default" : "outline"}
                        className={cn(
                          "h-9",
                          selectedRow.suggested_reset_to_l1
                            ? ""
                            : "border-rose-300 text-rose-700",
                        )}
                        onClick={handleSetL1}
                        disabled={isApplying}
                      >
                        <AlertTriangle className="mr-1 h-4 w-4" />
                        {t("Set level to L1")}
                      </Button>
                    </div>

                    <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
                      <select
                        className={fieldClassName}
                        value={levelInput}
                        onChange={(event) => setLevelInput(event.target.value)}
                        disabled={isApplying}
                      >
                        {[1, 2, 3, 4, 5].map((level) => (
                          <option key={level} value={level}>
                            L{level}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        className="h-9"
                        onClick={handleSetLevel}
                        disabled={isApplying}
                      >
                        <Sparkles className="mr-1 h-4 w-4" />
                        {t("Apply level")}
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
                        <div className="mt-2 max-h-52 space-y-1 overflow-auto text-xs">
                          {selectedUserHistory.xp_history.length ? (
                            selectedUserHistory.xp_history.map((row) => {
                              const ticketId = entryTicketId(row);
                              const context = ticketId
                                ? ticketContextById[ticketId] ?? null
                                : null;
                              return (
                                <div
                                  key={row.id}
                                  className="rounded border border-slate-200 bg-slate-50 px-2 py-1"
                                >
                                  <p className="font-medium text-slate-800">
                                    {row.amount > 0 ? `+${row.amount}` : row.amount} XP |{" "}
                                    {row.entry_type}
                                  </p>
                                  {ticketId ? (
                                    <p className="text-slate-600">
                                      {t("Ticket #{{id}}", { id: ticketId })}
                                      {context?.serialNumber
                                        ? ` • ${context.serialNumber}`
                                        : context?.inventoryItemId
                                          ? ` • ${t("Item #{{id}}", {
                                            id: context.inventoryItemId,
                                          })}`
                                          : ""}
                                    </p>
                                  ) : null}
                                  {row.description ? (
                                    <p className="text-slate-600">{row.description}</p>
                                  ) : null}
                                  <p className="text-slate-500">
                                    {new Date(row.created_at).toLocaleString()}
                                  </p>
                                </div>
                              );
                            })
                          ) : (
                            <p className="text-slate-500">
                              {t("No XP rows in selected period.")}
                            </p>
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
                              <div
                                key={row.id}
                                className="rounded border border-slate-200 bg-slate-50 px-2 py-1"
                              >
                                <p className="font-medium text-slate-800">
                                  {row.source} | {row.status} | L{row.previous_level} {"->"} L
                                  {row.new_level}
                                </p>
                                <p className="text-slate-500">
                                  {new Date(row.created_at).toLocaleString()} | {t("by")}{" "}
                                  {row.actor_username || t("system")}
                                </p>
                                {row.note ? (
                                  <p className="text-slate-600">
                                    {t("Comment")}: {row.note}
                                  </p>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500">
                              {t("No level history rows in selected period.")}
                            </p>
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
                              <div
                                key={row.id}
                                className="rounded border border-slate-200 bg-slate-50 px-2 py-1"
                              >
                                <p className="font-medium text-slate-800">
                                  {row.week_start}..{row.week_end} | {row.target_status || "n/a"}
                                </p>
                                <p className="text-slate-500">
                                  XP {row.weekly_xp}/{row.weekly_target_xp} | L
                                  {row.previous_level} {"->"} L{row.new_level}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-slate-500">
                              {t("No weekly evaluations in selected period.")}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">
                      {t("Select a technician to load history.")}
                    </p>
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
