import {
  Activity,
  ArrowLeft,
  Award,
  BarChart3,
  Flag,
  Loader2,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  Target,
  Trophy,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { useI18n } from "@/i18n";
import {
  getPublicTechnicianDetail,
  getPublicTechnicianLeaderboard,
  type PublicTechnicianDetail,
  type PublicTechnicianLeaderboard,
  type PublicTechnicianLeaderboardMember,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ViewState = "leaderboard" | "detail";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function parseTechFromLocation(): number | null {
  const params = new URLSearchParams(window.location.search);
  const value = params.get("tech");
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function scoreBarWidth(score: number, topScore: number): number {
  if (topScore <= 0) {
    return 0;
  }
  return Math.max(6, Math.round((score / topScore) * 100));
}

function contributionLabel(
  label: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (label === "Closed tickets") {
    return t("Closed tickets contribution");
  }
  if (label === "First-pass completions") {
    return t("First-pass bonus");
  }
  if (label === "Quality flags") {
    return t("Flag quality impact");
  }
  if (label === "Attendance consistency") {
    return t("Attendance contribution");
  }
  if (label === "Rework / QC fail penalty") {
    return t("Penalty");
  }
  return t(label);
}

function rankBadgeClass(rank: number): string {
  if (rank === 1) {
    return "border-amber-300 bg-amber-100 text-amber-800";
  }
  if (rank === 2) {
    return "border-slate-300 bg-slate-100 text-slate-700";
  }
  if (rank === 3) {
    return "border-orange-300 bg-orange-100 text-orange-800";
  }
  return "border-cyan-200 bg-cyan-50 text-cyan-800";
}

function flagBadgeClass(color: "green" | "yellow" | "red"): string {
  if (color === "green") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (color === "yellow") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function translateFlagColorLabel(
  color: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const normalized = color.trim().toLowerCase();
  if (normalized === "green") {
    return t("Green");
  }
  if (normalized === "yellow") {
    return t("Yellow");
  }
  if (normalized === "red") {
    return t("Red");
  }
  return color;
}

function translateStatusLabel(
  status: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const normalized = status.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "new") {
    return t("New");
  }
  if (normalized === "in_progress") {
    return t("In progress");
  }
  if (normalized === "under_review") {
    return t("Under review");
  }
  if (normalized === "waiting_qc") {
    return t("Waiting QC");
  }
  if (normalized === "assigned") {
    return t("Assigned");
  }
  if (normalized === "done") {
    return t("Done");
  }
  if (normalized === "pending") {
    return t("Pending");
  }
  if (normalized === "approved") {
    return t("Approved");
  }
  if (normalized === "rejected") {
    return t("Rejected");
  }
  return status;
}

export default function PublicStatsApp() {
  const { t } = useI18n();
  const [leaderboard, setLeaderboard] = useState<PublicTechnicianLeaderboard | null>(null);
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(true);
  const [leaderboardError, setLeaderboardError] = useState("");

  const [selectedUserId, setSelectedUserId] = useState<number | null>(() =>
    parseTechFromLocation(),
  );
  const [detail, setDetail] = useState<PublicTechnicianDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState("");

  const viewState: ViewState = selectedUserId ? "detail" : "leaderboard";

  const loadLeaderboard = useCallback(async () => {
    setIsLoadingLeaderboard(true);
    setLeaderboardError("");
    try {
      const data = await getPublicTechnicianLeaderboard();
      setLeaderboard(data);
    } catch (error) {
      setLeaderboard(null);
      setLeaderboardError(
        toErrorMessage(error, t("Could not load public technician leaderboard.")),
      );
    } finally {
      setIsLoadingLeaderboard(false);
    }
  }, [t]);

  const loadDetail = useCallback(async (userId: number) => {
    setIsLoadingDetail(true);
    setDetailError("");
    try {
      const data = await getPublicTechnicianDetail(userId);
      setDetail(data);
    } catch (error) {
      setDetail(null);
      setDetailError(toErrorMessage(error, t("Could not load technician detail.")));
    } finally {
      setIsLoadingDetail(false);
    }
  }, [t]);

  useEffect(() => {
    void loadLeaderboard();
  }, [loadLeaderboard]);

  useEffect(() => {
    if (!selectedUserId) {
      setDetail(null);
      setDetailError("");
      return;
    }
    void loadDetail(selectedUserId);
  }, [loadDetail, selectedUserId]);

  useEffect(() => {
    const onPopState = () => {
      setSelectedUserId(parseTechFromLocation());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const openDetail = useCallback((userId: number) => {
    const params = new URLSearchParams(window.location.search);
    params.set("tech", String(userId));
    const nextUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, "", nextUrl);
    setSelectedUserId(userId);
  }, []);

  const closeDetail = useCallback(() => {
    const params = new URLSearchParams(window.location.search);
    params.delete("tech");
    const query = params.toString();
    const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.pushState({}, "", nextUrl);
    setSelectedUserId(null);
  }, []);

  const topScore = useMemo(
    () => Math.max(0, ...(leaderboard?.members.map((member) => member.score) ?? [0])),
    [leaderboard?.members],
  );

  const renderLeaderboardRow = (member: PublicTechnicianLeaderboardMember) => {
    const width = scoreBarWidth(member.score, topScore);
    return (
      <button
        key={member.user_id}
        type="button"
        onClick={() => openDetail(member.user_id)}
        className="rm-panel w-full p-4 text-left transition hover:shadow-[0_18px_38px_-22px_rgba(15,23,42,0.45)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                  rankBadgeClass(member.rank),
                )}
              >
                #{member.rank}
              </span>
              <p className="truncate text-sm font-semibold text-slate-900">{member.name}</p>
            </div>
              <p className="mt-1 text-xs text-slate-500">
                @{member.username} • {t("Level {{level}}", { level: member.level })}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-slate-500">{t("Score")}</p>
              <p className="text-lg font-bold text-slate-900">{member.score}</p>
            </div>
          </div>

        <div className="mt-3">
          <div className="h-2 rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-cyan-500 via-teal-500 to-emerald-500"
              style={{ width: `${width}%` }}
            />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600 sm:grid-cols-4">
          <span>{t("Tasks")}: {member.tickets_done_total}</span>
          <span>XP: {member.xp_total}</span>
          <span>{t("1st pass")}: {member.first_pass_rate_percent}%</span>
          <span>{t("Attend")}: {member.attendance_days_total}d</span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-700">{t("Closed flags")}:</span>
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-xs font-semibold",
              flagBadgeClass("green"),
            )}
          >
            {t("Green")} {member.tickets_closed_by_flag.green}
          </span>
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-xs font-semibold",
              flagBadgeClass("yellow"),
            )}
          >
            {t("Yellow")} {member.tickets_closed_by_flag.yellow}
          </span>
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-xs font-semibold",
              flagBadgeClass("red"),
            )}
          >
            {t("Red")} {member.tickets_closed_by_flag.red}
          </span>
        </div>
      </button>
    );
  };

  return (
    <main className="rm-shell px-3 py-4 sm:px-5">
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <section className="rm-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
                <Trophy className="h-4 w-4" />
                {t("Public Stats")}
              </p>
              <h1 className="mt-2 text-2xl font-bold text-slate-900">
                {t("Technician Top Chart")}
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-600">
                {t(
                  "Ranking is based on a combined system score from closed tasks, XP, first-pass quality, flag quality, attendance, and rework penalties.",
                )}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="h-10"
              onClick={() => {
                if (viewState === "detail" && selectedUserId) {
                  void loadDetail(selectedUserId);
                } else {
                  void loadLeaderboard();
                }
              }}
              disabled={isLoadingLeaderboard || isLoadingDetail}
            >
              <RefreshCcw className="mr-2 h-4 w-4" />
              {t("Refresh")}
            </Button>
          </div>
        </section>

        {viewState === "leaderboard" ? (
          <>
            {leaderboardError ? (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {leaderboardError}
              </p>
            ) : null}

            {isLoadingLeaderboard ? (
              <section className="rm-panel p-6 text-center">
                <p className="inline-flex items-center gap-2 text-sm text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading leaderboard...")}
                </p>
              </section>
            ) : leaderboard ? (
              <>
                <section className="grid gap-3 sm:grid-cols-3">
                  <article className="rm-panel p-4">
                    <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <ShieldCheck className="h-4 w-4" />
                      {t("Technicians")}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                      {leaderboard.summary.technicians_total}
                    </p>
                  </article>
                  <article className="rm-panel p-4">
                    <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <Target className="h-4 w-4" />
                      {t("Closed Tickets")}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                      {leaderboard.summary.tickets_done_total}
                    </p>
                  </article>
                  <article className="rm-panel p-4">
                    <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <Sparkles className="h-4 w-4" />
                      {t("First Pass Rate")}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                      {leaderboard.summary.first_pass_rate_percent}%
                    </p>
                  </article>
                </section>

                <section className="space-y-3">
                  {leaderboard.members.length ? (
                    leaderboard.members.map((member) => renderLeaderboardRow(member))
                  ) : (
                    <section className="rm-panel p-6 text-center text-sm text-slate-600">
                      {t("No technicians available in leaderboard.")}
                    </section>
                  )}
                </section>
              </>
            ) : null}
          </>
        ) : (
          <>
            <section className="rm-panel p-4">
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={closeDetail}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                {t("Back To Leaderboard")}
              </Button>
            </section>

            {detailError ? (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {detailError}
              </p>
            ) : null}

            {isLoadingDetail ? (
              <section className="rm-panel p-6 text-center">
                <p className="inline-flex items-center gap-2 text-sm text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading technician details...")}
                </p>
              </section>
            ) : detail ? (
              <div className="space-y-4">
                <section className="rm-panel p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        {detail.profile.name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        @{detail.profile.username} •{" "}
                        {t("Level {{level}}", { level: detail.profile.level })}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs uppercase tracking-wide text-slate-500">{t("Rank")}</p>
                      <p className="text-2xl font-bold text-slate-900">
                        #{detail.leaderboard_position.rank}
                      </p>
                      <p className="text-xs text-slate-500">
                        {t("Top {{value}}%", {
                          value: detail.leaderboard_position.better_than_percent,
                        })}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">{t("Score")}</p>
                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {detail.leaderboard_position.score}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        {t("Closed Tickets")}
                      </p>
                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {detail.metrics.tickets.tickets_done_total}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        {t("First Pass")}
                      </p>
                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {detail.metrics.tickets.first_pass_rate_percent}%
                      </p>
                    </div>
                  </div>
                </section>

                <section className="rm-panel p-5">
                  <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <BarChart3 className="h-4 w-4" />
                    {t("Why This Rank")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {detail.score_breakdown.contribution_items.map((item) => (
                      <div
                        key={item.key}
                        className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                      >
                        <span className="text-slate-700">
                          {contributionLabel(item.label, t)}
                        </span>
                        <span
                          className={cn(
                            "font-semibold",
                            item.points >= 0 ? "text-emerald-700" : "text-rose-700",
                          )}
                        >
                          {item.points >= 0 ? "+" : ""}
                          {item.points}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
                        {t("Top Positive Factors")}
                      </p>
                      <div className="mt-2 space-y-1">
                        {detail.score_breakdown.reasoning.top_positive_factors.length ? (
                          detail.score_breakdown.reasoning.top_positive_factors.map(
                            (factor) => (
                              <p key={factor.key} className="text-xs text-emerald-800">
                                {contributionLabel(factor.label, t)}: +{factor.points}
                              </p>
                            ),
                          )
                        ) : (
                          <p className="text-xs text-emerald-700">{t("No positive factors.")}</p>
                        )}
                      </div>
                    </div>
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-rose-800">
                        {t("Top Negative Factors")}
                      </p>
                      <div className="mt-2 space-y-1">
                        {detail.score_breakdown.reasoning.top_negative_factors.length ? (
                          detail.score_breakdown.reasoning.top_negative_factors.map(
                            (factor) => (
                              <p key={factor.key} className="text-xs text-rose-800">
                                {contributionLabel(factor.label, t)}: {factor.points}
                              </p>
                            ),
                          )
                        ) : (
                          <p className="text-xs text-rose-700">{t("No negative factors.")}</p>
                        )}
                      </div>
                    </div>
                  </div>
                </section>

                <section className="rm-panel p-5">
                  <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Flag className="h-4 w-4" />
                    {t("Ticket Quality")}
                  </p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                      <p>{t("Done")}: {detail.metrics.tickets.tickets_done_total}</p>
                      <p>{t("First pass")}: {detail.metrics.tickets.tickets_first_pass_total}</p>
                      <p>{t("Rework")}: {detail.metrics.tickets.tickets_rework_total}</p>
                      <p>
                        {t("Avg duration")}: {detail.metrics.tickets.average_resolution_minutes} {t("min")}
                      </p>
                    </div>
                    <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                          flagBadgeClass("green"),
                        )}
                      >
                        {t("Green")} {detail.metrics.tickets.tickets_closed_by_flag.green}
                      </span>
                      <span
                        className={cn(
                          "ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                          flagBadgeClass("yellow"),
                        )}
                      >
                        {t("Yellow")} {detail.metrics.tickets.tickets_closed_by_flag.yellow}
                      </span>
                      <span
                        className={cn(
                          "ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                          flagBadgeClass("red"),
                        )}
                      >
                        {t("Red")} {detail.metrics.tickets.tickets_closed_by_flag.red}
                      </span>
                      <p className="pt-1 text-xs text-slate-600">
                        {t("QC pass events")}: {detail.metrics.tickets.qc_pass_events_total}
                      </p>
                      <p className="text-xs text-slate-600">
                        {t("QC fail events")}: {detail.metrics.tickets.qc_fail_events_total}
                      </p>
                    </div>
                    <div className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Status Counts (All Time)")}
                      </p>
                      {Object.entries(detail.metrics.tickets.status_counts).map(
                        ([status, total]) => (
                          <p key={status} className="text-xs text-slate-700">
                            {translateStatusLabel(status, t)}: {total}
                          </p>
                        ),
                      )}
                    </div>
                  </div>
                </section>

                <section className="grid gap-4 sm:grid-cols-2">
                  <article className="rm-panel p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <Sparkles className="h-4 w-4" />
                      {t("XP Breakdown")}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {t("Total XP")}: {detail.metrics.xp.xp_total}
                    </p>
                    <div className="mt-3 space-y-2">
                      {detail.metrics.xp.entry_type_breakdown.map((item) => (
                        <div
                          key={item.entry_type}
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
                        >
                          <p className="font-semibold text-slate-800">{item.entry_type}</p>
                          <p className="mt-1 text-slate-600">
                            {t("Amount")}: {item.total_amount} • {t("Entries")}: {item.total_count}
                          </p>
                        </div>
                      ))}
                    </div>
                  </article>

                  <article className="rm-panel p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <Activity className="h-4 w-4" />
                      {t("Attendance")}
                    </p>
                    <div className="mt-3 space-y-2 text-sm text-slate-700">
                      <p>{t("Attendance days")}: {detail.metrics.attendance.attendance_days_total}</p>
                      <p>
                        {t("Completed days")}: {detail.metrics.attendance.attendance_completed_days}
                      </p>
                      <p>
                        {t("Avg work/day")}: {detail.metrics.attendance.average_work_minutes_per_day} {t("min")}
                      </p>
                    </div>
                  </article>
                </section>

                <section className="rm-panel p-5">
                  <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Award className="h-4 w-4" />
                    {t("Recent Done Tickets")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {detail.recent.done_tickets.length ? (
                      detail.recent.done_tickets.map((ticket) => (
                        <div
                          key={ticket.id}
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-semibold text-slate-900">
                              {t("Ticket #{{id}}", { id: ticket.id })}
                            </p>
                            <span
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-xs font-semibold",
                                ticket.flag_color === "green"
                                  ? flagBadgeClass("green")
                                  : ticket.flag_color === "yellow"
                                    ? flagBadgeClass("yellow")
                                    : flagBadgeClass("red"),
                              )}
                            >
                              {translateFlagColorLabel(ticket.flag_color, t)}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-600">
                            {t("Duration")}: {ticket.total_duration} {t("min")} • XP: {ticket.xp_amount}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-600">{t("No done tickets yet.")}</p>
                    )}
                  </div>
                </section>

                <section className="rm-panel p-5">
                  <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Sparkles className="h-4 w-4" />
                    {t("Recent XP Activity")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {detail.recent.xp_transactions.length ? (
                      detail.recent.xp_transactions.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="font-semibold text-slate-900">{item.entry_type}</p>
                            <p
                              className={cn(
                                "font-semibold",
                                item.amount >= 0 ? "text-emerald-700" : "text-rose-700",
                              )}
                            >
                              {item.amount >= 0 ? "+" : ""}
                              {item.amount}
                            </p>
                          </div>
                          <p className="mt-1 text-slate-600">
                            {t("Ref")}: {item.reference}
                            {item.description ? ` • ${item.description}` : ""}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-600">{t("No XP transactions yet.")}</p>
                    )}
                  </div>
                </section>
              </div>
            ) : null}
          </>
        )}
      </div>
      <div className="fixed bottom-4 left-4 z-50">
        <LanguageSwitcher
          compact
          className="border-slate-300 bg-white/95 shadow-lg backdrop-blur"
        />
      </div>
    </main>
  );
}
