import {
  ArrowLeft,
  Crown,
  Flame,
  Loader2,
  Medal,
  Sparkles,
  Star,
  Trophy,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { useI18n } from "@/i18n";
import {
  getPublicTechnicianDetail,
  getPublicTechnicianLeaderboard,
  getPublicTechnicianPhoto,
  type PublicTechnicianDetail,
  type PublicTechnicianLeaderboard,
  type PublicTechnicianLeaderboardMember,
} from "@/lib/api";
import { notify } from "@/lib/notify";
import { cn } from "@/lib/utils";
import "@/public-stats/public-stats.css";

type ViewState = "leaderboard" | "detail";
type TopSlot = 1 | 2 | 3;
type TimeTabKey = "daily" | "weekly" | "monthly";

type TimeTab = {
  key: TimeTabKey;
  label: string;
  days: number;
};

const TIME_TABS: TimeTab[] = [
  { key: "daily", label: "Daily", days: 1 },
  { key: "weekly", label: "Weekly", days: 7 },
  { key: "monthly", label: "Monthly", days: 30 },
];

const AUTO_REFRESH_INTERVAL_MS = 10_000;

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

function formatShortDate(value: string): string {
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatDateTimeShort(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function initials(value: string): string {
  const tokens = value.trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) {
    return "?";
  }
  if (tokens.length === 1) {
    return tokens[0].slice(0, 2).toUpperCase();
  }
  return `${tokens[0][0] ?? ""}${tokens[1][0] ?? ""}`.toUpperCase();
}

function normalizeFlagColor(value: string): "green" | "yellow" | "red" {
  const normalized = value.trim().toLowerCase();
  if (normalized === "yellow") {
    return "yellow";
  }
  if (normalized === "red") {
    return "red";
  }
  return "green";
}

function flagChipClass(color: "green" | "yellow" | "red"): string {
  if (color === "green") {
    return "border-emerald-200/80 bg-emerald-300/20 text-emerald-50";
  }
  if (color === "yellow") {
    return "border-amber-200/80 bg-amber-300/20 text-amber-50";
  }
  return "border-rose-200/80 bg-rose-300/20 text-rose-50";
}

function topMember(
  members: PublicTechnicianLeaderboardMember[],
  rank: number,
): PublicTechnicianLeaderboardMember | null {
  return members.find((member) => member.rank === rank) ?? null;
}

function firstPassLabel(value: number): string {
  return `${Number.isFinite(value) ? value.toFixed(1) : "0.0"}%`;
}

function firstPassStars(value: number): number {
  if (value >= 95) {
    return 3;
  }
  if (value >= 90) {
    return 2;
  }
  if (value >= 85) {
    return 1;
  }
  return 0;
}

function compactNumber(value: number): string {
  if (!Number.isFinite(value)) {
    return "0";
  }
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function rowToneClass(rank: number): string {
  if (rank === 1) {
    return "ps-rank-row-top-1";
  }
  if (rank === 2) {
    return "ps-rank-row-top-2";
  }
  if (rank === 3) {
    return "ps-rank-row-top-3";
  }
  return "";
}

function podiumToneClass(slot: TopSlot): string {
  if (slot === 1) {
    return "ps-podium-first";
  }
  if (slot === 2) {
    return "ps-podium-second";
  }
  return "ps-podium-third";
}

function contributionLabel(
  label: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (label === "Closed tickets") {
    return t("Closed Tickets");
  }
  if (label === "XP total") {
    return t("Total XP");
  }
  if (label === "First-pass completions") {
    return t("First Pass");
  }
  if (label === "Quality flags") {
    return t("Ticket Quality");
  }
  if (label === "Attendance consistency") {
    return t("Attendance");
  }
  if (label === "Rework / QC fail penalty") {
    return t("Penalty");
  }
  return t(label);
}

function translateXpEntryTypeLabel(
  entryType: string,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const normalized = entryType.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "attendance_punctuality") {
    return t("Attendance Punctuality");
  }
  if (normalized === "ticket_base_xp") {
    return t("Ticket Base XP");
  }
  if (normalized === "ticket_qc_first_pass_bonus") {
    return t("Ticket QC First Pass Bonus");
  }
  if (normalized === "ticket_qc_status_update") {
    return t("Ticket QC Status Update");
  }
  if (normalized === "manual_adjustment") {
    return t("Manual Adjustment");
  }
  return entryType;
}

function hasOwnPhoto(
  source: Record<number, string | null>,
  userId: number,
): boolean {
  return Object.prototype.hasOwnProperty.call(source, userId);
}

type LazyPublicAvatarProps = {
  userId: number;
  name: string;
  photoUrl: string | null;
  shouldLoad: boolean;
  prioritize?: boolean;
  onVisible: (userId: number, options?: { prioritize?: boolean }) => void;
  className: string;
};

function LazyPublicAvatar({
  userId,
  name,
  photoUrl,
  shouldLoad,
  prioritize = false,
  onVisible,
  className,
}: LazyPublicAvatarProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!shouldLoad) {
      return;
    }
    const root = rootRef.current;
    if (!root) {
      return;
    }

    if (typeof IntersectionObserver === "undefined") {
      onVisible(userId, { prioritize });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries.some((entry) => entry.isIntersecting);
        if (!isVisible) {
          return;
        }
        onVisible(userId, { prioritize });
        observer.disconnect();
      },
      {
        rootMargin: "240px 0px",
      },
    );
    observer.observe(root);
    return () => observer.disconnect();
  }, [onVisible, prioritize, shouldLoad, userId]);

  return (
    <div ref={rootRef} className={className}>
      {photoUrl ? (
        <img
          src={photoUrl}
          alt={name}
          className="h-full w-full object-cover"
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-xs font-black text-white">
          {initials(name)}
        </div>
      )}
    </div>
  );
}

export default function PublicStatsApp() {
  const { t } = useI18n();

  const [timeTab, setTimeTab] = useState<TimeTabKey>("weekly");
  const [leaderboard, setLeaderboard] = useState<PublicTechnicianLeaderboard | null>(null);
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(true);
  const [leaderboardError, setLeaderboardError] = useState("");

  const [selectedUserId, setSelectedUserId] = useState<number | null>(() =>
    parseTechFromLocation(),
  );
  const [detail, setDetail] = useState<PublicTechnicianDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [lazyPhotoByUserId, setLazyPhotoByUserId] = useState<
    Record<number, string | null>
  >({});
  const queuedPhotoIdsRef = useRef<Set<number>>(new Set());
  const loadedPhotoIdsRef = useRef<Set<number>>(new Set());
  const photoQueueRef = useRef<number[]>([]);
  const isPhotoQueueRunningRef = useRef(false);

  const viewState: ViewState = selectedUserId ? "detail" : "leaderboard";

  const activeTimeTab = useMemo(
    () => TIME_TABS.find((tab) => tab.key === timeTab) ?? TIME_TABS[1],
    [timeTab],
  );

  const resolvePhotoEntry = useCallback((userId: number, photoUrl: string | null) => {
    setLazyPhotoByUserId((prev) => {
      const hadValue = hasOwnPhoto(prev, userId);
      if (hadValue && prev[userId] === photoUrl) {
        return prev;
      }
      return {
        ...prev,
        [userId]: photoUrl,
      };
    });
    loadedPhotoIdsRef.current.add(userId);
    queuedPhotoIdsRef.current.delete(userId);
  }, []);

  const fetchPublicPhoto = useCallback(
    async (userId: number): Promise<void> => {
      try {
        const photo = await getPublicTechnicianPhoto(userId);
        resolvePhotoEntry(userId, photo.photo_url ?? null);
      } catch {
        resolvePhotoEntry(userId, null);
      }
    },
    [resolvePhotoEntry],
  );

  const processPhotoQueue = useCallback(() => {
    if (isPhotoQueueRunningRef.current) {
      return;
    }
    const nextUserId = photoQueueRef.current.shift();
    if (!nextUserId) {
      return;
    }

    isPhotoQueueRunningRef.current = true;
    void fetchPublicPhoto(nextUserId).finally(() => {
      isPhotoQueueRunningRef.current = false;
      processPhotoQueue();
    });
  }, [fetchPublicPhoto]);

  const queuePhotoLoad = useCallback(
    (userId: number, options: { prioritize?: boolean } = {}) => {
      const { prioritize = false } = options;
      if (
        loadedPhotoIdsRef.current.has(userId)
        || queuedPhotoIdsRef.current.has(userId)
      ) {
        return;
      }

      queuedPhotoIdsRef.current.add(userId);
      if (prioritize) {
        photoQueueRef.current.unshift(userId);
      } else {
        photoQueueRef.current.push(userId);
      }
      processPhotoQueue();
    },
    [processPhotoQueue],
  );

  const loadLeaderboard = useCallback(
    async (options: { silent?: boolean } = {}) => {
      const { silent = false } = options;
      if (!silent) {
        setIsLoadingLeaderboard(true);
        setLeaderboardError("");
      }

      try {
        const data = await getPublicTechnicianLeaderboard({
          days: activeTimeTab.days,
          include_photo: false,
        });
        setLeaderboard(data);
        setLeaderboardError("");
      } catch (error) {
        setLeaderboardError(
          toErrorMessage(error, t("Could not load public technician leaderboard.")),
        );
      } finally {
        if (!silent) {
          setIsLoadingLeaderboard(false);
        }
      }
    },
    [activeTimeTab.days, t],
  );

  const loadDetail = useCallback(
    async (userId: number, options: { silent?: boolean } = {}) => {
      const { silent = false } = options;
      if (!silent) {
        setIsLoadingDetail(true);
        setDetailError("");
      }

      try {
        const data = await getPublicTechnicianDetail(userId, {
          include_photo: false,
        });
        setDetail(data);
        setDetailError("");
      } catch (error) {
        setDetailError(toErrorMessage(error, t("Could not load technician detail.")));
      } finally {
        if (!silent) {
          setIsLoadingDetail(false);
        }
      }
    },
    [t],
  );

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

  useEffect(() => {
    const timerId = window.setInterval(() => {
      if (selectedUserId) {
        void loadDetail(selectedUserId, { silent: true });
      } else {
        void loadLeaderboard({ silent: true });
      }
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(timerId);
    };
  }, [loadDetail, loadLeaderboard, selectedUserId]);

  useEffect(() => {
    if (leaderboardError) {
      notify("error", leaderboardError);
    }
  }, [leaderboardError]);

  useEffect(() => {
    if (detailError) {
      notify("error", detailError);
    }
  }, [detailError]);

  useEffect(() => {
    if (!leaderboard?.members?.length) {
      return;
    }

    for (const member of leaderboard.members) {
      if (member.photo_url) {
        resolvePhotoEntry(member.user_id, member.photo_url);
        continue;
      }
      if (!member.has_photo) {
        resolvePhotoEntry(member.user_id, null);
        continue;
      }
      if (member.rank <= 3) {
        queuePhotoLoad(member.user_id, { prioritize: true });
      }
    }
  }, [leaderboard, queuePhotoLoad, resolvePhotoEntry]);

  useEffect(() => {
    if (!detail?.profile) {
      return;
    }
    if (detail.profile.photo_url) {
      resolvePhotoEntry(detail.profile.user_id, detail.profile.photo_url);
      return;
    }
    if (!detail.profile.has_photo) {
      resolvePhotoEntry(detail.profile.user_id, null);
      return;
    }
    queuePhotoLoad(detail.profile.user_id, { prioritize: true });
  }, [detail, queuePhotoLoad, resolvePhotoEntry]);

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

  const leaderboardPeriod = useMemo(() => {
    if (!leaderboard) {
      return null;
    }

    const windowDays = leaderboard.period?.days ?? activeTimeTab.days;
    const endDateRaw = leaderboard.period?.end_date ?? leaderboard.generated_at;
    const startDateRaw = leaderboard.period?.start_date ?? (() => {
      const endDate = new Date(endDateRaw);
      if (Number.isNaN(endDate.valueOf())) {
        return "";
      }
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - (windowDays - 1));
      return startDate.toISOString();
    })();

    return {
      days: windowDays,
      startLabel: formatShortDate(startDateRaw),
      endLabel: formatShortDate(endDateRaw),
      updatedAtLabel: formatDateTimeShort(leaderboard.generated_at),
    };
  }, [activeTimeTab.days, leaderboard]);

  const rankedMembers = useMemo(
    () => (leaderboard?.members ?? []).slice().sort((left, right) => left.rank - right.rank),
    [leaderboard?.members],
  );

  const topMembers = useMemo(
    () => ({
      first: topMember(rankedMembers, 1),
      second: topMember(rankedMembers, 2),
      third: topMember(rankedMembers, 3),
    }),
    [rankedMembers],
  );

  const renderAvatar = (
    member: {
      user_id: number;
      name: string;
      has_photo?: boolean;
      photo_url?: string | null;
    },
    sizeClass: string,
    ringClass = "border-violet-100/70",
    options: { prioritize?: boolean } = {},
  ) => {
    const resolvedPhotoUrl = member.photo_url
      ?? (hasOwnPhoto(lazyPhotoByUserId, member.user_id)
        ? lazyPhotoByUserId[member.user_id] ?? null
        : null);
    const hasCachedPhoto = hasOwnPhoto(lazyPhotoByUserId, member.user_id);
    const shouldLoadPhoto = Boolean(
      member.has_photo
      && !resolvedPhotoUrl
      && !hasCachedPhoto,
    );

    return (
      <LazyPublicAvatar
        userId={member.user_id}
        name={member.name}
        photoUrl={resolvedPhotoUrl}
        shouldLoad={shouldLoadPhoto}
        prioritize={options.prioritize}
        onVisible={queuePhotoLoad}
        className={cn(
          "relative overflow-hidden rounded-full border-2 bg-violet-200/20 shadow-[0_14px_28px_-14px_rgba(0,0,0,0.88)]",
          ringClass,
          sizeClass,
        )}
      />
    );
  };

  const renderStars = (rate: number, iconClass = "h-3.5 w-3.5") => {
    const filled = firstPassStars(rate);
    return (
      <div className="inline-flex items-center gap-0.5">
        {[0, 1, 2].map((index) => (
          <Star
            key={index}
            className={cn(
              iconClass,
              index < filled ? "fill-yellow-300 text-yellow-300" : "fill-white/10 text-white/20",
            )}
          />
        ))}
      </div>
    );
  };

  const renderPodiumCard = (member: PublicTechnicianLeaderboardMember | null, slot: TopSlot) => {
    if (!member) {
      return (
        <article className="ps-podium-card border-dashed text-center text-sm text-violet-100/80">
          {t("No technicians available in leaderboard.")}
        </article>
      );
    }

    return (
      <button
        type="button"
        onClick={() => openDetail(member.user_id)}
        className={cn(
          "ps-podium-card w-full text-left",
          podiumToneClass(slot),
          slot === 1 ? "sm:-mt-6" : "",
        )}
      >
        {slot === 1 ? (
          <span className="absolute -top-4 left-1/2 inline-flex -translate-x-1/2 items-center gap-1 rounded-full border border-yellow-100/80 bg-yellow-300 px-3 py-1 text-[11px] font-black uppercase tracking-[0.12em] text-violet-950">
            <Crown className="h-3.5 w-3.5" />
            {t("Champion")}
          </span>
        ) : null}

        <div className="flex items-start justify-between gap-3">
          <span className="ps-rank-badge">{member.rank}</span>
          <span className="rounded-full border border-violet-100/55 bg-violet-100/15 px-2 py-0.5 text-[11px] font-bold text-violet-50">
            L{member.level}
          </span>
        </div>

        <div className="mt-3 flex flex-col items-center text-center">
          {renderAvatar(
            member,
            slot === 1 ? "h-20 w-20" : "h-16 w-16",
            slot === 1 ? "border-yellow-100/85" : "border-violet-100/80",
            { prioritize: true },
          )}
          <p className="mt-2 max-w-full truncate text-sm font-black">{member.name}</p>
          <p className="max-w-full truncate text-xs text-violet-100/80">@{member.username}</p>
          <div className="mt-1">{renderStars(member.first_pass_rate_percent)}</div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-center text-xs">
          <div className="ps-soft-pill rounded-xl px-2 py-1.5">
            <p className="ps-kicker text-[10px] text-violet-100/85">{t("Raw XP")}</p>
            <p className="text-base font-black text-white">{compactNumber(member.xp_total)}</p>
          </div>
          <div className="ps-soft-pill rounded-xl px-2 py-1.5">
            <p className="ps-kicker text-[10px] text-violet-100/85">{t("Avg duration")}</p>
            <p className="text-base font-black text-white">
              {member.average_resolution_minutes} {t("min")}
            </p>
          </div>
        </div>
      </button>
    );
  };

  const renderLeaderboardRow = (member: PublicTechnicianLeaderboardMember) => {
    const flags = member.tickets_closed_by_flag;
    return (
      <button
        key={member.user_id}
        type="button"
        onClick={() => openDetail(member.user_id)}
        className={cn("ps-rank-row w-full text-left text-white", rowToneClass(member.rank))}
      >
        <div className="relative flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="ps-rank-badge">{member.rank}</span>

            {renderAvatar(member, "h-11 w-11 shrink-0")}

            <div className="min-w-0">
              <p className="truncate text-[15px] font-black text-violet-50">{member.name}</p>
              <p className="truncate text-xs text-violet-100/85">@{member.username}</p>
              <div className="mt-1 flex items-center gap-1.5">
                <span className="rounded-full border border-violet-100/65 bg-violet-200/15 px-2 py-0.5 text-[10px] font-bold text-violet-50">
                  L{member.level}
                </span>
                {renderStars(member.first_pass_rate_percent, "h-3 w-3")}
              </div>
            </div>
          </div>

          <div className="shrink-0 text-right">
            <p className="ps-kicker text-[10px] text-violet-100/80">{t("Raw XP")}</p>
            <p className="ps-display text-3xl leading-none text-yellow-300 ps-neon-glow">
              {compactNumber(member.xp_total)}
            </p>
            <p className="text-[11px] font-semibold text-violet-100/80">
              {member.average_resolution_minutes} {t("min")}
            </p>
          </div>
        </div>

        <div className="relative mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
          <span className="rounded-full border border-violet-100/65 bg-violet-200/20 px-2 py-0.5 font-semibold text-violet-100">
            {t("Done")}: {member.tickets_done_total}
          </span>
          <span className="rounded-full border border-violet-100/65 bg-violet-200/20 px-2 py-0.5 font-semibold text-violet-100">
            {t("Rework")}: {member.tickets_rework_total}
          </span>
          <span className={cn("rounded-full border px-2 py-0.5 font-semibold", flagChipClass("green"))}>
            G: {flags.green}
          </span>
          <span className={cn("rounded-full border px-2 py-0.5 font-semibold", flagChipClass("yellow"))}>
            Y: {flags.yellow}
          </span>
          <span className={cn("rounded-full border px-2 py-0.5 font-semibold", flagChipClass("red"))}>
            R: {flags.red}
          </span>
          <span className="rounded-full border border-violet-100/65 bg-violet-200/15 px-2 py-0.5 font-semibold text-violet-100">
            QC {firstPassLabel(member.first_pass_rate_percent)}
          </span>
        </div>
      </button>
    );
  };

  return (
    <main className="public-stats-root min-h-[100svh] px-3 py-5 sm:px-6 sm:py-8">
      <div className="pointer-events-none absolute -left-16 top-16 h-72 w-72 rounded-full bg-fuchsia-300/20 blur-3xl ps-float" />
      <div className="pointer-events-none absolute -right-20 bottom-4 h-96 w-96 rounded-full bg-cyan-300/20 blur-3xl ps-float-slow" />

      <div className="relative mx-auto w-full max-w-6xl space-y-4">
        <section className="ps-panel rounded-[30px] p-5 sm:p-6">
          <div className="absolute -left-6 top-2 h-24 w-24 rounded-full bg-fuchsia-300/25 blur-2xl" />
          <div className="absolute right-4 top-8 h-20 w-20 rounded-full bg-cyan-300/20 blur-2xl" />

          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="ps-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-[0.14em]">
                <Trophy className="h-3.5 w-3.5" />
                {t("Technician Top Chart")}
              </p>
              <h1 className="ps-display mt-3 text-5xl leading-none text-yellow-300 ps-neon-glow sm:text-6xl">
                {t("Leaderboard")}
              </h1>
              <p className="mt-2 max-w-xl text-sm text-violet-100/85">
                Rank, level, raw XP, QC stars, and operational indicators designed for large-screen monitoring.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <LanguageSwitcher compact className="border-violet-100/60 bg-violet-900/55 text-white" />
              <span className="rounded-full border border-violet-100/45 bg-violet-100/10 px-3 py-1 text-[11px] font-semibold text-violet-100/90">
                {t("Auto-refresh every 10 seconds")}
              </span>
            </div>
          </div>

          <div className="relative mt-4 flex flex-wrap items-center gap-2">
            {TIME_TABS.map((tab) => {
              const isActive = tab.key === timeTab;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setTimeTab(tab.key)}
                  className={cn(
                    "rounded-full border px-4 py-1.5 text-xs font-bold uppercase tracking-wide transition",
                    isActive
                      ? "border-yellow-100 bg-yellow-300 text-violet-950"
                      : "border-violet-100/55 bg-violet-200/15 text-violet-100 hover:bg-violet-200/25",
                  )}
                >
                  {t(tab.label)}
                </button>
              );
            })}

            <div className="ml-auto flex flex-wrap items-center gap-2">
              <span className="ps-soft-pill rounded-full px-3 py-1 text-[11px] font-semibold text-violet-100">
                {leaderboardPeriod?.startLabel ?? "-"} - {leaderboardPeriod?.endLabel ?? "-"}
              </span>
              <span className="rounded-full border border-violet-100/45 bg-violet-100/10 px-3 py-1 text-[11px] font-semibold text-violet-100">
                {t("Updated at {{time}}", { time: leaderboardPeriod?.updatedAtLabel ?? "-" })}
              </span>
            </div>
          </div>
        </section>

        {viewState === "leaderboard" ? (
          <>
            {isLoadingLeaderboard ? (
              <section className="ps-panel rounded-[30px] p-8 text-center">
                <p className="inline-flex items-center gap-2 text-sm text-violet-100/85">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading leaderboard...")}
                </p>
              </section>
            ) : leaderboard ? (
              <>
                <section className="ps-panel rounded-[30px] p-4 sm:p-5">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-violet-50">
                      <Crown className="h-4 w-4 text-yellow-300" />
                      Podium Top-3
                    </p>
                    <p className="text-xs text-violet-100/75">
                      Raw XP and QC are prioritized for quick monitor readability.
                    </p>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3 md:items-end">
                    {renderPodiumCard(topMembers.second, 2)}
                    {renderPodiumCard(topMembers.first, 1)}
                    {renderPodiumCard(topMembers.third, 3)}
                  </div>

                  <div className="mx-auto mt-4 grid max-w-md grid-cols-3 gap-2 text-center">
                    <div className="rounded-t-2xl bg-[linear-gradient(180deg,#ffd95d,#f0ad1e)] py-3 ps-display text-4xl text-violet-950">
                      2
                    </div>
                    <div className="rounded-t-2xl bg-[linear-gradient(180deg,#ffe46b,#f0bb1f)] py-4 ps-display text-5xl text-violet-950">
                      1
                    </div>
                    <div className="rounded-t-2xl bg-[linear-gradient(180deg,#ffd95d,#f0ad1e)] py-3 ps-display text-4xl text-violet-950">
                      3
                    </div>
                  </div>
                </section>

                <section className="ps-panel rounded-[30px] p-3 sm:p-4">
                  <div className="grid grid-cols-[auto,1fr,auto] gap-2 rounded-xl border border-violet-100/30 bg-violet-100/10 px-3 py-2 text-[11px] font-bold uppercase tracking-wide text-violet-100/80">
                    <span>{t("Rank")}</span>
                    <span>{t("Name")}</span>
                    <span>{t("Raw XP")}</span>
                  </div>

                  <div className="mt-2 space-y-2">
                    {rankedMembers.length ? (
                      rankedMembers.map((member) => renderLeaderboardRow(member))
                    ) : (
                      <section className="rounded-2xl border border-violet-100/30 bg-violet-900/35 p-6 text-center text-sm text-violet-100/80">
                        {t("No technicians available in leaderboard.")}
                      </section>
                    )}
                  </div>
                </section>
              </>
            ) : null}
          </>
        ) : (
          <>
            <section className="ps-panel rounded-2xl p-3">
              <Button
                type="button"
                variant="outline"
                className="h-10 border-violet-100/55 bg-violet-200/15 text-white hover:bg-violet-200/25"
                onClick={closeDetail}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                {t("Back To Leaderboard")}
              </Button>
            </section>

            {isLoadingDetail ? (
              <section className="ps-panel rounded-[30px] p-8 text-center">
                <p className="inline-flex items-center gap-2 text-sm text-violet-100/85">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("Loading technician details...")}
                </p>
              </section>
            ) : detail ? (
              <div className="space-y-4">
                <section className="ps-panel rounded-[30px] p-5 sm:p-6">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-center gap-3">
                      {renderAvatar(
                        {
                          user_id: detail.profile.user_id,
                          name: detail.profile.name,
                          has_photo: detail.profile.has_photo,
                          photo_url: detail.profile.photo_url,
                        },
                        "h-20 w-20",
                        "border-yellow-100/80",
                        { prioritize: true },
                      )}
                      <div>
                        <p className="text-xl font-black text-violet-50">{detail.profile.name}</p>
                        <p className="text-sm text-violet-100/85">@{detail.profile.username}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="rounded-full border border-violet-100/60 bg-violet-200/20 px-2 py-0.5 text-xs font-bold text-violet-50">
                            L{detail.profile.level}
                          </span>
                          {renderStars(detail.metrics.tickets.first_pass_rate_percent, "h-4 w-4")}
                          <span className="text-xs font-semibold text-violet-100/85">
                            QC {firstPassLabel(detail.metrics.tickets.first_pass_rate_percent)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 lg:min-w-[320px]">
                      <div className="ps-soft-pill rounded-xl px-3 py-2 text-center">
                        <p className="text-[11px] uppercase tracking-wide text-violet-100/80">{t("Rank")}</p>
                        <p className="ps-display text-4xl leading-none text-yellow-300">
                          #{detail.leaderboard_position.rank}
                        </p>
                      </div>
                      <div className="ps-soft-pill rounded-xl px-3 py-2 text-center">
                        <p className="text-[11px] uppercase tracking-wide text-violet-100/80">{t("Score")}</p>
                        <p className="ps-display text-4xl leading-none text-yellow-300">
                          {detail.leaderboard_position.score}
                        </p>
                      </div>
                      <div className="col-span-2 rounded-xl border border-violet-100/40 bg-violet-200/10 px-3 py-2 text-center text-xs font-semibold text-violet-50">
                        {t("Top {{value}}%", { value: detail.leaderboard_position.better_than_percent })}
                      </div>
                    </div>
                  </div>
                </section>

                <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <article className="ps-widget">
                    <p className="ps-kicker text-[11px] text-violet-100/85">{t("Raw XP")}</p>
                    <p className="mt-2 ps-widget-value">{detail.metrics.xp.xp_total}</p>
                  </article>

                  <article className="ps-widget">
                    <p className="ps-kicker text-[11px] text-violet-100/85">QC%</p>
                    <p className="mt-2 ps-widget-value">
                      {firstPassLabel(detail.metrics.tickets.first_pass_rate_percent)}
                    </p>
                  </article>

                  <article className="ps-widget">
                    <p className="ps-kicker text-[11px] text-violet-100/85">{t("Done")}</p>
                    <p className="mt-2 ps-widget-value">{detail.metrics.tickets.tickets_done_total}</p>
                  </article>

                  <article className="ps-widget">
                    <p className="ps-kicker text-[11px] text-violet-100/85">{t("Rework")}</p>
                    <p className="mt-2 ps-widget-value">{detail.metrics.tickets.tickets_rework_total}</p>
                  </article>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <article className="ps-panel rounded-[28px] p-4 sm:p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-violet-50">
                      <Sparkles className="h-4 w-4 text-yellow-300" />
                      {t("Score Breakdown")}
                    </p>
                    <div className="mt-3 space-y-2">
                      {(() => {
                        const maxPoints = Math.max(
                          ...detail.score_breakdown.contribution_items.map((item) => Math.abs(item.points)),
                          1,
                        );

                        return detail.score_breakdown.contribution_items.map((item) => {
                          const isPositive = item.points >= 0;
                          const width = Math.max(
                            6,
                            Math.round((Math.abs(item.points) / maxPoints) * 100),
                          );

                          return (
                            <article
                              key={item.key}
                              className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2"
                            >
                              <div className="flex items-center justify-between gap-2 text-sm">
                                <p className="text-violet-50">{contributionLabel(item.label, t)}</p>
                                <p className={cn("font-bold", isPositive ? "text-emerald-200" : "text-rose-200")}>
                                  {isPositive ? "+" : ""}
                                  {item.points}
                                </p>
                              </div>
                              <div className="mt-2 h-1.5 rounded-full bg-violet-950/65">
                                <div
                                  className={cn(
                                    "h-1.5 rounded-full",
                                    isPositive
                                      ? "bg-gradient-to-r from-emerald-300 to-cyan-300"
                                      : "bg-gradient-to-r from-rose-300 to-orange-300",
                                  )}
                                  style={{ width: `${width}%` }}
                                />
                              </div>
                            </article>
                          );
                        });
                      })()}
                    </div>
                  </article>

                  <article className="ps-panel rounded-[28px] p-4 sm:p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-violet-50">
                      <Flame className="h-4 w-4 text-yellow-300" />
                      {t("Secondary indicators")}
                    </p>

                    <div className="mt-3 grid gap-2 text-sm text-violet-100">
                      <div className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2">
                        <p className="text-xs uppercase tracking-wide text-violet-100/80">Flag mix</p>
                        <p className="mt-1 text-sm">
                          G:{detail.metrics.tickets.tickets_closed_by_flag.green} Y:
                          {detail.metrics.tickets.tickets_closed_by_flag.yellow} R:
                          {detail.metrics.tickets.tickets_closed_by_flag.red}
                        </p>
                      </div>

                      <div className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2">
                        <p className="text-xs uppercase tracking-wide text-violet-100/80">
                          {t("Avg duration")}
                        </p>
                        <p className="mt-1 text-sm">
                          {detail.metrics.tickets.average_resolution_minutes} {t("min")}
                        </p>
                      </div>

                      <div className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2">
                        <p className="text-xs uppercase tracking-wide text-violet-100/80">{t("Attendance days")}</p>
                        <p className="mt-1 text-sm">{detail.metrics.attendance.attendance_days_total}</p>
                      </div>
                    </div>

                    <p className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-violet-50">
                      <Sparkles className="h-4 w-4 text-yellow-300" />
                      {t("XP Breakdown")}
                    </p>
                    <div className="mt-3 space-y-2">
                      {detail.metrics.xp.entry_type_breakdown.slice(0, 6).map((row) => (
                        <div
                          key={row.entry_type}
                          className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2 text-xs text-violet-100"
                        >
                          <p className="font-semibold text-violet-50">
                            {translateXpEntryTypeLabel(row.entry_type, t)}
                          </p>
                          <p className="mt-1 text-violet-100/80">
                            {t("Amount")}: {row.total_amount} • {t("Entries")}: {row.total_count}
                          </p>
                        </div>
                      ))}
                    </div>
                  </article>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <article className="ps-panel rounded-[28px] p-4 sm:p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-violet-50">
                      <Medal className="h-4 w-4 text-yellow-300" />
                      {t("Recent Done Tickets")}
                    </p>
                    <div className="mt-3 space-y-2">
                      {detail.recent.done_tickets.length ? (
                        detail.recent.done_tickets.slice(0, 6).map((ticket) => (
                          <article
                            key={ticket.id}
                            className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-xs font-semibold text-violet-100/80">#{ticket.id}</p>
                              <span
                                className={cn(
                                  "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase",
                                  flagChipClass(normalizeFlagColor(ticket.flag_color)),
                                )}
                              >
                                {ticket.flag_color}
                              </span>
                            </div>
                            <p className="mt-1 text-sm font-semibold text-violet-50">
                              {ticket.title?.trim() || t("Ticket #{{id}}", { id: ticket.id })}
                            </p>
                            <p className="mt-1 text-xs text-violet-100/80">
                              {ticket.total_duration} {t("min")} • {ticket.xp_amount} XP
                              {ticket.finished_at ? ` • ${formatDateTimeShort(ticket.finished_at)}` : ""}
                            </p>
                          </article>
                        ))
                      ) : (
                        <p className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-4 text-sm text-violet-100/80">
                          {t("No done tickets yet.")}
                        </p>
                      )}
                    </div>
                  </article>

                  <article className="ps-panel rounded-[28px] p-4 sm:p-5">
                    <p className="inline-flex items-center gap-2 text-sm font-semibold text-violet-50">
                      <Sparkles className="h-4 w-4 text-yellow-300" />
                      {t("Recent XP Activity")}
                    </p>
                    <div className="mt-3 space-y-2">
                      {detail.recent.xp_transactions.length ? (
                        detail.recent.xp_transactions.slice(0, 6).map((entry) => {
                          const isPositive = entry.amount >= 0;
                          return (
                            <article
                              key={entry.id}
                              className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-2"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-xs font-semibold text-violet-100/80">
                                  {translateXpEntryTypeLabel(entry.entry_type, t)}
                                </p>
                                <p
                                  className={cn(
                                    "text-sm font-bold",
                                    isPositive ? "text-emerald-200" : "text-rose-200",
                                  )}
                                >
                                  {isPositive ? "+" : ""}
                                  {entry.amount}
                                </p>
                              </div>
                              <p className="mt-1 text-xs text-violet-100/80">
                                {entry.description?.trim() || entry.reference}
                              </p>
                              <p className="mt-1 text-[11px] text-violet-100/70">
                                {formatDateTimeShort(entry.created_at)}
                              </p>
                            </article>
                          );
                        })
                      ) : (
                        <p className="rounded-xl border border-violet-100/30 bg-violet-200/10 px-3 py-4 text-sm text-violet-100/80">
                          {t("No XP transactions yet.")}
                        </p>
                      )}
                    </div>
                  </article>
                </section>
              </div>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
