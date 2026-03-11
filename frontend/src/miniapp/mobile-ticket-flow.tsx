import {
  CirclePlay,
  CheckCircle2,
  ClipboardCheck,
  ListTodo,
  Loader2,
  Pause,
  Play,
  PlusSquare,
  RefreshCcw,
  Search,
  ShieldAlert,
  Square,
  Timer,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { useI18n } from "@/i18n";
import {
  assignTicket,
  claimTicket,
  completeTicketParts,
  createTicket,
  getInventoryItem,
  listActivePoolTickets,
  listInventoryItems,
  listParts,
  listTicketWorkSessionHistory,
  listTechnicianTodoTickets,
  listTechnicianOptions,
  listTickets,
  pauseTicketWorkSession,
  qcFailTicket,
  qcPassTicket,
  resumeTicketWorkSession,
  reviewApproveTicket,
  reviewTicketManualMetrics,
  startTicketWork,
  stopTicketWorkSession,
  type InventoryItem,
  type InventoryPart,
  type TechnicianOption,
  type Ticket,
  type TicketColor,
  type TicketFlowPermissions,
  type TicketStatus,
  type WorkSessionStatus,
  type WorkSessionTransition,
} from "@/lib/api";
import { buildInventorySerialSearchQuery } from "@/lib/inventory-search";
import { cn } from "@/lib/utils";

type MobileTicketFlowProps = {
  accessToken: string;
  permissions: TicketFlowPermissions;
  currentUserId: number;
};

type MiniTab = "create" | "review" | "work" | "qc";

type FeedbackState =
  | {
      type: "success" | "error" | "info";
      message: string;
    }
  | null;

type PartDraft = {
  selected: boolean;
};

const TAB_META: Record<
  MiniTab,
  {
    labelKey: string;
    icon: typeof PlusSquare;
    permission: keyof TicketFlowPermissions;
  }
> = {
  create: {
    labelKey: "Create",
    icon: PlusSquare,
    permission: "can_create",
  },
  review: {
    labelKey: "Review",
    icon: ClipboardCheck,
    permission: "can_open_review_panel",
  },
  work: {
    labelKey: "Work",
    icon: ClipboardCheck,
    permission: "can_work",
  },
  qc: {
    labelKey: "QC",
    icon: CheckCircle2,
    permission: "can_qc",
  },
};

const STATUS_LABEL: Record<TicketStatus, string> = {
  under_review: "Under review",
  new: "New",
  assigned: "Assigned",
  in_progress: "In progress",
  waiting_qc: "Waiting QC",
  rework: "Rework",
  done: "Done",
};

const COLOR_LABEL: Record<TicketColor, string> = {
  green: "Green",
  yellow: "Yellow",
  red: "Red",
};

const DEFAULT_RECENT_LIMIT = 10;
const SEARCH_RESULT_LIMIT = 500;
type WorkQueueView = "pool" | "todo";
type DerivedSessionStatus = WorkSessionStatus | "idle";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function statusBadgeClass(status: TicketStatus): string {
  if (status === "under_review") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (status === "new") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (status === "assigned") {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  if (status === "in_progress") {
    return "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700";
  }
  if (status === "waiting_qc") {
    return "border-orange-200 bg-orange-50 text-orange-700";
  }
  if (status === "rework") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function colorPillClass(color: TicketColor): string {
  if (color === "green") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (color === "yellow") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function colorPickerButtonClass(color: TicketColor, isActive: boolean): string {
  if (color === "green") {
    return isActive
      ? "border-emerald-700 bg-emerald-600 text-white"
      : "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (color === "yellow") {
    return isActive
      ? "border-amber-700 bg-amber-400 text-slate-900"
      : "border-amber-200 bg-amber-50 text-amber-800";
  }
  return isActive
    ? "border-rose-700 bg-rose-600 text-white"
    : "border-rose-200 bg-rose-50 text-rose-800";
}

function ticketCardClass(flagColor: TicketColor, isActive: boolean): string {
  if (flagColor === "green") {
    return isActive
      ? "border-emerald-700 bg-emerald-600 text-white"
      : "border-emerald-300 bg-emerald-100 text-emerald-900";
  }
  if (flagColor === "yellow") {
    return isActive
      ? "border-amber-700 bg-amber-300 text-slate-900"
      : "border-amber-300 bg-amber-100 text-amber-900";
  }
  return isActive
    ? "border-rose-700 bg-rose-600 text-white"
    : "border-rose-300 bg-rose-100 text-rose-900";
}

function ticketCardMetaClass(flagColor: TicketColor, isActive: boolean): string {
  if (isActive) {
    return flagColor === "yellow" ? "text-slate-700" : "text-white/85";
  }
  if (flagColor === "green") {
    return "text-emerald-700";
  }
  if (flagColor === "yellow") {
    return "text-amber-800";
  }
  return "text-rose-700";
}

function distinctNumbers(values: number[]): number[] {
  return [...new Set(values)];
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatClock(secondsRaw: number): string {
  const seconds = Math.max(Math.floor(secondsRaw), 0);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secondsRest = seconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secondsRest).padStart(2, "0")}`;
}

function timestampMs(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const ts = new Date(value).valueOf();
  return Number.isFinite(ts) ? ts : null;
}

function deriveSessionSnapshot(
  transitions: WorkSessionTransition[],
  nowMs: number,
): {
  status: DerivedSessionStatus;
  activeSeconds: number;
} {
  const ordered = [...transitions].sort((left, right) => {
    const leftTs = timestampMs(left.event_at) ?? 0;
    const rightTs = timestampMs(right.event_at) ?? 0;
    return leftTs - rightTs;
  });

  let status: DerivedSessionStatus = "idle";
  let activeSeconds = 0;
  let runningSinceMs: number | null = null;

  for (const event of ordered) {
    const eventMs = timestampMs(event.event_at);
    if (eventMs === null) {
      continue;
    }

    if (event.action === "started" || event.action === "resumed") {
      if (runningSinceMs === null) {
        runningSinceMs = eventMs;
      }
      status = "running";
      continue;
    }

    if (event.action === "paused") {
      if (runningSinceMs !== null) {
        activeSeconds += Math.max(Math.floor((eventMs - runningSinceMs) / 1000), 0);
      }
      runningSinceMs = null;
      status = "paused";
      continue;
    }

    if (event.action === "stopped") {
      if (runningSinceMs !== null) {
        activeSeconds += Math.max(Math.floor((eventMs - runningSinceMs) / 1000), 0);
      }
      runningSinceMs = null;
      status = "stopped";
    }
  }

  if (runningSinceMs !== null) {
    activeSeconds += Math.max(Math.floor((nowMs - runningSinceMs) / 1000), 0);
  }

  return {
    status,
    activeSeconds,
  };
}

export function MobileTicketFlow({
  accessToken,
  permissions,
  currentUserId,
}: MobileTicketFlowProps) {
  const { t } = useI18n();
  const availableTabs = useMemo(
    () =>
      (Object.keys(TAB_META) as MiniTab[]).filter(
        (tab) => tab !== "review" && permissions[TAB_META[tab].permission],
      ),
    [permissions],
  );

  const [activeTab, setActiveTab] = useState<MiniTab>(
    availableTabs[0] ?? "create",
  );
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [inventoryCache, setInventoryCache] = useState<Record<number, InventoryItem>>({});
  const inventoryCacheRef = useRef<Record<number, InventoryItem>>({});

  const [createSearch, setCreateSearch] = useState("");
  const [createItems, setCreateItems] = useState<InventoryItem[]>([]);
  const [isLoadingCreateItems, setIsLoadingCreateItems] = useState(false);
  const [allParts, setAllParts] = useState<InventoryPart[]>([]);
  const [isLoadingParts, setIsLoadingParts] = useState(false);
  const [selectedCreateItemId, setSelectedCreateItemId] = useState<number | null>(null);
  const [partDrafts, setPartDrafts] = useState<Record<number, PartDraft>>({});
  const [ticketTitle, setTicketTitle] = useState("");
  const [createTotalMinutes, setCreateTotalMinutes] = useState("");
  const [createFlagColor, setCreateFlagColor] = useState<TicketColor>("green");
  const [createIntakeComment, setCreateIntakeComment] = useState("");
  const [isCreatingTicket, setIsCreatingTicket] = useState(false);

  const [reviewTickets, setReviewTickets] = useState<Ticket[]>([]);
  const [isLoadingReviewTickets, setIsLoadingReviewTickets] = useState(false);
  const [reviewStatusFilter, setReviewStatusFilter] = useState<"all" | "under_review" | "new">(
    "under_review",
  );
  const [reviewSearch, setReviewSearch] = useState("");
  const [selectedReviewTicketId, setSelectedReviewTicketId] = useState<number | null>(null);
  const [technicianOptions, setTechnicianOptions] = useState<TechnicianOption[]>([]);
  const [isLoadingTechnicians, setIsLoadingTechnicians] = useState(false);
  const [selectedTechnicianId, setSelectedTechnicianId] = useState("");
  const [manualColor, setManualColor] = useState<TicketColor>("green");
  const [manualXpAmount, setManualXpAmount] = useState("");
  const [isRunningReviewAction, setIsRunningReviewAction] = useState(false);

  const [workSearch, setWorkSearch] = useState("");
  const [workPoolTickets, setWorkPoolTickets] = useState<Ticket[]>([]);
  const [workTodoTickets, setWorkTodoTickets] = useState<Ticket[]>([]);
  const [isLoadingWorkQueues, setIsLoadingWorkQueues] = useState(false);
  const [workQueueView, setWorkQueueView] = useState<WorkQueueView>("pool");
  const [selectedWorkTicketId, setSelectedWorkTicketId] = useState<number | null>(null);
  const [selectedWorkCompletedPartIds, setSelectedWorkCompletedPartIds] = useState<number[]>(
    [],
  );
  const [workSessionHistory, setWorkSessionHistory] = useState<WorkSessionTransition[]>([]);
  const [isLoadingWorkSessionHistory, setIsLoadingWorkSessionHistory] = useState(false);
  const [workNowMs, setWorkNowMs] = useState(() => Date.now());
  const [isRunningWorkAction, setIsRunningWorkAction] = useState(false);

  const [qcTickets, setQcTickets] = useState<Ticket[]>([]);
  const [isLoadingQcTickets, setIsLoadingQcTickets] = useState(false);
  const [qcSearch, setQcSearch] = useState("");
  const [selectedQcTicketId, setSelectedQcTicketId] = useState<number | null>(null);
  const [selectedQcFailedPartIds, setSelectedQcFailedPartIds] = useState<number[]>([]);
  const [qcFailNote, setQcFailNote] = useState("");
  const [isRunningQcAction, setIsRunningQcAction] = useState(false);

  const statusLabel = useCallback(
    (status: TicketStatus) => t(STATUS_LABEL[status]),
    [t],
  );
  const colorLabel = useCallback(
    (color: TicketColor) => t(COLOR_LABEL[color]),
    [t],
  );
  const sessionStatusLabel = useCallback(
    (status: DerivedSessionStatus) => {
      if (status === "running") {
        return t("Running");
      }
      if (status === "paused") {
        return t("Paused");
      }
      if (status === "stopped") {
        return t("Stopped");
      }
      return t("Not started");
    },
    [t],
  );

  const pendingPartsForTicket = useCallback((ticket: Ticket) => {
    return ticket.ticket_parts.filter(
      (part) => Boolean(part.needs_rework) || !Boolean(part.is_completed),
    );
  }, []);

  const renderPendingPartDetails = useCallback(
    (
      ticket: Ticket,
      flagColor: TicketColor,
      isActive: boolean,
      options?: { limit?: number; className?: string },
    ) => {
      const pending = pendingPartsForTicket(ticket);
      const limit = Math.max(options?.limit ?? 2, 1);
      const textClass = options?.className ?? ticketCardMetaClass(flagColor, isActive);

      if (!pending.length) {
        return <p className={cn("mt-1 text-xs", textClass)}>{t("No pending parts")}</p>;
      }

      return (
        <div className="mt-1 space-y-1">
          {pending.slice(0, limit).map((part) => {
            const detail = `${part.part_name} · ${part.minutes} ${t("min")} · ${colorLabel(part.color)}`;
            return (
              <p
                key={`pending-part-${ticket.id}-${part.id}`}
                className={cn("text-xs", textClass)}
              >
                {part.needs_rework ? `${detail} · ${t("Rework")}` : detail}
              </p>
            );
          })}
          {pending.length > limit ? (
            <p className={cn("text-xs", textClass)}>
              +{pending.length - limit} {t("Pending parts")}
            </p>
          ) : null}
        </div>
      );
    },
    [colorLabel, pendingPartsForTicket, t],
  );

  const cacheInventoryItems = useCallback((items: InventoryItem[]) => {
    if (!items.length) {
      return;
    }
    setInventoryCache((prev) => {
      const next = { ...prev };
      items.forEach((item) => {
        next[item.id] = item;
      });
      return next;
    });
  }, []);

  useEffect(() => {
    inventoryCacheRef.current = inventoryCache;
  }, [inventoryCache]);

  const ensureInventoryLoaded = useCallback(
    async (itemIds: number[]) => {
      const missing = distinctNumbers(itemIds).filter(
        (itemId) => !inventoryCacheRef.current[itemId],
      );
      if (!missing.length) {
        return;
      }

      const loaded = await Promise.all(
        missing.slice(0, 30).map(async (itemId) => {
          try {
            return await getInventoryItem(accessToken, itemId);
          } catch {
            return null;
          }
        }),
      );
      cacheInventoryItems(loaded.filter((item): item is InventoryItem => item !== null));
    },
    [accessToken, cacheInventoryItems],
  );

  const refreshReviewTickets = useCallback(async () => {
    setIsLoadingReviewTickets(true);
    try {
      const search = reviewSearch.trim();
      const normalizedSearch = search.replace(/^#/, "").trim();
      const hasSearch =
        normalizedSearch.length >= 2 || /^\d+$/.test(normalizedSearch);
      const tickets = await listTickets(accessToken, {
        q: hasSearch ? normalizedSearch : undefined,
        status: reviewStatusFilter === "all" ? undefined : reviewStatusFilter,
        per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
      });
      setReviewTickets(tickets);
      void ensureInventoryLoaded(tickets.slice(0, 30).map((ticket) => ticket.inventory_item));
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load review tickets.")),
      });
    } finally {
      setIsLoadingReviewTickets(false);
    }
  }, [accessToken, ensureInventoryLoaded, reviewSearch, reviewStatusFilter, t]);

  const refreshWorkQueues = useCallback(async () => {
    setIsLoadingWorkQueues(true);
    try {
      const search = workSearch.trim();
      const normalizedSearch = search.replace(/^#/, "").trim();
      const hasSearch =
        normalizedSearch.length >= 2 || /^\d+$/.test(normalizedSearch);

      try {
        const [pool, todo] = await Promise.all([
          listActivePoolTickets(accessToken, {
            q: hasSearch ? normalizedSearch : undefined,
            per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
          }),
          listTechnicianTodoTickets(accessToken, {
            q: hasSearch ? normalizedSearch : undefined,
            per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
          }),
        ]);
        setWorkPoolTickets(pool.results);
        setWorkTodoTickets(todo.results);
        void ensureInventoryLoaded(
          [...pool.results, ...todo.results]
            .slice(0, 30)
            .map((ticket) => ticket.inventory_item),
        );
      } catch {
        const queue = await listTickets(accessToken, {
          q: hasSearch ? normalizedSearch : undefined,
          per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
        });
        const activeStatuses = new Set<TicketStatus>(["assigned", "in_progress", "rework"]);
        const todo = queue.filter(
          (ticket) => activeStatuses.has(ticket.status) && ticket.technician === currentUserId,
        );
        const pool = queue.filter(
          (ticket) =>
            activeStatuses.has(ticket.status) &&
            (ticket.technician === null || ticket.technician !== currentUserId),
        );
        setWorkPoolTickets(pool);
        setWorkTodoTickets(todo);
        void ensureInventoryLoaded(
          [...pool, ...todo].slice(0, 30).map((ticket) => ticket.inventory_item),
        );
      }
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load technician queue.")),
      });
    } finally {
      setIsLoadingWorkQueues(false);
    }
  }, [accessToken, currentUserId, ensureInventoryLoaded, t, workSearch]);

  const refreshWorkSessionHistory = useCallback(
    async (ticketId: number) => {
      setIsLoadingWorkSessionHistory(true);
      try {
        const history = await listTicketWorkSessionHistory(accessToken, ticketId, {
          per_page: 300,
        });
        setWorkSessionHistory(history);
      } catch (error) {
        setWorkSessionHistory([]);
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Could not load work session history.")),
        });
      } finally {
        setIsLoadingWorkSessionHistory(false);
      }
    },
    [accessToken, t],
  );

  const refreshQcTickets = useCallback(async () => {
    setIsLoadingQcTickets(true);
    try {
      const search = qcSearch.trim();
      const normalizedSearch = search.replace(/^#/, "").trim();
      const hasSearch =
        normalizedSearch.length >= 2 || /^\d+$/.test(normalizedSearch);
      const queue = await listTickets(accessToken, {
        q: hasSearch ? normalizedSearch : undefined,
        status: "waiting_qc",
        per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
      });
      setQcTickets(queue);
      void ensureInventoryLoaded(queue.slice(0, 30).map((ticket) => ticket.inventory_item));
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load QC queue.")),
      });
    } finally {
      setIsLoadingQcTickets(false);
    }
  }, [accessToken, ensureInventoryLoaded, qcSearch, t]);

  const refreshCreateItems = useCallback(async () => {
    setIsLoadingCreateItems(true);
    try {
      const searchQuery = buildInventorySerialSearchQuery(createSearch);
      const hasSearch = Boolean(searchQuery);
      const items = await listInventoryItems(accessToken, {
        q: searchQuery,
        is_active: true,
        ordering: "-created_at",
        per_page: hasSearch ? SEARCH_RESULT_LIMIT : DEFAULT_RECENT_LIMIT,
      });
      setCreateItems(items);
      cacheInventoryItems(items);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load inventory items.")),
      });
    } finally {
      setIsLoadingCreateItems(false);
    }
  }, [accessToken, cacheInventoryItems, createSearch, t]);

  const refreshParts = useCallback(async () => {
    setIsLoadingParts(true);
    try {
      const parts = await listParts(accessToken);
      setAllParts(parts);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load parts.")),
      });
    } finally {
      setIsLoadingParts(false);
    }
  }, [accessToken, t]);

  const refreshTechnicians = useCallback(async () => {
    setIsLoadingTechnicians(true);
    try {
      const technicians = await listTechnicianOptions(accessToken);
      setTechnicianOptions(technicians);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not load technician list.")),
      });
    } finally {
      setIsLoadingTechnicians(false);
    }
  }, [accessToken, t]);

  useEffect(() => {
    if (!feedback) {
      return;
    }
    const timer = window.setTimeout(() => setFeedback(null), 4200);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  useEffect(() => {
    if (!availableTabs.length) {
      return;
    }
    if (availableTabs.includes(activeTab)) {
      return;
    }
    setActiveTab(availableTabs[0]);
  }, [activeTab, availableTabs]);

  useEffect(() => {
    if (!permissions.can_create || activeTab !== "create") {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshCreateItems();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeTab, permissions.can_create, refreshCreateItems]);

  useEffect(() => {
    if (!permissions.can_create || activeTab !== "create" || allParts.length) {
      return;
    }
    void refreshParts();
  }, [activeTab, allParts.length, permissions.can_create, refreshParts]);

  useEffect(() => {
    if (!permissions.can_open_review_panel || activeTab !== "review") {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshReviewTickets();
    }, 250);
    if (permissions.can_assign && !technicianOptions.length) {
      void refreshTechnicians();
    }
    return () => window.clearTimeout(timer);
  }, [
    activeTab,
    permissions.can_assign,
    permissions.can_open_review_panel,
    refreshReviewTickets,
    refreshTechnicians,
    technicianOptions.length,
  ]);

  useEffect(() => {
    if (!permissions.can_qc || activeTab !== "qc") {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshQcTickets();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeTab, permissions.can_qc, refreshQcTickets]);

  useEffect(() => {
    if (!permissions.can_work || activeTab !== "work") {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshWorkQueues();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeTab, permissions.can_work, refreshWorkQueues]);

  const selectedCreateItem = useMemo(() => {
    if (selectedCreateItemId === null) {
      return null;
    }
    return (
      createItems.find((item) => item.id === selectedCreateItemId) ??
      inventoryCache[selectedCreateItemId] ??
      null
    );
  }, [createItems, inventoryCache, selectedCreateItemId]);

  const selectedCreateParts = useMemo(() => {
    if (!selectedCreateItem) {
      return [];
    }
    const seen = new Set<number>();
    return allParts
      .filter((part) => {
        if (seen.has(part.id)) {
          return false;
        }
        const byItem = (part.inventory_item ?? null) === selectedCreateItem.id;
        const byCategory =
          part.category !== null && part.category === selectedCreateItem.category;
        if (!byItem && !byCategory) {
          return false;
        }
        seen.add(part.id);
        return true;
      })
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [allParts, selectedCreateItem]);

  useEffect(() => {
    if (!selectedCreateItem) {
      setPartDrafts({});
      return;
    }
    setPartDrafts((prev) => {
      const next: Record<number, PartDraft> = {};
      selectedCreateParts.forEach((part) => {
        next[part.id] = prev[part.id] ?? {
          selected: false,
        };
      });
      return next;
    });
  }, [selectedCreateItem, selectedCreateParts]);

  useEffect(() => {
    setCreateTotalMinutes("");
    setCreateFlagColor("green");
    setCreateIntakeComment("");
  }, [selectedCreateItemId]);

  const selectedPartsCount = useMemo(
    () =>
      selectedCreateParts.filter((part) => {
        const draft = partDrafts[part.id];
        return Boolean(draft?.selected);
      }).length,
    [partDrafts, selectedCreateParts],
  );

  const reviewTicketsFiltered = useMemo(() => {
    return reviewTickets.filter((ticket) => {
      if (reviewStatusFilter !== "all" && ticket.status !== reviewStatusFilter) {
        return false;
      }
      return true;
    });
  }, [reviewStatusFilter, reviewTickets]);

  useEffect(() => {
    if (!reviewTicketsFiltered.length) {
      setSelectedReviewTicketId(null);
      return;
    }
    if (
      selectedReviewTicketId !== null &&
      reviewTicketsFiltered.some((ticket) => ticket.id === selectedReviewTicketId)
    ) {
      return;
    }
    setSelectedReviewTicketId(reviewTicketsFiltered[0].id);
  }, [reviewTicketsFiltered, selectedReviewTicketId]);

  const selectedReviewTicket = useMemo(
    () =>
      reviewTicketsFiltered.find((ticket) => ticket.id === selectedReviewTicketId) ?? null,
    [reviewTicketsFiltered, selectedReviewTicketId],
  );

  useEffect(() => {
    if (!selectedReviewTicket) {
      return;
    }
    setSelectedTechnicianId(
      selectedReviewTicket.technician ? String(selectedReviewTicket.technician) : "",
    );
    setManualColor(selectedReviewTicket.flag_color);
    setManualXpAmount(String(selectedReviewTicket.xp_amount ?? 0));
  }, [selectedReviewTicket]);

  const workPoolFiltered = useMemo(() => workPoolTickets, [workPoolTickets]);
  const workTodoFiltered = useMemo(() => workTodoTickets, [workTodoTickets]);
  const workCombined = useMemo(() => {
    const seen = new Set<number>();
    const merged: Ticket[] = [];
    [...workTodoFiltered, ...workPoolFiltered].forEach((ticket) => {
      if (seen.has(ticket.id)) {
        return;
      }
      seen.add(ticket.id);
      merged.push(ticket);
    });
    return merged;
  }, [workPoolFiltered, workTodoFiltered]);

  useEffect(() => {
    if (!workCombined.length) {
      setSelectedWorkTicketId(null);
      return;
    }
    if (
      selectedWorkTicketId !== null &&
      workCombined.some((ticket) => ticket.id === selectedWorkTicketId)
    ) {
      return;
    }
    setSelectedWorkTicketId(workCombined[0].id);
  }, [selectedWorkTicketId, workCombined]);

  const selectedWorkTicket = useMemo(
    () => workCombined.find((ticket) => ticket.id === selectedWorkTicketId) ?? null,
    [selectedWorkTicketId, workCombined],
  );

  const isSelectedWorkTicketFromPool = useMemo(
    () =>
      selectedWorkTicket
        ? workPoolFiltered.some((ticket) => ticket.id === selectedWorkTicket.id)
        : false,
    [selectedWorkTicket, workPoolFiltered],
  );
  const isSelectedWorkTicketFromTodo = useMemo(
    () =>
      selectedWorkTicket
        ? workTodoFiltered.some((ticket) => ticket.id === selectedWorkTicket.id)
        : false,
    [selectedWorkTicket, workTodoFiltered],
  );

  useEffect(() => {
    setSelectedWorkCompletedPartIds([]);
    setWorkSessionHistory([]);
    setWorkNowMs(Date.now());
  }, [selectedWorkTicketId]);

  useEffect(() => {
    if (!selectedWorkTicket || !isSelectedWorkTicketFromTodo) {
      setWorkSessionHistory([]);
      return;
    }
    void refreshWorkSessionHistory(selectedWorkTicket.id);
  }, [isSelectedWorkTicketFromTodo, refreshWorkSessionHistory, selectedWorkTicket]);

  const selectedWorkSessionSnapshot = useMemo(
    () => deriveSessionSnapshot(workSessionHistory, workNowMs),
    [workNowMs, workSessionHistory],
  );

  useEffect(() => {
    if (selectedWorkSessionSnapshot.status !== "running") {
      return;
    }
    const timer = window.setInterval(() => {
      setWorkNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [selectedWorkSessionSnapshot.status]);

  useEffect(() => {
    if (!selectedWorkTicket) {
      return;
    }
    if (isSelectedWorkTicketFromTodo) {
      setWorkQueueView("todo");
      return;
    }
    if (isSelectedWorkTicketFromPool) {
      setWorkQueueView("pool");
    }
  }, [isSelectedWorkTicketFromPool, isSelectedWorkTicketFromTodo, selectedWorkTicket]);

  const qcTicketsFiltered = useMemo(() => {
    return qcTickets;
  }, [qcTickets]);

  useEffect(() => {
    if (!qcTicketsFiltered.length) {
      setSelectedQcTicketId(null);
      return;
    }
    if (
      selectedQcTicketId !== null &&
      qcTicketsFiltered.some((ticket) => ticket.id === selectedQcTicketId)
    ) {
      return;
    }
    setSelectedQcTicketId(qcTicketsFiltered[0].id);
  }, [qcTicketsFiltered, selectedQcTicketId]);

  const selectedQcTicket = useMemo(
    () => qcTicketsFiltered.find((ticket) => ticket.id === selectedQcTicketId) ?? null,
    [qcTicketsFiltered, selectedQcTicketId],
  );

  useEffect(() => {
    setSelectedQcFailedPartIds([]);
    setQcFailNote("");
  }, [selectedQcTicketId]);

  const updatePartDraft = useCallback(
    (partId: number, patch: Partial<PartDraft>) => {
      setPartDrafts((prev) => ({
        ...prev,
        [partId]: {
          ...(prev[partId] ?? {
            selected: false,
          }),
          ...patch,
        },
      }));
    },
    [],
  );

  const handleCreateTicket = useCallback(async () => {
    if (!selectedCreateItem) {
      setFeedback({
        type: "info",
        message: t("Select an inventory item first."),
      });
      return;
    }

    const selectedPartSpecs = selectedCreateParts
      .filter((part) => partDrafts[part.id]?.selected)
      .map((part) => ({
        part_id: part.id,
      }));

    if (!selectedPartSpecs.length) {
      setFeedback({
        type: "info",
        message: t("Select at least one part for the ticket."),
      });
      return;
    }

    const parsedTotalMinutes = Number.parseInt(createTotalMinutes, 10);
    if (!Number.isFinite(parsedTotalMinutes) || parsedTotalMinutes < 1) {
      setFeedback({
        type: "error",
        message: t("Total minutes must be at least 1."),
      });
      return;
    }

    setIsCreatingTicket(true);
    try {
      await createTicket(accessToken, {
        serial_number: selectedCreateItem.serial_number,
        title: ticketTitle.trim() || undefined,
        total_minutes: parsedTotalMinutes,
        flag_color: createFlagColor,
        intake_comment: createIntakeComment.trim() || undefined,
        part_specs: selectedPartSpecs,
      });
      setFeedback({
        type: "success",
        message: t("Ticket created successfully."),
      });
      setSelectedCreateItemId(null);
      setPartDrafts({});
      setTicketTitle("");
      setCreateTotalMinutes("");
      setCreateFlagColor("green");
      setCreateIntakeComment("");
      void Promise.all([refreshReviewTickets(), refreshQcTickets(), refreshWorkQueues()]);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not create ticket.")),
      });
    } finally {
      setIsCreatingTicket(false);
    }
  }, [
    accessToken,
    createFlagColor,
    createIntakeComment,
    createTotalMinutes,
    partDrafts,
    refreshQcTickets,
    refreshReviewTickets,
    refreshWorkQueues,
    selectedCreateItem,
    selectedCreateParts,
    ticketTitle,
    t,
  ]);

  const handleReviewApproveAndAssign = useCallback(async () => {
    if (!selectedReviewTicket) {
      return;
    }

    if (!permissions.can_approve_and_assign) {
      setFeedback({
        type: "error",
        message: t("You do not have permission to approve and assign tickets."),
      });
      return;
    }

    const technicianId = Number.parseInt(selectedTechnicianId, 10);
    if (!Number.isFinite(technicianId) || technicianId <= 0) {
      setFeedback({
        type: "info",
        message: t("Select a technician to assign."),
      });
      return;
    }

    setIsRunningReviewAction(true);
    try {
      const reviewedTicket =
        selectedReviewTicket.approved_at && selectedReviewTicket.approved_by
          ? selectedReviewTicket
          : await reviewApproveTicket(accessToken, selectedReviewTicket.id);
      await assignTicket(accessToken, reviewedTicket.id, technicianId);
      setFeedback({
        type: "success",
        message: t("Ticket approved and assigned."),
      });
      await Promise.all([refreshReviewTickets(), refreshWorkQueues()]);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not approve and assign ticket.")),
      });
    } finally {
      setIsRunningReviewAction(false);
    }
  }, [
    accessToken,
    permissions.can_approve_and_assign,
    refreshReviewTickets,
    refreshWorkQueues,
    selectedReviewTicket,
    selectedTechnicianId,
    t,
  ]);

  const handleReviewManualMetrics = useCallback(async () => {
    if (!selectedReviewTicket) {
      return;
    }
    const xpAmount = Number.parseInt(manualXpAmount, 10);
    if (!Number.isFinite(xpAmount) || xpAmount < 0) {
      setFeedback({
        type: "error",
        message: t("XP amount must be 0 or higher."),
      });
      return;
    }

    setIsRunningReviewAction(true);
    try {
      await reviewTicketManualMetrics(accessToken, selectedReviewTicket.id, {
        flag_color: manualColor,
        xp_amount: xpAmount,
      });
      setFeedback({
        type: "success",
        message: t("Manual metrics updated for ticket #{{id}}.", {
          id: selectedReviewTicket.id,
        }),
      });
      await refreshReviewTickets();
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not update manual metrics.")),
      });
    } finally {
      setIsRunningReviewAction(false);
    }
  }, [
    accessToken,
    manualColor,
    manualXpAmount,
    refreshReviewTickets,
    selectedReviewTicket,
    t,
  ]);

  const handleClaimWorkTicket = useCallback(async (ticketId: number) => {
    if (!permissions.can_work) {
      return;
    }
    setIsRunningWorkAction(true);
    try {
      await claimTicket(accessToken, ticketId);
      setFeedback({
        type: "success",
        message: t("Ticket claimed."),
      });
      await Promise.all([refreshWorkQueues(), refreshQcTickets()]);
      setSelectedWorkTicketId(ticketId);
      setWorkQueueView("todo");
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not claim ticket.")),
      });
    } finally {
      setIsRunningWorkAction(false);
    }
  }, [accessToken, permissions.can_work, refreshQcTickets, refreshWorkQueues, t]);

  const handleWorkSessionAction = useCallback(
    async (
      ticketId: number,
      action: "start" | "pause" | "resume" | "stop",
    ) => {
      if (!permissions.can_work) {
        return;
      }
      setIsRunningWorkAction(true);
      try {
        if (action === "start") {
          await startTicketWork(accessToken, ticketId);
        } else if (action === "pause") {
          await pauseTicketWorkSession(accessToken, ticketId);
        } else if (action === "resume") {
          await resumeTicketWorkSession(accessToken, ticketId);
        } else {
          await stopTicketWorkSession(accessToken, ticketId);
        }

        if (action === "start") {
          setFeedback({ type: "success", message: t("Work started.") });
        } else if (action === "pause") {
          setFeedback({ type: "success", message: t("Work paused.") });
        } else if (action === "resume") {
          setFeedback({ type: "success", message: t("Work resumed.") });
        } else {
          setFeedback({
            type: "success",
            message: t("Work stopped. Select completed parts."),
          });
        }

        await Promise.all([refreshWorkQueues(), refreshQcTickets()]);
        await refreshWorkSessionHistory(ticketId);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Could not update work session.")),
        });
      } finally {
        setIsRunningWorkAction(false);
      }
    },
    [
      accessToken,
      permissions.can_work,
      refreshQcTickets,
      refreshWorkQueues,
      refreshWorkSessionHistory,
      t,
    ],
  );

  const handleSubmitWorkCompletion = useCallback(async () => {
    if (!permissions.can_work || !selectedWorkTicket) {
      return;
    }
    if (!selectedWorkCompletedPartIds.length) {
      setFeedback({
        type: "info",
        message: t("Select at least one completed part."),
      });
      return;
    }

    setIsRunningWorkAction(true);
    try {
      await completeTicketParts(accessToken, selectedWorkTicket.id, {
        completed_part_ids: selectedWorkCompletedPartIds,
      });
      setFeedback({
        type: "success",
        message: t("Part completion submitted."),
      });
      setSelectedWorkCompletedPartIds([]);
      await Promise.all([refreshWorkQueues(), refreshQcTickets()]);
      setWorkQueueView("pool");
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Could not submit part completion.")),
      });
    } finally {
      setIsRunningWorkAction(false);
    }
  }, [
    accessToken,
    permissions.can_work,
    refreshQcTickets,
    refreshWorkQueues,
    selectedWorkCompletedPartIds,
    selectedWorkTicket,
    t,
  ]);

  const handleQcDecision = useCallback(
    async (decision: "pass" | "fail") => {
      if (!selectedQcTicket) {
        return;
      }
      if (decision === "fail" && !selectedQcFailedPartIds.length) {
        setFeedback({
          type: "error",
          message: t("Select at least one failed part."),
        });
        return;
      }
      setIsRunningQcAction(true);
      try {
        if (decision === "pass") {
          await qcPassTicket(accessToken, selectedQcTicket.id);
        } else {
          await qcFailTicket(accessToken, selectedQcTicket.id, {
            failed_part_ids: selectedQcFailedPartIds,
            note: qcFailNote.trim() || undefined,
          });
        }
        setFeedback({
          type: "success",
          message:
            decision === "pass"
              ? t("QC passed for ticket #{{id}}.", { id: selectedQcTicket.id })
              : t("QC failed for ticket #{{id}}.", { id: selectedQcTicket.id }),
        });
        await Promise.all([refreshQcTickets(), refreshReviewTickets(), refreshWorkQueues()]);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Could not process QC action.")),
        });
      } finally {
        setIsRunningQcAction(false);
      }
    },
    [
      accessToken,
      refreshQcTickets,
      refreshReviewTickets,
      refreshWorkQueues,
      selectedQcFailedPartIds,
      qcFailNote,
      selectedQcTicket,
      t,
    ],
  );

  const renderCreateTab = () => (
    <div className="space-y-3">
      <section className="rm-panel p-4">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            value={createSearch}
            onChange={(event) => setCreateSearch(event.target.value)}
            className="rm-input h-11"
            placeholder={t("Search by serial or name")}
          />
          <Button
            type="button"
            variant="outline"
            className="h-11 px-3"
            onClick={() => {
              void refreshCreateItems();
              if (!allParts.length) {
                void refreshParts();
              }
            }}
            disabled={isLoadingCreateItems || isLoadingParts}
          >
            <RefreshCcw className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {t("Select an item to create a new repair ticket.")}
        </p>

        <div className="mt-3 max-h-[34svh] space-y-2 overflow-y-auto pr-1">
          {isLoadingCreateItems ? (
            <p className="text-sm text-slate-600">{t("Loading items...")}</p>
          ) : createItems.length ? (
            createItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedCreateItemId(item.id)}
                className={cn(
                  "w-full rounded-xl border px-3 py-3 text-left transition",
                  selectedCreateItemId === item.id
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-slate-50 text-slate-900",
                )}
              >
                <p className="text-sm font-semibold">{item.serial_number}</p>
                <p
                  className={cn(
                    "mt-1 text-xs",
                    selectedCreateItemId === item.id ? "text-slate-200" : "text-slate-600",
                  )}
                >
                  {item.name}
                </p>
              </button>
            ))
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-sm text-slate-500">
              {t("No matching inventory items.")}
            </p>
          )}
        </div>
      </section>

      <section className="rm-panel p-4">
        {selectedCreateItem ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-sm font-semibold text-slate-900">
                {selectedCreateItem.serial_number}
              </p>
              <p className="text-xs text-slate-600">{selectedCreateItem.name}</p>
            </div>

            <input
              value={ticketTitle}
              onChange={(event) => setTicketTitle(event.target.value)}
              className="rm-input h-11"
              placeholder={t("Ticket title (optional)")}
            />

            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-900">{t("Parts")}</p>
              <span className="text-xs text-slate-500">
                {t("Selected")}: {selectedPartsCount}
              </span>
            </div>

            {isLoadingParts ? (
              <p className="text-sm text-slate-600">{t("Loading parts...")}</p>
            ) : selectedCreateParts.length ? (
              <div className="max-h-[44svh] space-y-2 overflow-y-auto pr-1">
                {selectedCreateParts.map((part) => {
                  const draft = partDrafts[part.id] ?? {
                    selected: false,
                  };
                  return (
                    <div
                      key={part.id}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-3"
                    >
                      <label className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-slate-900">
                          {part.name}
                        </span>
                        <input
                          type="checkbox"
                          checked={draft.selected}
                          onChange={(event) =>
                            updatePartDraft(part.id, { selected: event.target.checked })
                          }
                          className="h-5 w-5 accent-slate-900"
                        />
                      </label>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-700">
                {t("No parts are configured for this item category.")}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2">
              <input
                className="rm-input h-10"
                type="number"
                min={1}
                value={createTotalMinutes}
                onChange={(event) => setCreateTotalMinutes(event.target.value)}
                placeholder={t("Total minutes")}
              />
              <select
                className="rm-input h-10"
                value={createFlagColor}
                onChange={(event) =>
                  setCreateFlagColor(event.target.value as TicketColor)
                }
              >
                {(["green", "yellow", "red"] as TicketColor[]).map((color) => (
                  <option key={`create-flag-${color}`} value={color}>
                    {colorLabel(color)}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              className="rm-input min-h-[80px] resize-y py-2"
              value={createIntakeComment}
              onChange={(event) => setCreateIntakeComment(event.target.value)}
              placeholder={t("Comment (optional)")}
            />

            <Button
              type="button"
              className="h-11 w-full"
              disabled={
                isCreatingTicket ||
                isLoadingParts ||
                !selectedCreateItem ||
                !selectedCreateParts.length ||
                !Number.isInteger(Number.parseInt(createTotalMinutes, 10)) ||
                Number.parseInt(createTotalMinutes, 10) < 1
              }
              onClick={() => void handleCreateTicket()}
            >
              {isCreatingTicket ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("Creating ticket...")}
                </>
              ) : (
                t("Create Ticket")
              )}
            </Button>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Choose an inventory item to start ticket creation.")}
          </p>
        )}
      </section>
    </div>
  );

  const renderReviewTab = () => (
    <div className="space-y-3">
      <section className="rm-panel p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-900">{t("Review queue")}</p>
          <Button
            type="button"
            variant="outline"
            className="h-9 px-3"
            onClick={() => void refreshReviewTickets()}
            disabled={isLoadingReviewTickets}
          >
            <RefreshCcw className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-2 grid grid-cols-3 gap-2">
          {([
            { value: "under_review", label: t("Under review") },
            { value: "new", label: t("New") },
            { value: "all", label: t("All") },
          ] as const).map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setReviewStatusFilter(option.value)}
              className={cn(
                "rounded-lg border px-2 py-2 text-xs font-semibold",
                reviewStatusFilter === option.value
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-slate-50 text-slate-700",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="mt-2 flex items-center gap-2">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            className="rm-input h-10"
            value={reviewSearch}
            onChange={(event) => setReviewSearch(event.target.value)}
            placeholder={t("Search ticket id, serial, title")}
          />
        </div>

        <div className="mt-3 max-h-[32svh] space-y-2 overflow-y-auto pr-1">
          {isLoadingReviewTickets ? (
            <p className="text-sm text-slate-600">{t("Loading tickets...")}</p>
          ) : reviewTicketsFiltered.length ? (
            reviewTicketsFiltered.map((ticket) => {
              const serial =
                inventoryCache[ticket.inventory_item]?.serial_number ??
                t("Item #{{id}}", { id: ticket.inventory_item });
              return (
                <button
                  key={ticket.id}
                  type="button"
                  onClick={() => {
                    setSelectedReviewTicketId(ticket.id);
                    void ensureInventoryLoaded([ticket.inventory_item]);
                  }}
                  className={cn(
                    "w-full rounded-xl border px-3 py-3 text-left transition",
                    selectedReviewTicketId === ticket.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-900",
                  )}
                >
                  <p className="text-sm font-semibold">#{ticket.id}</p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {serial}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {statusLabel(ticket.status)}
                  </p>
                </button>
              );
            })
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-sm text-slate-500">
              {t("No tickets found.")}
            </p>
          )}
        </div>
      </section>

      <section className="rm-panel p-4">
        {selectedReviewTicket ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  {t("Ticket #{{id}}", { id: selectedReviewTicket.id })}
                </p>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                    statusBadgeClass(selectedReviewTicket.status),
                  )}
                >
                  {statusLabel(selectedReviewTicket.status)}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                {
                  inventoryCache[selectedReviewTicket.inventory_item]?.serial_number ??
                  t("Item #{{id}}", { id: selectedReviewTicket.inventory_item })
                }
              </p>
              {selectedReviewTicket.title ? (
                <p className="mt-1 text-xs text-slate-600">{selectedReviewTicket.title}</p>
              ) : null}
            </div>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
              <p className="text-sm font-semibold text-slate-900">{t("Part specs")}</p>
              {selectedReviewTicket.ticket_parts.length ? (
                selectedReviewTicket.ticket_parts.map((part) => (
                  <div
                    key={part.id}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-slate-900">{part.part_name}</p>
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                          colorPillClass(part.color),
                        )}
                      >
                        {colorLabel(part.color)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      {t("Minutes")}: {part.minutes}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {t("Comment")}: {part.comment || "-"}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500">{t("No part specs.")}</p>
              )}
            </div>

            {permissions.can_review || permissions.can_assign ? (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
                <p className="text-sm font-semibold text-slate-900">
                  {t("Assign technician")}
                </p>
                <select
                  className="rm-input h-11"
                  value={selectedTechnicianId}
                  onChange={(event) => setSelectedTechnicianId(event.target.value)}
                  disabled={!permissions.can_approve_and_assign || isRunningReviewAction}
                >
                  <option value="">
                    {isLoadingTechnicians
                      ? t("Loading technicians...")
                      : t("Select technician")}
                  </option>
                  {technicianOptions.map((technician) => (
                    <option
                      key={technician.user_id}
                      value={String(technician.user_id)}
                    >
                      {technician.name === technician.username
                        ? technician.username
                        : `${technician.name} (@${technician.username})`}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  className="h-11 w-full"
                  onClick={() => void handleReviewApproveAndAssign()}
                  disabled={
                    isRunningReviewAction ||
                    !selectedTechnicianId ||
                    !permissions.can_approve_and_assign
                  }
                >
                  {t("Approve & Assign")}
                </Button>
                {!permissions.can_approve_and_assign ? (
                  <p className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                    {t("You do not have permission to approve and assign tickets.")}
                  </p>
                ) : null}
              </div>
            ) : null}

            {permissions.can_manual_metrics ? (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
                <p className="text-sm font-semibold text-slate-900">{t("Manual metrics")}</p>
                <div className="grid grid-cols-3 gap-2">
                  {(["green", "yellow", "red"] as TicketColor[]).map((color) => (
                    <button
                      key={`manual-${color}`}
                      type="button"
                      onClick={() => setManualColor(color)}
                      className={cn(
                        "rounded-lg border px-2 py-2 text-xs font-semibold",
                        colorPickerButtonClass(color, manualColor === color),
                      )}
                    >
                      {colorLabel(color)}
                    </button>
                  ))}
                </div>
                <input
                  className="rm-input h-11"
                  type="number"
                  min={0}
                  value={manualXpAmount}
                  onChange={(event) => setManualXpAmount(event.target.value)}
                  placeholder={t("XP amount")}
                />
                <Button
                  type="button"
                  className="h-11 w-full"
                  variant="outline"
                  onClick={() => void handleReviewManualMetrics()}
                  disabled={isRunningReviewAction}
                >
                  {t("Save Manual Metrics")}
                </Button>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Select a review ticket to continue.")}
          </p>
        )}
      </section>
    </div>
  );

  const renderWorkTab = () => {
    const isSelectedFromPool = isSelectedWorkTicketFromPool;
    const isSelectedFromTodo = isSelectedWorkTicketFromTodo;
    const selectedPartSet = new Set(selectedWorkCompletedPartIds);
    const visibleTickets = workQueueView === "pool" ? workPoolFiltered : workTodoFiltered;
    const selectedWorkSessionStatus: DerivedSessionStatus = isSelectedFromTodo
      ? selectedWorkSessionSnapshot.status
      : "idle";
    const workedSeconds = selectedWorkSessionSnapshot.activeSeconds;

    const plannedSeconds = Math.max((selectedWorkTicket?.total_duration ?? 0) * 60, 0);
    const totalParts = selectedWorkTicket?.ticket_parts.length ?? 0;
    const completedParts = selectedWorkTicket
      ? selectedWorkTicket.ticket_parts.filter((part) => Boolean(part.is_completed)).length
      : 0;
    const pendingParts = selectedWorkTicket ? pendingPartsForTicket(selectedWorkTicket) : [];
    const progressPercent =
      totalParts > 0 ? Math.min(Math.round((completedParts / totalParts) * 100), 100) : 0;
    const selectedWorkTicketStatus = selectedWorkTicket?.status ?? null;

    const canStartWork =
      selectedWorkTicketStatus !== null &&
      isSelectedFromTodo &&
      (selectedWorkTicketStatus === "assigned" || selectedWorkTicketStatus === "rework");
    const canPauseWork =
      selectedWorkTicketStatus !== null &&
      isSelectedFromTodo &&
      selectedWorkTicketStatus === "in_progress" &&
      selectedWorkSessionStatus === "running";
    const canResumeWork =
      selectedWorkTicketStatus !== null &&
      isSelectedFromTodo &&
      selectedWorkTicketStatus === "in_progress" &&
      selectedWorkSessionStatus === "paused";
    const canStopWork =
      selectedWorkTicketStatus !== null &&
      isSelectedFromTodo &&
      selectedWorkTicketStatus === "in_progress" &&
      (selectedWorkSessionStatus === "running" || selectedWorkSessionStatus === "paused");
    const canSelectCompletedParts =
      selectedWorkTicketStatus !== null &&
      isSelectedFromTodo &&
      selectedWorkTicketStatus === "in_progress" &&
      selectedWorkSessionStatus === "stopped";
    const canSubmitCompletion =
      canSelectCompletedParts &&
      selectedWorkCompletedPartIds.length > 0 &&
      !isRunningWorkAction &&
      permissions.can_work;

    return (
      <div className="space-y-3">
        <section className="rm-panel p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-900">{t("Technician queue")}</p>
            <Button
              type="button"
              variant="outline"
              className="h-9 px-3"
              onClick={() => void refreshWorkQueues()}
              disabled={isLoadingWorkQueues}
            >
              <RefreshCcw className="h-4 w-4" />
            </Button>
          </div>

          <div className="mt-2 flex items-center gap-2">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              className="rm-input h-10"
              value={workSearch}
              onChange={(event) => setWorkSearch(event.target.value)}
              placeholder={t("Search ticket id, serial, title")}
            />
          </div>

          <div className="mt-3 max-h-[33svh] space-y-2 overflow-y-auto pr-1">
            {isLoadingWorkQueues ? (
              <p className="text-sm text-slate-600">{t("Loading technician queue...")}</p>
            ) : visibleTickets.length ? (
              visibleTickets.map((ticket) => {
                const serial =
                  inventoryCache[ticket.inventory_item]?.serial_number ??
                  t("Item #{{id}}", { id: ticket.inventory_item });
                const pending = pendingPartsForTicket(ticket);
                const selected = selectedWorkTicketId === ticket.id;
                return (
                  <button
                    key={`${workQueueView}-${ticket.id}`}
                    type="button"
                    onClick={() => {
                      setSelectedWorkTicketId(ticket.id);
                      void ensureInventoryLoaded([ticket.inventory_item]);
                    }}
                    className={cn(
                      "w-full rounded-xl border px-3 py-3 text-left transition",
                      ticketCardClass(ticket.flag_color, selected),
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{t("Ticket #{{id}}", { id: ticket.id })}</p>
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                          selected
                            ? ticket.flag_color === "yellow"
                              ? "border-black/15 text-slate-800"
                              : "border-white/35 text-white"
                            : "border-slate-400/60 text-slate-700",
                        )}
                      >
                        {statusLabel(ticket.status)}
                      </span>
                    </div>
                    <p className={cn("mt-1 text-xs", ticketCardMetaClass(ticket.flag_color, selected))}>
                      {t("Serial")}: {serial}
                    </p>
                    <p className={cn("mt-1 text-xs", ticketCardMetaClass(ticket.flag_color, selected))}>
                      {t("Pending parts")}: {pending.length}
                    </p>
                    {renderPendingPartDetails(ticket, ticket.flag_color, selected)}
                  </button>
                );
              })
            ) : (
              <p className="rounded-lg border border-dashed border-slate-300 px-3 py-3 text-center text-sm text-slate-500">
                {workQueueView === "pool"
                  ? t("No active pool tickets.")
                  : t("No tickets in personal todo.")}
              </p>
            )}
          </div>
        </section>

        <section className="rm-panel p-4">
          {selectedWorkTicket ? (
            <div className="space-y-3">
              <div
                className={cn(
                  "rounded-xl border px-3 py-2",
                  ticketCardClass(selectedWorkTicket.flag_color, false),
                )}
              >
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900">
                    {t("Ticket #{{id}}", { id: selectedWorkTicket.id })}
                  </p>
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                      statusBadgeClass(selectedWorkTicket.status),
                    )}
                  >
                    {statusLabel(selectedWorkTicket.status)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-700">
                  {t("Serial")}:{" "}
                  {inventoryCache[selectedWorkTicket.inventory_item]?.serial_number ??
                    t("Item #{{id}}", { id: selectedWorkTicket.inventory_item })}
                </p>
                <p className="mt-1 text-xs text-slate-700">
                  {t("Priority")}: {colorLabel(selectedWorkTicket.flag_color)}
                </p>
                <p className="mt-1 text-xs text-slate-700">
                  {t("Pending parts")}: {pendingParts.length}
                </p>
                {renderPendingPartDetails(
                  selectedWorkTicket,
                  selectedWorkTicket.flag_color,
                  false,
                  { limit: 3, className: "text-slate-700" },
                )}
              </div>

              {isSelectedFromPool ? (
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                  <p className="text-xs text-slate-600">
                    {t("Claim this ticket to move it into your todo queue.")}
                  </p>
                  <Button
                    type="button"
                    className="mt-2 h-11 w-full"
                    onClick={() => void handleClaimWorkTicket(selectedWorkTicket.id)}
                    disabled={isRunningWorkAction || !permissions.can_work}
                  >
                    {t("Claim")}
                  </Button>
                </div>
              ) : null}

              {isSelectedFromTodo ? (
                <div className="space-y-3 rounded-xl border border-slate-200 bg-white px-3 py-3">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Timer className="h-4 w-4 text-slate-500" />
                        {t("Timer")}
                      </p>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                        {sessionStatusLabel(selectedWorkSessionStatus)}
                      </span>
                    </div>
                    <p className="mt-2 text-xl font-semibold tracking-tight text-slate-900">
                      {formatClock(workedSeconds)}
                    </p>
                    <p className="text-xs text-slate-600">
                      {t("Worked")}: {formatClock(workedSeconds)} · {t("Planned")}:{" "}
                      {formatClock(plannedSeconds)}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {t("Parts done")}: {completedParts}/{totalParts}
                    </p>
                    <div className="mt-2 h-1.5 rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-slate-900 transition-all"
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                    {isLoadingWorkSessionHistory ? (
                      <p className="mt-2 text-xs text-slate-500">{t("Loading work session...")}</p>
                    ) : null}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {canStartWork ? (
                      <Button
                        type="button"
                        className="h-11"
                        onClick={() => void handleWorkSessionAction(selectedWorkTicket.id, "start")}
                        disabled={isRunningWorkAction || !permissions.can_work}
                      >
                        <Play className="mr-1.5 h-4 w-4" />
                        {t("Start work")}
                      </Button>
                    ) : null}
                    {canPauseWork ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="h-11 border-amber-300 text-amber-700"
                        onClick={() => void handleWorkSessionAction(selectedWorkTicket.id, "pause")}
                        disabled={isRunningWorkAction || !permissions.can_work}
                      >
                        <Pause className="mr-1.5 h-4 w-4" />
                        {t("Pause")}
                      </Button>
                    ) : null}
                    {canResumeWork ? (
                      <Button
                        type="button"
                        className="h-11"
                        onClick={() => void handleWorkSessionAction(selectedWorkTicket.id, "resume")}
                        disabled={isRunningWorkAction || !permissions.can_work}
                      >
                        <CirclePlay className="mr-1.5 h-4 w-4" />
                        {t("Resume")}
                      </Button>
                    ) : null}
                    {canStopWork ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="h-11 border-rose-300 text-rose-700"
                        onClick={() => void handleWorkSessionAction(selectedWorkTicket.id, "stop")}
                        disabled={isRunningWorkAction || !permissions.can_work}
                      >
                        <Square className="mr-1.5 h-4 w-4" />
                        {t("Stop")}
                      </Button>
                    ) : null}
                  </div>

                  {!canSelectCompletedParts ? (
                    <p className="rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-600">
                      {t("Stop session to select completed parts.")}
                    </p>
                  ) : (
                    <>
                      <p className="text-sm font-semibold text-slate-900">{t("Parts completion")}</p>
                      {selectedWorkTicket.ticket_parts.length ? (
                        selectedWorkTicket.ticket_parts.map((part) => {
                          const isCompleted = Boolean(part.is_completed || part.completed_at);
                          const checked = selectedPartSet.has(part.id);
                          const completedBy =
                            part.completed_by_name ||
                            (typeof part.completed_by === "number"
                              ? t("User #{{id}}", { id: part.completed_by })
                              : t("Not completed"));

                          return (
                            <label
                              key={`work-part-${part.id}`}
                              className="block rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={(event) => {
                                      setSelectedWorkCompletedPartIds((prev) => {
                                        const next = new Set(prev);
                                        if (event.target.checked) {
                                          next.add(part.id);
                                        } else {
                                          next.delete(part.id);
                                        }
                                        return [...next];
                                      });
                                    }}
                                    disabled={
                                      isCompleted ||
                                      isRunningWorkAction ||
                                      !permissions.can_work ||
                                      !canSelectCompletedParts
                                    }
                                    className="h-5 w-5 accent-slate-900"
                                  />
                                  <p className="text-sm font-medium text-slate-900">{part.part_name}</p>
                                </div>
                                <span
                                  className={cn(
                                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                                    colorPillClass(part.color),
                                  )}
                                >
                                  {colorLabel(part.color)}
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-slate-600">{t("Minutes")}: {part.minutes}</p>
                              <p className="mt-1 text-xs text-slate-600">{t("Comment")}: {part.comment || "-"}</p>
                              <p className="mt-1 text-xs text-slate-600">{t("Completed by")}: {completedBy}</p>
                              <p className="mt-1 text-xs text-slate-600">
                                {t("Completed at")}: {formatDate(part.completed_at)}
                              </p>
                            </label>
                          );
                        })
                      ) : (
                        <p className="text-xs text-slate-500">{t("No part specs.")}</p>
                      )}

                      <Button
                        type="button"
                        className="h-11 w-full"
                        onClick={() => void handleSubmitWorkCompletion()}
                        disabled={!canSubmitCompletion}
                      >
                        <CheckCircle2 className="mr-1.5 h-4 w-4" />
                        {t("Submit completion")}
                      </Button>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
              {t("Select a work ticket to continue.")}
            </p>
          )}
        </section>
      </div>
    );
  };

  const renderQcTab = () => (
    <div className="space-y-3">
      <section className="rm-panel p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-900">{t("QC queue")}</p>
          <Button
            type="button"
            variant="outline"
            className="h-9 px-3"
            onClick={() => void refreshQcTickets()}
            disabled={isLoadingQcTickets}
          >
            <RefreshCcw className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            className="rm-input h-10"
            value={qcSearch}
            onChange={(event) => setQcSearch(event.target.value)}
            placeholder={t("Search ticket id, serial, title")}
          />
        </div>

        <div className="mt-3 max-h-[32svh] space-y-2 overflow-y-auto pr-1">
          {isLoadingQcTickets ? (
            <p className="text-sm text-slate-600">{t("Loading QC queue...")}</p>
          ) : qcTicketsFiltered.length ? (
            qcTicketsFiltered.map((ticket) => {
              const serial =
                inventoryCache[ticket.inventory_item]?.serial_number ??
                t("Item #{{id}}", { id: ticket.inventory_item });
              const pendingParts = pendingPartsForTicket(ticket);
              const selected = selectedQcTicketId === ticket.id;
              return (
                <button
                  key={ticket.id}
                  type="button"
                  onClick={() => {
                    setSelectedQcTicketId(ticket.id);
                    void ensureInventoryLoaded([ticket.inventory_item]);
                  }}
                  className={cn(
                    "w-full rounded-xl border px-3 py-3 text-left transition",
                    ticketCardClass(ticket.flag_color, selected),
                  )}
                >
                  <p className="text-sm font-semibold">
                    {t("Ticket #{{id}}", { id: ticket.id })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      ticketCardMetaClass(ticket.flag_color, selected),
                    )}
                  >
                    {t("Serial")}: {serial}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      ticketCardMetaClass(ticket.flag_color, selected),
                    )}
                  >
                    {t("Priority")}: {colorLabel(ticket.flag_color)}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      ticketCardMetaClass(ticket.flag_color, selected),
                    )}
                  >
                    {t("Pending parts")}: {pendingParts.length}
                  </p>
                  {renderPendingPartDetails(ticket, ticket.flag_color, selected)}
                </button>
              );
            })
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-center text-sm text-slate-500">
              {t("No tickets in QC queue.")}
            </p>
          )}
        </div>
      </section>

      <section className="rm-panel p-4">
        {selectedQcTicket ? (
          <div className="space-y-3">
            <div
              className={cn(
                "rounded-xl border px-3 py-2",
                ticketCardClass(selectedQcTicket.flag_color, false),
              )}
            >
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  {t("Ticket #{{id}}", { id: selectedQcTicket.id })}
                </p>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                    statusBadgeClass(selectedQcTicket.status),
                  )}
                >
                  {statusLabel(selectedQcTicket.status)}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-700">
                {t("Serial")}:{" "}
                {inventoryCache[selectedQcTicket.inventory_item]?.serial_number ??
                  t("Item #{{id}}", { id: selectedQcTicket.inventory_item })}
              </p>
              <p className="mt-1 text-xs text-slate-700">
                {t("Priority")}: {colorLabel(selectedQcTicket.flag_color)}
              </p>
              <p className="mt-1 text-xs text-slate-700">
                {t("Pending parts")}: {pendingPartsForTicket(selectedQcTicket).length}
              </p>
              {renderPendingPartDetails(
                selectedQcTicket,
                selectedQcTicket.flag_color,
                false,
                { limit: 3, className: "text-slate-700" },
              )}
            </div>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
              <p className="text-sm font-semibold text-slate-900">{t("Part specs")}</p>
              {selectedQcTicket.ticket_parts.length ? (
                selectedQcTicket.ticket_parts.map((part) => {
                  const checked = selectedQcFailedPartIds.includes(part.id);
                  const completedBy =
                    part.completed_by_name ||
                    (typeof part.completed_by === "number"
                      ? t("User #{{id}}", { id: part.completed_by })
                      : t("Not completed"));
                  return (
                    <label
                      key={part.id}
                      className="block rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => {
                              setSelectedQcFailedPartIds((prev) => {
                                const next = new Set(prev);
                                if (event.target.checked) {
                                  next.add(part.id);
                                } else {
                                  next.delete(part.id);
                                }
                                return [...next];
                              });
                            }}
                            disabled={
                              !permissions.can_qc ||
                              isRunningQcAction ||
                              selectedQcTicket.status !== "waiting_qc"
                            }
                            className="h-5 w-5 accent-slate-900"
                          />
                          <p className="text-sm font-medium text-slate-900">{part.part_name}</p>
                        </div>
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                            colorPillClass(part.color),
                          )}
                        >
                          {colorLabel(part.color)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Minutes")}: {part.minutes}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Comment")}: {part.comment || "-"}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Completed by")}: {completedBy}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Completed at")}: {formatDate(part.completed_at)}
                      </p>
                    </label>
                  );
                })
              ) : (
                <p className="text-xs text-slate-500">{t("No part specs.")}</p>
              )}
            </div>

            {permissions.can_qc ? (
              <div className="space-y-2">
                <textarea
                  className="rm-input min-h-[84px] resize-y py-2"
                  value={qcFailNote}
                  onChange={(event) => setQcFailNote(event.target.value)}
                  placeholder={t("QC fail comment (optional)")}
                  disabled={
                    isRunningQcAction || selectedQcTicket.status !== "waiting_qc"
                  }
                />
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    className="h-11"
                    onClick={() => void handleQcDecision("pass")}
                    disabled={
                      isRunningQcAction || selectedQcTicket.status !== "waiting_qc"
                    }
                  >
                    {t("QC Pass")}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 border-rose-300 text-rose-700"
                    onClick={() => void handleQcDecision("fail")}
                    disabled={
                      isRunningQcAction ||
                      selectedQcTicket.status !== "waiting_qc" ||
                      !selectedQcFailedPartIds.length
                    }
                  >
                    {t("QC Fail")}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {t("You do not have permission to run QC actions.")}
              </p>
            )}
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Select a QC ticket to continue.")}
          </p>
        )}
      </section>
    </div>
  );

  const hasWorkTab = availableTabs.includes("work");
  const nonWorkTabs = availableTabs.filter((tab) => tab !== "work");

  return (
    <section className="space-y-3 pb-24">
      <FeedbackToast feedback={feedback} />

      {!availableTabs.length ? (
        <section className="rm-panel p-4">
          <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 px-3 py-3">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-amber-800">
              <ShieldAlert className="h-4 w-4" />
              {t("No ticket permissions")}
            </p>
            <p className="mt-2 text-xs text-amber-700">
              {t("Your account does not have create/review/work/qc access.")}
            </p>
          </div>
        </section>
      ) : activeTab === "create" ? (
        renderCreateTab()
      ) : activeTab === "review" ? (
        renderReviewTab()
      ) : activeTab === "work" ? (
        renderWorkTab()
      ) : (
        renderQcTab()
      )}

      {availableTabs.length ? (
        <nav className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3">
          <div className="mx-auto flex max-w-md gap-2 rounded-2xl border border-white/80 bg-white/95 p-2 shadow-[0_16px_32px_-22px_rgba(15,23,42,0.55)] backdrop-blur">
            {hasWorkTab ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("work");
                    setWorkQueueView("pool");
                  }}
                  className={cn(
                    "flex-1 rounded-xl px-3 py-2.5 text-xs font-semibold transition",
                    activeTab === "work" && workQueueView === "pool"
                      ? "bg-slate-900 text-white"
                      : "border border-slate-200 bg-slate-50 text-slate-700",
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <ListTodo className="h-4 w-4" />
                    {t("Active pool")}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("work");
                    setWorkQueueView("todo");
                  }}
                  className={cn(
                    "flex-1 rounded-xl px-3 py-2.5 text-xs font-semibold transition",
                    activeTab === "work" && workQueueView === "todo"
                      ? "bg-slate-900 text-white"
                      : "border border-slate-200 bg-slate-50 text-slate-700",
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <ClipboardCheck className="h-4 w-4" />
                    {t("My todo")}
                  </span>
                </button>
              </>
            ) : null}

            {nonWorkTabs.map((tab) => {
              const Icon = TAB_META[tab].icon;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "flex-1 rounded-xl px-3 py-2.5 text-xs font-semibold transition",
                    activeTab === tab
                      ? "bg-slate-900 text-white"
                      : "border border-slate-200 bg-slate-50 text-slate-700",
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <Icon className="h-4 w-4" />
                    {t(TAB_META[tab].labelKey)}
                  </span>
                </button>
              );
            })}
          </div>
        </nav>
      ) : null}
    </section>
  );
}
