import {
  ArrowLeft,
  ClipboardCheck,
  FilePlus2,
  History,
  RefreshCcw,
  Search,
  Ticket,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { useI18n } from "@/i18n";
import {
  assignTicket,
  createTicket,
  getTicket,
  getInventoryItem,
  listAllCategories,
  listInventoryItemsPage,
  listParts,
  listTechnicianOptions,
  listTicketWorkSessionHistory,
  listTicketTransitions,
  listTickets,
  listTicketsPage,
  moveTicketToWaitingQc,
  pauseTicketWorkSession,
  qcFailTicket,
  qcPassTicket,
  reviewApproveTicket,
  reviewTicketManualMetrics,
  resumeTicketWorkSession,
  startTicketWork,
  stopTicketWorkSession,
  type InventoryCategory,
  type InventoryItem,
  type InventoryItemStatus,
  type InventoryPart,
  type PaginationMeta,
  type TechnicianOption,
  type Ticket as TicketModel,
  type TicketColor,
  type TicketStatus,
  type TicketTransition,
  type WorkSessionTransition,
  type WorkSessionStatus,
} from "@/lib/api";
import {
  buildInventorySerialSearchQuery,
  normalizeInventorySerialSearchQuery,
} from "@/lib/inventory-search";
import { cn } from "@/lib/utils";

type TicketFlowProps = {
  accessToken: string;
  currentUserId: number | null;
  canCreate: boolean;
  canReview: boolean;
  canWork: boolean;
  canQc: boolean;
  roleSlugs: string[];
  routeBase?: string;
  showWorkTab?: boolean;
  restrictTabsByPermission?: boolean;
  syncRouteWithUrl?: boolean;
};

type FeedbackState =
  | {
      type: "success" | "error" | "info";
      message: string;
    }
  | null;

type TicketRoute =
  | { name: "createList" }
  | { name: "createItem"; itemId: number }
  | { name: "historyTicket"; ticketId: number }
  | { name: "review" }
  | { name: "work" }
  | { name: "qc" };

type TicketFlowMenu = "create" | "review" | "work" | "qc";

type ItemFilterState = {
  search: string;
  categoryId: string;
  status: "all" | InventoryItemStatus;
  activity: "all" | "active" | "inactive";
};

type PartSpecFormState = {
  selected: boolean;
  color: TicketColor;
  minutes: string;
  comment: string;
};

type AuditTimelineEvent = {
  key: string;
  source: "workflow" | "work_session";
  action: string;
  fromStatus: string | null;
  toStatus: string;
  actorLabel: string;
  note: string | null;
  at: string;
  metadata: Record<string, unknown>;
};

const DEFAULT_ITEM_FILTERS: ItemFilterState = {
  search: "",
  categoryId: "",
  status: "all",
  activity: "all",
};

const ITEM_STATUS_OPTIONS: InventoryItemStatus[] = [
  "ready",
  "in_service",
  "rented",
  "blocked",
  "write_off",
];

const TICKET_STATUS_OPTIONS: TicketStatus[] = [
  "under_review",
  "new",
  "assigned",
  "in_progress",
  "waiting_qc",
  "rework",
  "done",
];

const TICKET_COLOR_OPTIONS: TicketColor[] = ["green", "yellow", "red"];
const LIST_PER_PAGE_OPTIONS = [10, 20, 50];
const DEFAULT_LIST_PER_PAGE = 20;

const fieldClassName =
  "rm-input";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatTokenLabel(value: string | null): string {
  if (!value) {
    return "-";
  }
  return value
    .split("_")
    .filter(Boolean)
    .map((token) => token[0].toUpperCase() + token.slice(1))
    .join(" ");
}

function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function normalizeTicketRouteBase(routeBase: string): string {
  const compact = routeBase.trim();
  if (!compact) {
    return "/tickets";
  }
  const withLeadingSlash = compact.startsWith("/") ? compact : `/${compact}`;
  const withoutTrailingSlash = withLeadingSlash.replace(/\/+$/, "");
  return withoutTrailingSlash || "/tickets";
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function routeMenu(route: TicketRoute): TicketFlowMenu {
  if (route.name === "review") {
    return "review";
  }
  if (route.name === "work") {
    return "work";
  }
  if (route.name === "qc") {
    return "qc";
  }
  return "create";
}

function routeForMenu(menu: TicketFlowMenu): TicketRoute {
  if (menu === "review") {
    return { name: "review" };
  }
  if (menu === "work") {
    return { name: "work" };
  }
  if (menu === "qc") {
    return { name: "qc" };
  }
  return { name: "createList" };
}

function parseTicketRoute(pathname: string, routeBase = "/tickets"): TicketRoute {
  const normalizedBase = normalizeTicketRouteBase(routeBase);
  const escapedBase = escapeRegExp(normalizedBase);
  const createItemMatch = pathname.match(
    new RegExp(`^${escapedBase}/create/item/(\\d+)/?$`),
  );
  if (createItemMatch) {
    const parsedId = Number(createItemMatch[1]);
    if (Number.isFinite(parsedId) && parsedId > 0) {
      return { name: "createItem", itemId: parsedId };
    }
  }

  const historyTicketMatch = pathname.match(
    new RegExp(`^${escapedBase}/history/(\\d+)/?$`),
  );
  if (historyTicketMatch) {
    const parsedId = Number(historyTicketMatch[1]);
    if (Number.isFinite(parsedId) && parsedId > 0) {
      return { name: "historyTicket", ticketId: parsedId };
    }
  }

  if (pathname.startsWith(`${normalizedBase}/review`)) {
    return { name: "review" };
  }
  if (pathname.startsWith(`${normalizedBase}/work`)) {
    return { name: "work" };
  }
  if (pathname.startsWith(`${normalizedBase}/qc`)) {
    return { name: "qc" };
  }

  if (pathname.startsWith(`${normalizedBase}/create`)) {
    return { name: "createList" };
  }

  return { name: "createList" };
}

function toTicketPath(route: TicketRoute, routeBase = "/tickets"): string {
  const normalizedBase = normalizeTicketRouteBase(routeBase);
  if (route.name === "review") {
    return `${normalizedBase}/review`;
  }
  if (route.name === "work") {
    return `${normalizedBase}/work`;
  }
  if (route.name === "qc") {
    return `${normalizedBase}/qc`;
  }
  if (route.name === "createItem") {
    return `${normalizedBase}/create/item/${route.itemId}`;
  }
  if (route.name === "historyTicket") {
    return `${normalizedBase}/history/${route.ticketId}`;
  }
  return `${normalizedBase}/create`;
}

function areItemFiltersEqual(left: ItemFilterState, right: ItemFilterState): boolean {
  return (
    left.search === right.search &&
    left.categoryId === right.categoryId &&
    left.status === right.status &&
    left.activity === right.activity
  );
}

function inventoryStatusBadgeClass(status: InventoryItemStatus): string {
  if (status === "ready") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status === "in_service") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (status === "rented") {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  if (status === "blocked") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function ticketStatusBadgeClass(status: TicketStatus): string {
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

function ticketColorBadgeClass(color: TicketColor): string {
  if (color === "green") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (color === "yellow") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function inventoryStatusLabel(
  status: InventoryItemStatus,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (status === "ready") {
    return t("Ready");
  }
  if (status === "in_service") {
    return t("In Service");
  }
  if (status === "rented") {
    return t("Rented");
  }
  if (status === "blocked") {
    return t("Blocked");
  }
  return t("Write Off");
}

function ticketStatusLabel(
  status: TicketStatus,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (status === "under_review") {
    return t("Under review");
  }
  if (status === "new") {
    return t("New");
  }
  if (status === "assigned") {
    return t("Assigned");
  }
  if (status === "in_progress") {
    return t("In progress");
  }
  if (status === "waiting_qc") {
    return t("Waiting QC");
  }
  if (status === "rework") {
    return t("Rework");
  }
  return t("Done");
}

function ticketColorLabel(
  color: TicketColor,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (color === "green") {
    return t("Green");
  }
  if (color === "yellow") {
    return t("Yellow");
  }
  return t("Red");
}

export function TicketFlow({
  accessToken,
  currentUserId,
  canCreate,
  canReview,
  canWork,
  canQc,
  roleSlugs,
  routeBase = "/tickets",
  showWorkTab = true,
  restrictTabsByPermission = false,
  syncRouteWithUrl = true,
}: TicketFlowProps) {
  const { t } = useI18n();
  const [route, setRoute] = useState<TicketRoute>(() =>
    syncRouteWithUrl
      ? parseTicketRoute(window.location.pathname, routeBase)
      : { name: "createList" },
  );

  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [isMutating, setIsMutating] = useState(false);

  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);

  const [itemFilters, setItemFilters] = useState<ItemFilterState>(DEFAULT_ITEM_FILTERS);
  const [appliedItemFilters, setAppliedItemFilters] =
    useState<ItemFilterState>(DEFAULT_ITEM_FILTERS);
  const [createItems, setCreateItems] = useState<InventoryItem[]>([]);
  const [createItemsPage, setCreateItemsPage] = useState(1);
  const [createItemsPerPage, setCreateItemsPerPage] = useState(DEFAULT_LIST_PER_PAGE);
  const [createItemsPagination, setCreateItemsPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_LIST_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [isLoadingCreateItems, setIsLoadingCreateItems] = useState(false);

  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null);
  const [selectedItemParts, setSelectedItemParts] = useState<InventoryPart[]>([]);
  const [selectedItemTicketHistory, setSelectedItemTicketHistory] = useState<
    TicketModel[]
  >([]);
  const [ticketTitle, setTicketTitle] = useState("");
  const [partSpecForms, setPartSpecForms] = useState<
    Record<number, PartSpecFormState>
  >({});
  const [isLoadingCreateItemPage, setIsLoadingCreateItemPage] = useState(false);
  const [historyTicket, setHistoryTicket] = useState<TicketModel | null>(null);
  const [historyItem, setHistoryItem] = useState<InventoryItem | null>(null);
  const [historyTransitions, setHistoryTransitions] = useState<TicketTransition[]>([]);
  const [historyWorkSessionHistory, setHistoryWorkSessionHistory] = useState<
    WorkSessionTransition[]
  >([]);
  const [isLoadingHistoryTicket, setIsLoadingHistoryTicket] = useState(false);

  const [reviewTickets, setReviewTickets] = useState<TicketModel[]>([]);
  const [reviewPage, setReviewPage] = useState(1);
  const [reviewPerPage, setReviewPerPage] = useState(DEFAULT_LIST_PER_PAGE);
  const [reviewPagination, setReviewPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_LIST_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [isLoadingReviewTickets, setIsLoadingReviewTickets] = useState(false);
  const [reviewStatusFilter, setReviewStatusFilter] = useState<"all" | TicketStatus>(
    "under_review",
  );
  const [reviewSearch, setReviewSearch] = useState("");
  const [selectedReviewTicketId, setSelectedReviewTicketId] = useState<number | null>(
    null,
  );
  const [reviewTransitions, setReviewTransitions] = useState<TicketTransition[]>([]);
  const [isLoadingReviewTransitions, setIsLoadingReviewTransitions] = useState(false);
  const [reviewItem, setReviewItem] = useState<InventoryItem | null>(null);
  const [technicianOptions, setTechnicianOptions] = useState<TechnicianOption[]>([]);
  const [isLoadingTechnicians, setIsLoadingTechnicians] = useState(false);
  const [selectedTechnicianId, setSelectedTechnicianId] = useState("");
  const [reviewFlagColor, setReviewFlagColor] = useState<TicketColor>("green");
  const [reviewXpAmount, setReviewXpAmount] = useState("");

  const [workTickets, setWorkTickets] = useState<TicketModel[]>([]);
  const [workPage, setWorkPage] = useState(1);
  const [workPerPage, setWorkPerPage] = useState(DEFAULT_LIST_PER_PAGE);
  const [workPagination, setWorkPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_LIST_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [isLoadingWorkTickets, setIsLoadingWorkTickets] = useState(false);
  const [workStatusFilter, setWorkStatusFilter] = useState<
    "all" | "assigned" | "in_progress" | "rework" | "waiting_qc"
  >("all");
  const [workSearch, setWorkSearch] = useState("");
  const [selectedWorkTicketId, setSelectedWorkTicketId] = useState<number | null>(null);
  const [workTransitions, setWorkTransitions] = useState<TicketTransition[]>([]);
  const [isLoadingWorkTransitions, setIsLoadingWorkTransitions] = useState(false);
  const [workSessionHistory, setWorkSessionHistory] = useState<WorkSessionTransition[]>(
    [],
  );
  const [isLoadingWorkSessionHistory, setIsLoadingWorkSessionHistory] = useState(false);
  const [workItem, setWorkItem] = useState<InventoryItem | null>(null);

  const [qcTickets, setQcTickets] = useState<TicketModel[]>([]);
  const [qcPage, setQcPage] = useState(1);
  const [qcPerPage, setQcPerPage] = useState(DEFAULT_LIST_PER_PAGE);
  const [qcPagination, setQcPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_LIST_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [isLoadingQcTickets, setIsLoadingQcTickets] = useState(false);
  const [qcStatusFilter, setQcStatusFilter] = useState<"waiting_qc" | "all">(
    "waiting_qc",
  );
  const [qcSearch, setQcSearch] = useState("");
  const [selectedQcTicketId, setSelectedQcTicketId] = useState<number | null>(null);
  const [qcTransitions, setQcTransitions] = useState<TicketTransition[]>([]);
  const [isLoadingQcTransitions, setIsLoadingQcTransitions] = useState(false);
  const [qcItem, setQcItem] = useState<InventoryItem | null>(null);

  const [inventoryCache, setInventoryCache] = useState<Record<number, InventoryItem>>(
    {},
  );

  const activeMenu = routeMenu(route);

  const canAccessCreateMenu = restrictTabsByPermission ? canCreate : true;
  const canAccessReviewMenu = restrictTabsByPermission ? canReview : true;
  const canAccessWorkMenu =
    showWorkTab && (restrictTabsByPermission ? canWork : true);
  const canAccessQcMenu = restrictTabsByPermission ? canQc : true;
  const visibleMenus = useMemo<TicketFlowMenu[]>(() => {
    const next: TicketFlowMenu[] = [];
    if (canAccessCreateMenu) {
      next.push("create");
    }
    if (canAccessReviewMenu) {
      next.push("review");
    }
    if (canAccessWorkMenu) {
      next.push("work");
    }
    if (canAccessQcMenu) {
      next.push("qc");
    }
    return next;
  }, [
    canAccessCreateMenu,
    canAccessQcMenu,
    canAccessReviewMenu,
    canAccessWorkMenu,
  ]);

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const inventoryStatusLabelByValue = useMemo(
    () => new Map(ITEM_STATUS_OPTIONS.map((option) => [option, inventoryStatusLabel(option, t)])),
    [t],
  );

  const ticketStatusLabelByValue = useMemo(
    () => new Map(TICKET_STATUS_OPTIONS.map((option) => [option, ticketStatusLabel(option, t)])),
    [t],
  );

  const ticketColorLabelByValue = useMemo(
    () => new Map(TICKET_COLOR_OPTIONS.map((option) => [option, ticketColorLabel(option, t)])),
    [t],
  );

  const technicianLabelById = useMemo(
    () =>
      new Map(
        technicianOptions.map((technician) => [
          technician.user_id,
          technician.name === technician.username
            ? technician.username
            : `${technician.name} (@${technician.username})`,
        ]),
      ),
    [technicianOptions],
  );

  const historyUserLabelById = useMemo(() => {
    const map = new Map<number, string>();
    technicianLabelById.forEach((value, key) => {
      map.set(key, value);
    });

    if (historyTicket?.master) {
      map.set(
        historyTicket.master,
        historyTicket.master_name?.trim() ||
          map.get(historyTicket.master) ||
          t("User #{{id}}", { id: historyTicket.master }),
      );
    }
    if (historyTicket?.technician) {
      map.set(
        historyTicket.technician,
        historyTicket.technician_name?.trim() ||
          map.get(historyTicket.technician) ||
          t("User #{{id}}", { id: historyTicket.technician }),
      );
    }
    if (historyTicket?.approved_by) {
      map.set(
        historyTicket.approved_by,
        historyTicket.approved_by_name?.trim() ||
          map.get(historyTicket.approved_by) ||
          t("User #{{id}}", { id: historyTicket.approved_by }),
      );
    }
    return map;
  }, [historyTicket, t, technicianLabelById]);

  const resolveHistoryActorLabel = useCallback(
    (
      actorId: number | null,
      actorName?: string | null,
      actorUsername?: string | null,
    ): string => {
      const normalizedName = actorName?.trim();
      if (normalizedName) {
        return normalizedName;
      }

      const normalizedUsername = actorUsername?.trim();
      if (normalizedUsername) {
        return `@${normalizedUsername}`;
      }

      if (actorId !== null) {
        return historyUserLabelById.get(actorId) ?? t("User #{{id}}", { id: actorId });
      }

      return t("System");
    },
    [historyUserLabelById, t],
  );

  const historyTimeline = useMemo<AuditTimelineEvent[]>(() => {
    const workflowEvents: AuditTimelineEvent[] = historyTransitions.map((transition) => ({
      key: `wf-${transition.id}`,
      source: "workflow",
      action: transition.action,
      fromStatus: transition.from_status,
      toStatus: transition.to_status,
      actorLabel: resolveHistoryActorLabel(
        transition.actor,
        transition.actor_name,
        transition.actor_username,
      ),
      note: transition.note,
      at: transition.created_at,
      metadata: transition.metadata ?? {},
    }));

    const workSessionEvents: AuditTimelineEvent[] = historyWorkSessionHistory.map(
      (event) => ({
        key: `ws-${event.id}`,
        source: "work_session",
        action: event.action,
        fromStatus: event.from_status,
        toStatus: event.to_status,
        actorLabel: resolveHistoryActorLabel(
          event.actor,
          event.actor_name,
          event.actor_username,
        ),
        note: null,
        at: event.event_at,
        metadata: event.metadata ?? {},
      }),
    );

    return [...workflowEvents, ...workSessionEvents].sort((left, right) => {
      const leftTsRaw = new Date(left.at).valueOf();
      const rightTsRaw = new Date(right.at).valueOf();
      const leftTs = Number.isFinite(leftTsRaw) ? leftTsRaw : 0;
      const rightTs = Number.isFinite(rightTsRaw) ? rightTsRaw : 0;
      return rightTs - leftTs;
    });
  }, [
    historyTransitions,
    historyWorkSessionHistory,
    resolveHistoryActorLabel,
  ]);

  const hasPendingItemFilterChanges = useMemo(
    () => !areItemFiltersEqual(itemFilters, appliedItemFilters),
    [itemFilters, appliedItemFilters],
  );

  const selectedPartsCount = useMemo(
    () =>
      selectedItemParts.filter((part) => {
        const row = partSpecForms[part.id];
        return Boolean(row?.selected);
      }).length,
    [selectedItemParts, partSpecForms],
  );

  const selectedReviewTicket = useMemo(
    () => reviewTickets.find((ticket) => ticket.id === selectedReviewTicketId) ?? null,
    [reviewTickets, selectedReviewTicketId],
  );

  const isSuperAdmin = useMemo(
    () => roleSlugs.includes("super_admin"),
    [roleSlugs],
  );

  const workVisibleTickets = useMemo(() => {
    const allowedStatuses = new Set<TicketStatus>([
      "assigned",
      "in_progress",
      "rework",
      "waiting_qc",
    ]);

    return workTickets.filter((ticket) => {
      if (!allowedStatuses.has(ticket.status)) {
        return false;
      }
      if (!isSuperAdmin) {
        if (currentUserId === null) {
          return false;
        }
        if (ticket.technician !== currentUserId) {
          return false;
        }
      }
      return true;
    });
  }, [
    currentUserId,
    isSuperAdmin,
    workTickets,
  ]);

  const selectedWorkTicket = useMemo(
    () => workVisibleTickets.find((ticket) => ticket.id === selectedWorkTicketId) ?? null,
    [selectedWorkTicketId, workVisibleTickets],
  );

  const currentWorkSessionStatus = useMemo<WorkSessionStatus | null>(() => {
    if (!workSessionHistory.length) {
      return null;
    }
    return workSessionHistory[0].to_status;
  }, [workSessionHistory]);

  const selectedQcTicket = useMemo(
    () => qcTickets.find((ticket) => ticket.id === selectedQcTicketId) ?? null,
    [qcTickets, selectedQcTicketId],
  );

  const navigate = useCallback((nextRoute: TicketRoute) => {
    if (syncRouteWithUrl) {
      const nextPath = toTicketPath(nextRoute, routeBase);
      if (window.location.pathname !== nextPath) {
        window.history.pushState({}, "", nextPath);
      }
    }
    setRoute(nextRoute);
    setFeedback(null);
  }, [routeBase, syncRouteWithUrl]);

  const cacheInventoryItems = useCallback((nextItems: InventoryItem[]) => {
    if (!nextItems.length) {
      return;
    }

    setInventoryCache((prev) => {
      const merged = { ...prev };
      nextItems.forEach((item) => {
        merged[item.id] = item;
      });
      return merged;
    });
  }, []);

  const runMutation = useCallback(
    async (task: () => Promise<void>, successMessage: string) => {
      setIsMutating(true);
      setFeedback(null);
      try {
        await task();
        setFeedback({ type: "success", message: successMessage });
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Action failed.")),
        });
        throw error;
      } finally {
        setIsMutating(false);
      }
    },
    [t],
  );

  const loadCategories = useCallback(async () => {
    setIsLoadingCategories(true);
    try {
      const nextCategories = await listAllCategories(accessToken);
      setCategories(nextCategories);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load categories.")),
      });
    } finally {
      setIsLoadingCategories(false);
    }
  }, [accessToken, t]);

  const loadCreateItems = useCallback(
    async (filters: ItemFilterState, page: number, perPage: number) => {
      setIsLoadingCreateItems(true);
      try {
        const searchQuery = buildInventorySerialSearchQuery(filters.search);
        const paginated = await listInventoryItemsPage(accessToken, {
          page,
          per_page: perPage,
          q: searchQuery,
          category: filters.categoryId ? Number(filters.categoryId) : undefined,
          status: filters.status === "all" ? undefined : filters.status,
          is_active:
            filters.activity === "all"
              ? undefined
              : filters.activity === "active",
        });

        if (page > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
          setCreateItemsPage(paginated.pagination.page_count);
          return;
        }

        setCreateItems(paginated.results);
        setCreateItemsPagination(paginated.pagination);
        cacheInventoryItems(paginated.results);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load inventory items.")),
        });
      } finally {
        setIsLoadingCreateItems(false);
      }
    },
    [accessToken, cacheInventoryItems, t],
  );

  const loadCreateItemPage = useCallback(
    async (itemId: number) => {
      setIsLoadingCreateItemPage(true);
      try {
        const [item, allParts, tickets] = await Promise.all([
          getInventoryItem(accessToken, itemId),
          listParts(accessToken),
          listTickets(accessToken, { per_page: 400 }),
        ]);

        const itemParts = allParts.filter((part) => part.category === item.category);
        const itemTickets = tickets
          .filter((ticket) => ticket.inventory_item === item.id)
          .sort((left, right) => {
            const leftTime = new Date(left.created_at).valueOf();
            const rightTime = new Date(right.created_at).valueOf();
            return rightTime - leftTime;
          });

        const initialPartForms: Record<number, PartSpecFormState> = {};
        itemParts.forEach((part) => {
          initialPartForms[part.id] = {
            selected: false,
            color: "green",
            minutes: "",
            comment: "",
          };
        });

        setSelectedItem(item);
        setSelectedItemParts(itemParts);
        setSelectedItemTicketHistory(itemTickets);
        setPartSpecForms(initialPartForms);
        setTicketTitle("");
        cacheInventoryItems([item]);
      } catch (error) {
        setSelectedItem(null);
        setSelectedItemParts([]);
        setSelectedItemTicketHistory([]);
        setPartSpecForms({});
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load ticket creation context.")),
        });
      } finally {
        setIsLoadingCreateItemPage(false);
      }
    },
    [accessToken, cacheInventoryItems, t],
  );

  const loadHistoryTicketPage = useCallback(
    async (ticketId: number) => {
      setIsLoadingHistoryTicket(true);
      try {
        const [ticket, transitions, workHistory] = await Promise.all([
          getTicket(accessToken, ticketId),
          listTicketTransitions(accessToken, ticketId, { per_page: 300 }),
          listTicketWorkSessionHistory(accessToken, ticketId, { per_page: 300 }),
        ]);

        setHistoryTicket(ticket);
        setHistoryTransitions(transitions);
        setHistoryWorkSessionHistory(workHistory);

        const cachedItem = inventoryCache[ticket.inventory_item];
        if (cachedItem) {
          setHistoryItem(cachedItem);
        } else {
          try {
            const item = await getInventoryItem(accessToken, ticket.inventory_item);
            setHistoryItem(item);
            cacheInventoryItems([item]);
          } catch {
            setHistoryItem(null);
          }
        }
      } catch (error) {
        setHistoryTicket(null);
        setHistoryItem(null);
        setHistoryTransitions([]);
        setHistoryWorkSessionHistory([]);
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load ticket full details.")),
        });
      } finally {
        setIsLoadingHistoryTicket(false);
      }
    },
    [accessToken, cacheInventoryItems, inventoryCache, t],
  );

  const loadReviewTickets = useCallback(async () => {
    setIsLoadingReviewTickets(true);
    try {
      const search = reviewSearch.trim();
      const paginated = await listTicketsPage(accessToken, {
        page: reviewPage,
        per_page: reviewPerPage,
        q: search.length >= 2 ? search : undefined,
        status: reviewStatusFilter === "all" ? undefined : reviewStatusFilter,
      });
      if (reviewPage > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
        setReviewPage(paginated.pagination.page_count);
        return;
      }
      setReviewTickets(paginated.results);
      setReviewPagination(paginated.pagination);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load tickets for review.")),
      });
    } finally {
      setIsLoadingReviewTickets(false);
    }
  }, [accessToken, reviewPage, reviewPerPage, reviewSearch, reviewStatusFilter, t]);

  const loadWorkTickets = useCallback(async () => {
    setIsLoadingWorkTickets(true);
    try {
      const search = workSearch.trim();
      const paginated = await listTicketsPage(accessToken, {
        page: workPage,
        per_page: workPerPage,
        q: search.length >= 2 ? search : undefined,
        status: workStatusFilter === "all" ? undefined : workStatusFilter,
      });
      if (workPage > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
        setWorkPage(paginated.pagination.page_count);
        return;
      }
      setWorkTickets(paginated.results);
      setWorkPagination(paginated.pagination);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load technician tickets.")),
      });
    } finally {
      setIsLoadingWorkTickets(false);
    }
  }, [accessToken, t, workPage, workPerPage, workSearch, workStatusFilter]);

  const loadQcTickets = useCallback(async () => {
    setIsLoadingQcTickets(true);
    try {
      const search = qcSearch.trim();
      const paginated = await listTicketsPage(accessToken, {
        page: qcPage,
        per_page: qcPerPage,
        q: search.length >= 2 ? search : undefined,
        status: qcStatusFilter === "all" ? undefined : qcStatusFilter,
      });
      if (qcPage > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
        setQcPage(paginated.pagination.page_count);
        return;
      }
      setQcTickets(paginated.results);
      setQcPagination(paginated.pagination);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load QC tickets.")),
      });
    } finally {
      setIsLoadingQcTickets(false);
    }
  }, [accessToken, qcPage, qcPerPage, qcSearch, qcStatusFilter, t]);

  const loadTechnicians = useCallback(async () => {
    if (!canReview) {
      setTechnicianOptions([]);
      setIsLoadingTechnicians(false);
      return;
    }

    setIsLoadingTechnicians(true);
    try {
      const nextTechnicians = await listTechnicianOptions(accessToken);
      setTechnicianOptions(nextTechnicians);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load technicians.")),
      });
    } finally {
      setIsLoadingTechnicians(false);
    }
  }, [accessToken, canReview, t]);

  const loadReviewTransitions = useCallback(
    async (ticketId: number) => {
      setIsLoadingReviewTransitions(true);
      try {
        const nextTransitions = await listTicketTransitions(accessToken, ticketId, {
          per_page: 100,
        });
        setReviewTransitions(nextTransitions);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load ticket transitions.")),
        });
      } finally {
        setIsLoadingReviewTransitions(false);
      }
    },
    [accessToken, t],
  );

  const loadWorkTransitions = useCallback(
    async (ticketId: number) => {
      setIsLoadingWorkTransitions(true);
      try {
        const nextTransitions = await listTicketTransitions(accessToken, ticketId, {
          per_page: 100,
        });
        setWorkTransitions(nextTransitions);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load ticket transitions.")),
        });
      } finally {
        setIsLoadingWorkTransitions(false);
      }
    },
    [accessToken, t],
  );

  const loadQcTransitions = useCallback(
    async (ticketId: number) => {
      setIsLoadingQcTransitions(true);
      try {
        const nextTransitions = await listTicketTransitions(accessToken, ticketId, {
          per_page: 100,
        });
        setQcTransitions(nextTransitions);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load ticket transitions.")),
        });
      } finally {
        setIsLoadingQcTransitions(false);
      }
    },
    [accessToken, t],
  );

  const loadWorkSessionHistory = useCallback(
    async (ticketId: number) => {
      setIsLoadingWorkSessionHistory(true);
      try {
        const history = await listTicketWorkSessionHistory(accessToken, ticketId, {
          per_page: 100,
        });
        setWorkSessionHistory(history);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load work session history.")),
        });
      } finally {
        setIsLoadingWorkSessionHistory(false);
      }
    },
    [accessToken, t],
  );

  const loadReviewItem = useCallback(
    async (itemId: number) => {
      const cached = inventoryCache[itemId];
      if (cached) {
        setReviewItem(cached);
        return;
      }

      try {
        const item = await getInventoryItem(accessToken, itemId);
        setReviewItem(item);
        cacheInventoryItems([item]);
      } catch {
        setReviewItem(null);
      }
    },
    [accessToken, cacheInventoryItems, inventoryCache],
  );

  const loadWorkItem = useCallback(
    async (itemId: number) => {
      const cached = inventoryCache[itemId];
      if (cached) {
        setWorkItem(cached);
        return;
      }
      try {
        const item = await getInventoryItem(accessToken, itemId);
        setWorkItem(item);
        cacheInventoryItems([item]);
      } catch {
        setWorkItem(null);
      }
    },
    [accessToken, cacheInventoryItems, inventoryCache],
  );

  const loadQcItem = useCallback(
    async (itemId: number) => {
      const cached = inventoryCache[itemId];
      if (cached) {
        setQcItem(cached);
        return;
      }
      try {
        const item = await getInventoryItem(accessToken, itemId);
        setQcItem(item);
        cacheInventoryItems([item]);
      } catch {
        setQcItem(null);
      }
    },
    [accessToken, cacheInventoryItems, inventoryCache],
  );

  useEffect(() => {
    if (!syncRouteWithUrl) {
      return;
    }
    const onPopState = () => {
      setRoute(parseTicketRoute(window.location.pathname, routeBase));
      setFeedback(null);
    };

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, [routeBase, syncRouteWithUrl]);

  useEffect(() => {
    if (!visibleMenus.length) {
      return;
    }
    const active = routeMenu(route);
    if (visibleMenus.includes(active)) {
      return;
    }

    const fallbackRoute = routeForMenu(visibleMenus[0]);
    if (syncRouteWithUrl) {
      const fallbackPath = toTicketPath(fallbackRoute, routeBase);
      if (window.location.pathname !== fallbackPath) {
        window.history.replaceState({}, "", fallbackPath);
      }
    }
    setRoute(fallbackRoute);
    setFeedback(null);
  }, [route, routeBase, syncRouteWithUrl, visibleMenus]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    setReviewPage(1);
  }, [reviewSearch, reviewStatusFilter]);

  useEffect(() => {
    setWorkPage(1);
  }, [workSearch, workStatusFilter]);

  useEffect(() => {
    setQcPage(1);
  }, [qcSearch, qcStatusFilter]);

  useEffect(() => {
    if (itemFilters.search === appliedItemFilters.search) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setCreateItemsPage(1);
      setAppliedItemFilters((prev) => ({
        ...prev,
        search: itemFilters.search,
      }));
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [appliedItemFilters.search, itemFilters.search]);

  useEffect(() => {
    if (route.name !== "createList") {
      return;
    }
    void loadCreateItems(appliedItemFilters, createItemsPage, createItemsPerPage);
  }, [appliedItemFilters, createItemsPage, createItemsPerPage, loadCreateItems, route]);

  useEffect(() => {
    if (route.name !== "createItem") {
      setSelectedItem(null);
      setSelectedItemParts([]);
      setSelectedItemTicketHistory([]);
      setPartSpecForms({});
      setTicketTitle("");
      return;
    }

    void loadCreateItemPage(route.itemId);
  }, [loadCreateItemPage, route]);

  useEffect(() => {
    if (route.name !== "historyTicket") {
      setHistoryTicket(null);
      setHistoryItem(null);
      setHistoryTransitions([]);
      setHistoryWorkSessionHistory([]);
      return;
    }

    void loadHistoryTicketPage(route.ticketId);
  }, [loadHistoryTicketPage, route]);

  useEffect(() => {
    if (route.name !== "review") {
      setReviewTransitions([]);
      setReviewItem(null);
      setSelectedTechnicianId("");
      return;
    }

    void loadReviewTickets();
    void loadTechnicians();
  }, [loadReviewTickets, loadTechnicians, route]);

  useEffect(() => {
    if (route.name !== "review") {
      return;
    }

    if (!reviewTickets.length) {
      setSelectedReviewTicketId(null);
      return;
    }

    if (
      selectedReviewTicketId === null ||
      !reviewTickets.some((ticket) => ticket.id === selectedReviewTicketId)
    ) {
      setSelectedReviewTicketId(reviewTickets[0].id);
    }
  }, [reviewTickets, route, selectedReviewTicketId]);

  useEffect(() => {
    if (!selectedReviewTicket) {
      setReviewTransitions([]);
      setReviewItem(null);
      setSelectedTechnicianId("");
      return;
    }

    setReviewFlagColor(selectedReviewTicket.flag_color);
    setReviewXpAmount(String(selectedReviewTicket.xp_amount));
    setSelectedTechnicianId(
      selectedReviewTicket.technician ? String(selectedReviewTicket.technician) : "",
    );

    void loadReviewTransitions(selectedReviewTicket.id);
    void loadReviewItem(selectedReviewTicket.inventory_item);
  }, [loadReviewItem, loadReviewTransitions, selectedReviewTicket]);

  useEffect(() => {
    if (route.name !== "work") {
      setWorkTransitions([]);
      setWorkSessionHistory([]);
      setWorkItem(null);
      return;
    }
    void loadWorkTickets();
  }, [loadWorkTickets, route]);

  useEffect(() => {
    if (route.name !== "work") {
      return;
    }
    if (!workVisibleTickets.length) {
      setSelectedWorkTicketId(null);
      return;
    }
    if (
      selectedWorkTicketId === null ||
      !workVisibleTickets.some((ticket) => ticket.id === selectedWorkTicketId)
    ) {
      setSelectedWorkTicketId(workVisibleTickets[0].id);
    }
  }, [route, selectedWorkTicketId, workVisibleTickets]);

  useEffect(() => {
    if (!selectedWorkTicket) {
      setWorkTransitions([]);
      setWorkSessionHistory([]);
      setWorkItem(null);
      return;
    }
    void loadWorkTransitions(selectedWorkTicket.id);
    void loadWorkSessionHistory(selectedWorkTicket.id);
    void loadWorkItem(selectedWorkTicket.inventory_item);
  }, [
    loadWorkItem,
    loadWorkSessionHistory,
    loadWorkTransitions,
    selectedWorkTicket,
  ]);

  useEffect(() => {
    if (route.name !== "qc") {
      setQcTransitions([]);
      setQcItem(null);
      return;
    }
    void loadQcTickets();
  }, [loadQcTickets, route]);

  useEffect(() => {
    if (route.name !== "qc") {
      return;
    }
    if (!qcTickets.length) {
      setSelectedQcTicketId(null);
      return;
    }
    if (
      selectedQcTicketId === null ||
      !qcTickets.some((ticket) => ticket.id === selectedQcTicketId)
    ) {
      setSelectedQcTicketId(qcTickets[0].id);
    }
  }, [qcTickets, route, selectedQcTicketId]);

  useEffect(() => {
    if (!selectedQcTicket) {
      setQcTransitions([]);
      setQcItem(null);
      return;
    }
    void loadQcTransitions(selectedQcTicket.id);
    void loadQcItem(selectedQcTicket.inventory_item);
  }, [loadQcItem, loadQcTransitions, selectedQcTicket]);

  const handleRefresh = async () => {
    setFeedback(null);

    if (route.name === "createList") {
      await Promise.all([
        loadCategories(),
        loadCreateItems(appliedItemFilters, createItemsPage, createItemsPerPage),
      ]);
      return;
    }

    if (route.name === "createItem") {
      await Promise.all([loadCategories(), loadCreateItemPage(route.itemId)]);
      return;
    }
    if (route.name === "historyTicket") {
      await loadHistoryTicketPage(route.ticketId);
      return;
    }
    if (route.name === "review") {
      await Promise.all([loadCategories(), loadReviewTickets(), loadTechnicians()]);
      if (selectedReviewTicket) {
        await Promise.all([
          loadReviewTransitions(selectedReviewTicket.id),
          loadReviewItem(selectedReviewTicket.inventory_item),
        ]);
      }
      return;
    }
    if (route.name === "work") {
      await Promise.all([loadCategories(), loadWorkTickets()]);
      if (selectedWorkTicket) {
        await Promise.all([
          loadWorkTransitions(selectedWorkTicket.id),
          loadWorkSessionHistory(selectedWorkTicket.id),
          loadWorkItem(selectedWorkTicket.inventory_item),
        ]);
      }
      return;
    }

    await Promise.all([loadCategories(), loadQcTickets()]);
    if (selectedQcTicket) {
      await Promise.all([
        loadQcTransitions(selectedQcTicket.id),
        loadQcItem(selectedQcTicket.inventory_item),
      ]);
    }
  };

  const handleApplyItemFilters = () => {
    const normalizedSearch = normalizeInventorySerialSearchQuery(itemFilters.search);
    if (normalizedSearch.length === 1) {
      setFeedback({
        type: "info",
        message: t("Search query starts applying from 2 characters. Showing wider result set."),
      });
    } else {
      setFeedback(null);
    }

    setCreateItemsPage(1);
    setAppliedItemFilters(itemFilters);
  };

  const handleResetItemFilters = () => {
    setItemFilters(DEFAULT_ITEM_FILTERS);
    setAppliedItemFilters(DEFAULT_ITEM_FILTERS);
    setCreateItemsPage(1);
    setFeedback(null);
  };

  const handleCreateTicket = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canCreate || !selectedItem) {
      return;
    }

    if (!selectedItemParts.length) {
      setFeedback({
        type: "error",
        message: t("Selected inventory item has no parts. Add parts before ticket intake."),
      });
      return;
    }

    const selectedParts = selectedItemParts.filter((part) => {
      const form = partSpecForms[part.id];
      return Boolean(form?.selected);
    });

    if (!selectedParts.length) {
      setFeedback({
        type: "error",
        message: t("Select at least one part to continue."),
      });
      return;
    }

    const partSpecs = [] as Array<{
      part_id: number;
      color: TicketColor;
      comment: string;
      minutes: number;
    }>;

    for (const part of selectedParts) {
      const form = partSpecForms[part.id];
      if (!form) {
        setFeedback({
          type: "error",
          message: t("Part form state is missing. Refresh and try again."),
        });
        return;
      }

      const parsedMinutes = Number(form.minutes);
      if (!Number.isInteger(parsedMinutes) || parsedMinutes < 1) {
        setFeedback({
          type: "error",
          message: t("Minutes must be at least 1 for part {{part}}.", {
            part: part.name,
          }),
        });
        return;
      }

      partSpecs.push({
        part_id: part.id,
        color: form.color,
        comment: form.comment.trim(),
        minutes: parsedMinutes,
      });
    }

    try {
      await runMutation(async () => {
        await createTicket(accessToken, {
          serial_number: selectedItem.serial_number,
          title: ticketTitle.trim() || undefined,
          part_specs: partSpecs,
        });

        await loadCreateItemPage(selectedItem.id);
      }, t("Ticket created and sent to UNDER_REVIEW."));
    } catch {
      // feedback already set
    }
  };

  const handleManualMetricsSave = async () => {
    if (!canReview || !selectedReviewTicket) {
      return;
    }

    const parsedXp = Number(reviewXpAmount);
    if (!Number.isInteger(parsedXp) || parsedXp < 0) {
      setFeedback({
        type: "error",
        message: t("XP must be an integer greater than or equal to 0."),
      });
      return;
    }

    try {
      await runMutation(async () => {
        const updated = await reviewTicketManualMetrics(
          accessToken,
          selectedReviewTicket.id,
          {
            flag_color: reviewFlagColor,
            xp_amount: parsedXp,
          },
        );

        setReviewTickets((prev) =>
          prev.map((ticket) => (ticket.id === updated.id ? updated : ticket)),
        );

        await loadReviewTickets();
      }, t("Ticket review updated by admin."));
    } catch {
      // feedback already set
    }
  };

  const handleReviewApproveAndAssign = async () => {
    if (!canReview || !selectedReviewTicket) {
      return;
    }

    const parsedTechnicianId = Number(selectedTechnicianId);
    if (!Number.isInteger(parsedTechnicianId) || parsedTechnicianId < 1) {
      setFeedback({
        type: "error",
        message: t("Select a technician before approving the ticket."),
      });
      return;
    }

    try {
      await runMutation(async () => {
        const reviewedTicket =
          selectedReviewTicket.approved_at && selectedReviewTicket.approved_by
            ? selectedReviewTicket
            : await reviewApproveTicket(accessToken, selectedReviewTicket.id);
        const assigned = await assignTicket(
          accessToken,
          reviewedTicket.id,
          parsedTechnicianId,
        );

        setReviewTickets((prev) =>
          prev.map((ticket) => (ticket.id === assigned.id ? assigned : ticket)),
        );

        await Promise.all([
          loadReviewTickets(),
          loadReviewTransitions(assigned.id),
          loadReviewItem(assigned.inventory_item),
        ]);
      }, t("Ticket approved and assigned."));
    } catch {
      // feedback already set
    }
  };

  const handleWorkAction = async (
    action: "start" | "pause" | "resume" | "stop" | "to_waiting_qc",
  ) => {
    if (!canWork || !selectedWorkTicket) {
      return;
    }

    const successMessageMap: Record<typeof action, string> = {
      start: t("Work started."),
      pause: t("Work session paused."),
      resume: t("Work session resumed."),
      stop: t("Work session stopped."),
      to_waiting_qc: t("Ticket moved to waiting QC."),
    };

    try {
      await runMutation(async () => {
        if (action === "start") {
          await startTicketWork(accessToken, selectedWorkTicket.id);
        } else if (action === "pause") {
          await pauseTicketWorkSession(accessToken, selectedWorkTicket.id);
        } else if (action === "resume") {
          await resumeTicketWorkSession(accessToken, selectedWorkTicket.id);
        } else if (action === "stop") {
          await stopTicketWorkSession(accessToken, selectedWorkTicket.id);
        } else {
          await moveTicketToWaitingQc(accessToken, selectedWorkTicket.id);
        }

        await Promise.all([
          loadWorkTickets(),
          loadWorkTransitions(selectedWorkTicket.id),
          loadWorkSessionHistory(selectedWorkTicket.id),
          loadReviewTickets(),
          loadQcTickets(),
        ]);
      }, successMessageMap[action]);
    } catch {
      // feedback already set
    }
  };

  const handleQcDecision = async (decision: "pass" | "fail") => {
    if (!canQc || !selectedQcTicket) {
      return;
    }
    try {
      await runMutation(async () => {
        if (decision === "pass") {
          await qcPassTicket(accessToken, selectedQcTicket.id);
        } else {
          await qcFailTicket(accessToken, selectedQcTicket.id);
        }
        await Promise.all([
          loadQcTickets(),
          loadQcTransitions(selectedQcTicket.id),
          loadWorkTickets(),
          loadReviewTickets(),
        ]);
      }, decision === "pass" ? t("QC passed.") : t("QC failed. Sent to rework."));
    } catch {
      // feedback already set
    }
  };

  const renderCreateListPage = () => {
    const oneCharSearch =
      normalizeInventorySerialSearchQuery(itemFilters.search).length === 1;

    return (
      <div className="mt-4 space-y-4">
        <section className="rounded-lg border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-900">{t("Create Ticket")}</p>
          <p className="mt-1 text-sm text-slate-600">
            {t(
              "Pick an inventory item first. The next page shows ticket history for that item and the new-ticket intake form.",
            )}
          </p>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_1fr_auto]">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Search")}
              </label>
              <div className="relative mt-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  className={cn(fieldClassName, "pl-9")}
                  value={itemFilters.search}
                  onChange={(event) =>
                    setItemFilters((prev) => ({
                      ...prev,
                      search: event.target.value,
                    }))
                  }
                  onKeyDown={(event) => {
                    if (event.key !== "Enter") {
                      return;
                    }
                    event.preventDefault();
                    handleApplyItemFilters();
                  }}
                  placeholder={t("Serial number search")}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Category")}
              </label>
              <select
                className={cn(fieldClassName, "mt-1")}
                value={itemFilters.categoryId}
                onChange={(event) =>
                  setItemFilters((prev) => ({
                    ...prev,
                    categoryId: event.target.value,
                  }))
                }
                disabled={isLoadingCategories}
              >
                <option value="">{t("All categories")}</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Status")}
              </label>
              <select
                className={cn(fieldClassName, "mt-1")}
                value={itemFilters.status}
                onChange={(event) =>
                  setItemFilters((prev) => ({
                    ...prev,
                    status: event.target.value as ItemFilterState["status"],
                  }))
                }
              >
                <option value="all">{t("All statuses")}</option>
                {ITEM_STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {inventoryStatusLabel(option, t)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                {t("Active")}
              </label>
              <select
                className={cn(fieldClassName, "mt-1")}
                value={itemFilters.activity}
                onChange={(event) =>
                  setItemFilters((prev) => ({
                    ...prev,
                    activity: event.target.value as ItemFilterState["activity"],
                  }))
                }
              >
                <option value="all">{t("All")}</option>
                <option value="active">{t("Active")}</option>
                <option value="inactive">{t("Inactive")}</option>
              </select>
            </div>

            <div className="flex items-end gap-2">
              <Button
                type="button"
                className="h-10"
                onClick={handleApplyItemFilters}
                disabled={isLoadingCreateItems || !hasPendingItemFilterChanges}
              >
                {t("Apply")}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={handleResetItemFilters}
                disabled={isLoadingCreateItems}
              >
                {t("Reset")}
              </Button>
            </div>
          </div>

          {oneCharSearch ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Backend search starts at 2 characters.")}
            </p>
          ) : null}
        </section>

        <section className="rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">
              {t("Inventory Items ({{count}})", { count: createItemsPagination.total_count })}
            </p>
            <p className="text-xs text-slate-500">{t("Select item to continue")}</p>
          </div>

          {isLoadingCreateItems ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t("Loading items...")}</p>
          ) : !createItems.length ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">
              {t("No items found.")}
            </p>
          ) : (
            <>
              <div className="space-y-2 p-3 md:hidden">
                {createItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => navigate({ name: "createItem", itemId: item.id })}
                    className="w-full rounded-md border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-300"
                  >
                    <p className="text-sm font-semibold text-slate-900">{item.serial_number}</p>
                    <p className="text-sm text-slate-700">{item.name || "-"}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {t("Category")}: {categoryNameById.get(item.category) ?? `#${item.category}`}
                    </p>
                  </button>
                ))}
              </div>

              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Serial")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Name")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Category")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Status")}
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Action")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {createItems.map((item) => (
                      <tr key={item.id} className="transition hover:bg-slate-50">
                        <td className="px-4 py-3 text-sm font-medium text-slate-900">
                          {item.serial_number}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700">{item.name || "-"}</td>
                        <td className="px-4 py-3 text-sm text-slate-700">
                          {categoryNameById.get(item.category) ?? `#${item.category}`}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-xs font-medium",
                              inventoryStatusBadgeClass(item.status),
                            )}
                          >
                            {inventoryStatusLabelByValue.get(item.status) ?? item.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => navigate({ name: "createItem", itemId: item.id })}
                          >
                            {t("Select")}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <PaginationControls
            page={createItemsPagination.page}
            pageCount={createItemsPagination.page_count}
            perPage={createItemsPagination.per_page}
            totalCount={createItemsPagination.total_count}
            isLoading={isLoadingCreateItems}
            onPageChange={(nextPage) => setCreateItemsPage(nextPage)}
            onPerPageChange={(nextPerPage) => {
              setCreateItemsPerPage(nextPerPage);
              setCreateItemsPage(1);
            }}
            perPageOptions={LIST_PER_PAGE_OPTIONS}
          />
        </section>
      </div>
    );
  };

  const renderCreateItemPage = () => {
    if (isLoadingCreateItemPage) {
      return (
        <section className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="text-sm text-slate-600">{t("Loading ticket intake page...")}</p>
        </section>
      );
    }

    if (!selectedItem) {
      return (
        <section className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center">
          <p className="text-sm text-slate-600">{t("Inventory item not found.")}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3 h-10"
            onClick={() => navigate({ name: "createList" })}
          >
            {t("Back to Item List")}
          </Button>
        </section>
      );
    }

    return (
      <div className="mt-4 space-y-4">
        <button
          type="button"
          onClick={() => navigate({ name: "createList" })}
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("Back to item selection")}
        </button>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-lg font-semibold text-slate-900">{selectedItem.serial_number}</p>
          <p className="mt-1 text-sm text-slate-700">{selectedItem.name || t("Unnamed item")}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
            <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
              {t("Category")}: {categoryNameById.get(selectedItem.category) ?? `#${selectedItem.category}`}
            </span>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5",
                inventoryStatusBadgeClass(selectedItem.status),
              )}
            >
              {inventoryStatusLabelByValue.get(selectedItem.status) ?? selectedItem.status}
            </span>
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
          <section className="rounded-lg border border-slate-200 p-4">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <History className="h-4 w-4" />
              {t("Previous Ticket History ({{count}})", {
                count: selectedItemTicketHistory.length,
              })}
            </p>

            {selectedItemTicketHistory.length ? (
              <div className="mt-3 space-y-2">
                {selectedItemTicketHistory.map((ticket) => (
                  <button
                    key={ticket.id}
                    type="button"
                    onClick={() =>
                      navigate({ name: "historyTicket", ticketId: ticket.id })
                    }
                    className="w-full rounded-md border border-slate-200 bg-white p-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">
                        {t("Ticket #{{id}}", { id: ticket.id })}
                      </p>
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-xs font-medium",
                          ticketStatusBadgeClass(ticket.status),
                        )}
                      >
                        {ticketStatusLabelByValue.get(ticket.status) ?? ticket.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      {t("Created")}: {formatDate(ticket.created_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {t("Total Minutes")}: {ticket.total_duration} | {t("Flag")}:{" "}
                      {ticketColorLabelByValue.get(ticket.flag_color) ?? ticket.flag_color}
                    </p>
                    <p className="mt-2 text-xs font-semibold text-slate-800">
                      {t("Open full ticket details")}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
                {t("No previous tickets for this item.")}
              </p>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <FilePlus2 className="h-4 w-4" />
              {t("New Ticket Intake")}
            </p>
            <p className="mt-1 text-xs text-slate-600">{t("Select at least one part.")}</p>

            <form onSubmit={handleCreateTicket} className="mt-3 space-y-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Title (optional)")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={ticketTitle}
                  onChange={(event) => setTicketTitle(event.target.value)}
                  disabled={!canCreate || isMutating}
                  placeholder={t("Ticket title")}
                />
              </div>

              {selectedItemParts.length ? (
                <div className="space-y-2">
                  {selectedItemParts.map((part) => {
                    const form = partSpecForms[part.id];
                    if (!form) {
                      return null;
                    }

                    return (
                      <div
                        key={part.id}
                        className="rounded-md border border-slate-200 bg-slate-50 p-3"
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-900">
                            <input
                              type="checkbox"
                              checked={form.selected}
                              onChange={(event) =>
                                setPartSpecForms((prev) => ({
                                  ...prev,
                                  [part.id]: {
                                    ...prev[part.id],
                                    selected: event.target.checked,
                                  },
                                }))
                              }
                              disabled={!canCreate || isMutating}
                            />
                            {part.name}
                          </label>
                          <p className="text-xs text-slate-500">
                            {t("Part ID")}: {part.id}
                          </p>
                        </div>

                        <div className="mt-3 grid gap-2 md:grid-cols-3">
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              {t("Color")}
                            </label>
                            <select
                              className={cn(fieldClassName, "mt-1")}
                              value={form.color}
                              onChange={(event) =>
                                setPartSpecForms((prev) => ({
                                  ...prev,
                                  [part.id]: {
                                    ...prev[part.id],
                                    color: event.target.value as TicketColor,
                                  },
                                }))
                              }
                              disabled={!canCreate || isMutating || !form.selected}
                            >
                              {TICKET_COLOR_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {ticketColorLabel(option, t)}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              {t("Minutes")}
                            </label>
                            <input
                              type="number"
                              min={1}
                              className={cn(fieldClassName, "mt-1")}
                              value={form.minutes}
                              onChange={(event) =>
                                setPartSpecForms((prev) => ({
                                  ...prev,
                                  [part.id]: {
                                    ...prev[part.id],
                                    minutes: event.target.value,
                                  },
                                }))
                              }
                              disabled={!canCreate || isMutating || !form.selected}
                              placeholder={t("e.g. 20")}
                            />
                          </div>

                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              {t("Comment (optional)")}
                            </label>
                            <input
                              className={cn(fieldClassName, "mt-1")}
                              value={form.comment}
                              onChange={(event) =>
                                setPartSpecForms((prev) => ({
                                  ...prev,
                                  [part.id]: {
                                    ...prev[part.id],
                                    comment: event.target.value,
                                  },
                                }))
                              }
                              disabled={!canCreate || isMutating || !form.selected}
                              placeholder={t("Part note")}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-600">
                  {t(
                    "This item has no parts. Add parts in inventory management before ticket intake.",
                  )}
                </p>
              )}

              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                {t("Selected parts")}: {selectedPartsCount}/{selectedItemParts.length || 0}
              </div>

              {!canCreate ? (
                <p className="text-xs text-amber-700">
                  {t("Your roles do not allow ticket creation.")}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button
                  type="submit"
                  className="h-10"
                  disabled={
                    !canCreate ||
                    isMutating ||
                    !selectedItemParts.length ||
                    selectedPartsCount < 1
                  }
                >
                  {t("Create Ticket")}
                </Button>
                {canReview ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10"
                    onClick={() => navigate({ name: "review" })}
                  >
                    {t("Open Review Queue")}
                  </Button>
                ) : null}
              </div>
            </form>
          </section>
        </div>
      </div>
    );
  };

  const renderHistoryTicketPage = () => {
    if (isLoadingHistoryTicket) {
      return (
        <section className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="text-sm text-slate-600">{t("Loading full ticket details...")}</p>
        </section>
      );
    }

    if (!historyTicket) {
      return (
        <section className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center">
          <p className="text-sm text-slate-600">{t("Ticket details were not found.")}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3 h-10"
            onClick={() => navigate({ name: "createList" })}
          >
            {t("Back to Ticket Create")}
          </Button>
        </section>
      );
    }

    const ticketStatusLabel =
      ticketStatusLabelByValue.get(historyTicket.status) ?? historyTicket.status;
    const itemSerial = historyItem?.serial_number ?? t("Item #{{id}}", {
      id: historyTicket.inventory_item,
    });
    const masterLabel = resolveHistoryActorLabel(
      historyTicket.master,
      historyTicket.master_name,
    );
    const technicianLabel = historyTicket.technician
      ? resolveHistoryActorLabel(
          historyTicket.technician,
          historyTicket.technician_name,
        )
      : t("Not assigned");
    const approvedByLabel = historyTicket.approved_by
      ? resolveHistoryActorLabel(
          historyTicket.approved_by,
          historyTicket.approved_by_name,
        )
      : t("Not approved yet");
    const pauseCount = historyWorkSessionHistory.filter(
      (entry) => entry.action === "paused",
    ).length;
    const resumeCount = historyWorkSessionHistory.filter(
      (entry) => entry.action === "resumed",
    ).length;
    const stopCount = historyWorkSessionHistory.filter(
      (entry) => entry.action === "stopped",
    ).length;

    return (
      <div className="mt-4 space-y-4">
        <button
          type="button"
          onClick={() =>
            navigate({ name: "createItem", itemId: historyTicket.inventory_item })
          }
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("Back to item ticket history")}
        </button>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xl font-semibold text-slate-900">
              {t("Ticket #{{id}}", { id: historyTicket.id })}
            </p>
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 text-xs font-medium",
                ticketStatusBadgeClass(historyTicket.status),
              )}
            >
              {ticketStatusLabel}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-700">{historyTicket.title || t("No title")}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
            <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
              {t("Item")}: {itemSerial}
            </span>
            <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
              {t("Opened {{at}} by {{name}}", {
                at: formatDate(historyTicket.created_at),
                name: masterLabel,
              })}
            </span>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("Workflow Events")}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {historyTransitions.length}
            </p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("Work Session Events")}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {historyWorkSessionHistory.length}
            </p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("Pauses / Resumes")}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {pauseCount} / {resumeCount}
            </p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("Stops")}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{stopCount}</p>
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
          <div className="space-y-4">
            <section className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-900">{t("Ticket Snapshot")}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Master")}</p>
                  <p className="text-sm font-medium text-slate-900">{masterLabel}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Technician")}</p>
                  <p className="text-sm font-medium text-slate-900">{technicianLabel}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Approved By")}</p>
                  <p className="text-sm font-medium text-slate-900">{approvedByLabel}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Flag / XP")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatTokenLabel(historyTicket.flag_color)} / {historyTicket.xp_amount}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Created")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatDate(historyTicket.created_at)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Assigned")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatDate(historyTicket.assigned_at)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Started")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatDate(historyTicket.started_at)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Finished")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatDate(historyTicket.finished_at)}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Total Minutes")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {historyTicket.total_duration}
                  </p>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                  <p className="text-xs text-slate-500">{t("Manual Metrics")}</p>
                  <p className="text-sm font-medium text-slate-900">
                    {historyTicket.is_manual ? t("Yes") : t("No")}
                  </p>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-900">{t("Selected Part Specs")}</p>
              {historyTicket.ticket_parts.length ? (
                <div className="mt-3 space-y-2">
                  {historyTicket.ticket_parts.map((part) => (
                    <div
                      key={part.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{part.part_name}</p>
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-xs font-medium",
                            ticketColorBadgeClass(part.color),
                          )}
                        >
                          {ticketColorLabelByValue.get(part.color) ?? part.color}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">{t("Minutes")}: {part.minutes}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Comment")}: {part.comment || "-"}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
                  {t("No part specs found on this ticket.")}
                </p>
              )}
            </section>
          </div>

          <section className="rounded-lg border border-slate-200 p-4">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <History className="h-4 w-4" />
              {t("Full Activity Timeline")}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {t("Workflow changes and work-session events sorted by time.")}
            </p>

            {historyTimeline.length ? (
              <div className="mt-3 space-y-2">
                {historyTimeline.map((event) => {
                  const metadataEntries = Object.entries(event.metadata ?? {});
                  return (
                    <div
                      key={event.key}
                      className="rounded-md border border-slate-200 bg-slate-50 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
                            event.source === "workflow"
                              ? "border-sky-200 bg-sky-100 text-sky-700"
                              : "border-amber-200 bg-amber-100 text-amber-700",
                          )}
                        >
                          {event.source === "workflow" ? t("Workflow") : t("Work Session")}
                        </span>
                        <p className="text-sm font-semibold text-slate-900">
                          {formatTokenLabel(event.action)}
                        </p>
                      </div>

                      <p className="mt-1 text-xs text-slate-600">
                        {t("Actor")}: {event.actorLabel}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Status")}: {formatTokenLabel(event.fromStatus)} {"->"}{" "}
                        {formatTokenLabel(event.toStatus)}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("At")}: {formatDate(event.at)}
                      </p>
                      {event.note ? (
                        <p className="mt-1 text-xs text-slate-600">{t("Note")}: {event.note}</p>
                      ) : null}

                      {metadataEntries.length ? (
                        <div className="mt-2 grid gap-1 sm:grid-cols-2">
                          {metadataEntries.map(([key, value]) => (
                            <p
                              key={`${event.key}-${key}`}
                              className="rounded border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600"
                            >
                              <span className="font-semibold text-slate-700">
                                {formatTokenLabel(key)}:
                              </span>{" "}
                              {formatMetadataValue(value)}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
                {t("No ticket events found.")}
              </p>
            )}
          </section>
        </div>
      </div>
    );
  };

  const renderReviewPage = () => (
    <div className="mt-4 grid gap-4 xl:grid-cols-[360px_1fr]">
      <section className="rounded-lg border border-slate-200 p-4">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
          <ClipboardCheck className="h-4 w-4" />
          {t("Review Queue")}
        </p>

        <div className="mt-3 space-y-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Search")}
            </label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className={cn(fieldClassName, "pl-9")}
                value={reviewSearch}
                onChange={(event) => setReviewSearch(event.target.value)}
                placeholder={t("Ticket id, serial, title")}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Status")}
            </label>
            <select
              className={cn(fieldClassName, "mt-1")}
              value={reviewStatusFilter}
              onChange={(event) =>
                setReviewStatusFilter(event.target.value as "all" | TicketStatus)
              }
            >
              <option value="all">{t("All statuses")}</option>
              {TICKET_STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {ticketStatusLabel(option, t)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {reviewSearch.trim().length === 1 ? (
          <p className="mt-2 text-xs text-amber-700">
            {t("Backend search starts at 2 characters.")}
          </p>
        ) : null}

        {isLoadingReviewTickets ? (
          <p className="mt-3 text-sm text-slate-600">{t("Loading tickets...")}</p>
        ) : reviewTickets.length ? (
          <div className="mt-3 space-y-2">
            {reviewTickets.map((ticket) => {
              const item = inventoryCache[ticket.inventory_item];
              return (
                <button
                  key={ticket.id}
                  type="button"
                  onClick={() => setSelectedReviewTicketId(ticket.id)}
                  className={cn(
                    "w-full rounded-md border p-3 text-left transition",
                    selectedReviewTicketId === ticket.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 hover:border-slate-300",
                  )}
                >
                  <p className="text-sm font-semibold">
                    {t("Ticket #{{id}}", { id: ticket.id })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id
                        ? "text-slate-200"
                        : "text-slate-600",
                    )}
                  >
                    {item?.serial_number ?? t("Item #{{id}}", { id: ticket.inventory_item })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id
                        ? "text-slate-200"
                        : "text-slate-600",
                    )}
                  >
                    {ticket.title || t("No title")}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
            {t("No tickets in review queue.")}
          </p>
        )}

        <PaginationControls
          className="mt-3 -mx-4"
          page={reviewPagination.page}
          pageCount={reviewPagination.page_count}
          perPage={reviewPagination.per_page}
          totalCount={reviewPagination.total_count}
          isLoading={isLoadingReviewTickets}
          onPageChange={(nextPage) => setReviewPage(nextPage)}
          onPerPageChange={(nextPerPage) => {
            setReviewPerPage(nextPerPage);
            setReviewPage(1);
          }}
          perPageOptions={LIST_PER_PAGE_OPTIONS}
        />
      </section>

      <section className="rounded-lg border border-slate-200 p-4">
        {selectedReviewTicket ? (
          <div className="space-y-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold text-slate-900">
                  {t("Ticket #{{id}}", { id: selectedReviewTicket.id })}
                </p>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs font-medium",
                    ticketStatusBadgeClass(selectedReviewTicket.status),
                  )}
                >
                  {ticketStatusLabelByValue.get(selectedReviewTicket.status) ??
                    selectedReviewTicket.status}
                </span>
              </div>

              <p className="mt-1 text-sm text-slate-700">
                {selectedReviewTicket.title || t("No title")}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {t("Item")}:{" "}
                {reviewItem?.serial_number ??
                  t("Item #{{id}}", { id: selectedReviewTicket.inventory_item })}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {t("Created")}: {formatDate(selectedReviewTicket.created_at)}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {t("Auto/Current Minutes")}: {selectedReviewTicket.total_duration}
              </p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-900">{t("Part Specs")}</p>

                {selectedReviewTicket.ticket_parts.length ? (
                  <div className="mt-2 space-y-2">
                    {selectedReviewTicket.ticket_parts.map((part) => (
                      <div
                        key={part.id}
                        className="rounded-md border border-slate-200 bg-slate-50 p-2"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-slate-900">{part.part_name}</p>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-xs font-medium",
                              ticketColorBadgeClass(part.color),
                            )}
                          >
                            {ticketColorLabelByValue.get(part.color) ?? part.color}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-slate-600">{t("Minutes")}: {part.minutes}</p>
                        <p className="mt-1 text-xs text-slate-600">
                          {t("Comment")}: {part.comment || "-"}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-600">{t("No part specs.")}</p>
                )}
              </div>

              <div className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-900">{t("Review Actions")}</p>
                <p className="mt-1 text-xs text-slate-600">
                  {t("Approve review and assign a technician in one action.")}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  {t("Current technician")}:{" "}
                  {selectedReviewTicket.technician
                    ? technicianLabelById.get(selectedReviewTicket.technician) ??
                      t("User #{{id}}", { id: selectedReviewTicket.technician })
                    : t("Not assigned")}
                </p>

                <div className="mt-3">
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Technician")}
                  </label>
                  <select
                    className={cn(fieldClassName, "mt-1")}
                    value={selectedTechnicianId}
                    onChange={(event) => setSelectedTechnicianId(event.target.value)}
                    disabled={!canReview || isMutating || isLoadingTechnicians}
                  >
                    <option value="">
                      {isLoadingTechnicians ? t("Loading technicians...") : t("Select technician")}
                    </option>
                    {technicianOptions.map((technician) => (
                      <option key={technician.user_id} value={technician.user_id}>
                        {technician.name === technician.username
                          ? technician.username
                          : `${technician.name} (@${technician.username})`}
                      </option>
                    ))}
                  </select>
                </div>

                {!canReview ? (
                  <p className="mt-2 text-xs text-amber-700">
                    {t("Your roles do not allow ticket review.")}
                  </p>
                ) : null}

                <div className="mt-3">
                  <Button
                    type="button"
                    className="h-10"
                    onClick={() => void handleReviewApproveAndAssign()}
                    disabled={
                      !canReview ||
                      isMutating ||
                      isLoadingTechnicians ||
                      !selectedTechnicianId
                    }
                  >
                    {t("Approve & Assign")}
                  </Button>
                </div>

                <div className="mt-4 border-t border-slate-200 pt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Manual Metrics (Optional)")}
                  </p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("Flag Color")}
                      </label>
                      <select
                        className={cn(fieldClassName, "mt-1")}
                        value={reviewFlagColor}
                        onChange={(event) =>
                          setReviewFlagColor(event.target.value as TicketColor)
                        }
                        disabled={!canReview || isMutating}
                      >
                        {TICKET_COLOR_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {ticketColorLabel(option, t)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("XP Amount")}
                      </label>
                      <input
                        type="number"
                        min={0}
                        className={cn(fieldClassName, "mt-1")}
                        value={reviewXpAmount}
                        onChange={(event) => setReviewXpAmount(event.target.value)}
                        disabled={!canReview || isMutating}
                      />
                    </div>
                  </div>
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="outline"
                      className="h-10"
                      onClick={() => void handleManualMetricsSave()}
                      disabled={!canReview || isMutating}
                    >
                      {t("Save Manual Metrics")}
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold text-slate-900">{t("Ticket Transitions")}</p>

              {isLoadingReviewTransitions ? (
                <p className="mt-2 text-sm text-slate-600">{t("Loading transitions...")}</p>
              ) : reviewTransitions.length ? (
                <div className="mt-2 space-y-2">
                  {reviewTransitions.map((transition) => (
                    <div
                      key={transition.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-2"
                    >
                      <p className="text-xs font-semibold text-slate-900">
                        {transition.action}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {transition.from_status || "-"} {"->"} {transition.to_status}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {formatDate(transition.created_at)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{t("No transitions yet.")}</p>
              )}
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Select a ticket from the queue.")}
          </p>
        )}
      </section>
    </div>
  );

  const renderWorkPage = () => (
    <div className="mt-4 grid gap-4 xl:grid-cols-[360px_1fr]">
      <section className="rounded-lg border border-slate-200 p-4">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
          <ClipboardCheck className="h-4 w-4" />
          {t("Technician Queue")}
        </p>
        <div className="mt-3 space-y-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Search")}
            </label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className={cn(fieldClassName, "pl-9")}
                value={workSearch}
                onChange={(event) => setWorkSearch(event.target.value)}
                placeholder={t("Ticket id, serial, title")}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Status")}
            </label>
            <select
              className={cn(fieldClassName, "mt-1")}
              value={workStatusFilter}
              onChange={(event) =>
                setWorkStatusFilter(
                  event.target.value as "all" | "assigned" | "in_progress" | "rework" | "waiting_qc",
                )
              }
            >
              <option value="all">{t("All work statuses")}</option>
              <option value="assigned">{t("Assigned")}</option>
              <option value="in_progress">{t("In progress")}</option>
              <option value="rework">{t("Rework")}</option>
              <option value="waiting_qc">{t("Waiting QC")}</option>
            </select>
          </div>
        </div>

        {workSearch.trim().length === 1 ? (
          <p className="mt-2 text-xs text-amber-700">
            {t("Backend search starts at 2 characters.")}
          </p>
        ) : null}

        {isLoadingWorkTickets ? (
          <p className="mt-3 text-sm text-slate-600">{t("Loading technician queue...")}</p>
        ) : workVisibleTickets.length ? (
          <div className="mt-3 space-y-2">
            {workVisibleTickets.map((ticket) => {
              const item = inventoryCache[ticket.inventory_item];
              return (
                <button
                  key={ticket.id}
                  type="button"
                  onClick={() => setSelectedWorkTicketId(ticket.id)}
                  className={cn(
                    "w-full rounded-md border p-3 text-left transition",
                    selectedWorkTicketId === ticket.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 hover:border-slate-300",
                  )}
                >
                  <p className="text-sm font-semibold">
                    {t("Ticket #{{id}}", { id: ticket.id })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedWorkTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {item?.serial_number ?? t("Item #{{id}}", { id: ticket.inventory_item })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedWorkTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {ticketStatusLabelByValue.get(ticket.status) ?? ticket.status}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
            {t("No tickets in technician queue.")}
          </p>
        )}

        <PaginationControls
          className="mt-3 -mx-4"
          page={workPagination.page}
          pageCount={workPagination.page_count}
          perPage={workPagination.per_page}
          totalCount={workPagination.total_count}
          isLoading={isLoadingWorkTickets}
          onPageChange={(nextPage) => setWorkPage(nextPage)}
          onPerPageChange={(nextPerPage) => {
            setWorkPerPage(nextPerPage);
            setWorkPage(1);
          }}
          perPageOptions={LIST_PER_PAGE_OPTIONS}
        />
      </section>

      <section className="rounded-lg border border-slate-200 p-4">
        {selectedWorkTicket ? (
          <div className="space-y-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold text-slate-900">
                  {t("Ticket #{{id}}", { id: selectedWorkTicket.id })}
                </p>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs font-medium",
                    ticketStatusBadgeClass(selectedWorkTicket.status),
                  )}
                >
                  {ticketStatusLabelByValue.get(selectedWorkTicket.status) ??
                    selectedWorkTicket.status}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                {t("Item")}:{" "}
                {workItem?.serial_number ??
                  t("Item #{{id}}", { id: selectedWorkTicket.inventory_item })}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {t("Session status")}: {currentWorkSessionStatus ?? t("none")}
              </p>
            </div>

            {!canWork ? (
              <p className="rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {t("Your roles do not allow work-session actions.")}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void handleWorkAction("stop")}
                disabled={
                  !canWork ||
                  isMutating ||
                  selectedWorkTicket.status !== "in_progress" ||
                  !["running", "paused"].includes(currentWorkSessionStatus ?? "")
                }
              >
                {t("Stop")}
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => void handleWorkAction("to_waiting_qc")}
                disabled={
                  !canWork ||
                  isMutating ||
                  selectedWorkTicket.status !== "in_progress" ||
                  currentWorkSessionStatus !== "stopped"
                }
              >
                {t("Move To QC")}
              </Button>
            </div>

            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold text-slate-900">{t("Work Session History")}</p>
              {isLoadingWorkSessionHistory ? (
                <p className="mt-2 text-sm text-slate-600">{t("Loading history...")}</p>
              ) : workSessionHistory.length ? (
                <div className="mt-2 space-y-2">
                  {workSessionHistory.map((entry) => (
                    <div
                      key={entry.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-2"
                    >
                      <p className="text-xs font-semibold text-slate-900">{entry.action}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {entry.from_status || "-"} {"->"} {entry.to_status}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {formatDate(entry.event_at)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{t("No work session events yet.")}</p>
              )}
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Select a ticket from technician queue.")}
          </p>
        )}
      </section>
    </div>
  );

  const renderQcPage = () => (
    <div className="mt-4 grid gap-4 xl:grid-cols-[360px_1fr]">
      <section className="rounded-lg border border-slate-200 p-4">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
          <ClipboardCheck className="h-4 w-4" />
          {t("QC Queue")}
        </p>
        <div className="mt-3 space-y-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Search")}
            </label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className={cn(fieldClassName, "pl-9")}
                value={qcSearch}
                onChange={(event) => setQcSearch(event.target.value)}
                placeholder={t("Ticket id, serial, title")}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              {t("Status")}
            </label>
            <select
              className={cn(fieldClassName, "mt-1")}
              value={qcStatusFilter}
              onChange={(event) => setQcStatusFilter(event.target.value as "waiting_qc" | "all")}
            >
              <option value="waiting_qc">{t("Waiting QC")}</option>
              <option value="all">{t("All statuses")}</option>
            </select>
          </div>
        </div>

        {qcSearch.trim().length === 1 ? (
          <p className="mt-2 text-xs text-amber-700">
            {t("Backend search starts at 2 characters.")}
          </p>
        ) : null}

        {isLoadingQcTickets ? (
          <p className="mt-3 text-sm text-slate-600">{t("Loading QC queue...")}</p>
        ) : qcTickets.length ? (
          <div className="mt-3 space-y-2">
            {qcTickets.map((ticket) => {
              const item = inventoryCache[ticket.inventory_item];
              return (
                <button
                  key={ticket.id}
                  type="button"
                  onClick={() => setSelectedQcTicketId(ticket.id)}
                  className={cn(
                    "w-full rounded-md border p-3 text-left transition",
                    selectedQcTicketId === ticket.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 hover:border-slate-300",
                  )}
                >
                  <p className="text-sm font-semibold">
                    {t("Ticket #{{id}}", { id: ticket.id })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedQcTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {item?.serial_number ?? t("Item #{{id}}", { id: ticket.inventory_item })}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedQcTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {ticketStatusLabelByValue.get(ticket.status) ?? ticket.status}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
            {t("No tickets in QC queue.")}
          </p>
        )}

        <PaginationControls
          className="mt-3 -mx-4"
          page={qcPagination.page}
          pageCount={qcPagination.page_count}
          perPage={qcPagination.per_page}
          totalCount={qcPagination.total_count}
          isLoading={isLoadingQcTickets}
          onPageChange={(nextPage) => setQcPage(nextPage)}
          onPerPageChange={(nextPerPage) => {
            setQcPerPage(nextPerPage);
            setQcPage(1);
          }}
          perPageOptions={LIST_PER_PAGE_OPTIONS}
        />
      </section>

      <section className="rounded-lg border border-slate-200 p-4">
        {selectedQcTicket ? (
          <div className="space-y-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold text-slate-900">
                  {t("Ticket #{{id}}", { id: selectedQcTicket.id })}
                </p>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs font-medium",
                    ticketStatusBadgeClass(selectedQcTicket.status),
                  )}
                >
                  {ticketStatusLabelByValue.get(selectedQcTicket.status) ?? selectedQcTicket.status}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-600">
                {t("Item")}:{" "}
                {qcItem?.serial_number ??
                  t("Item #{{id}}", { id: selectedQcTicket.inventory_item })}
              </p>
            </div>

            {!canQc ? (
              <p className="rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {t("You can view QC queue, but your roles cannot run QC pass/fail actions.")}
              </p>
            ) : null}

            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold text-slate-900">{t("Part Specs")}</p>
              {selectedQcTicket.ticket_parts.length ? (
                <div className="mt-2 space-y-2">
                  {selectedQcTicket.ticket_parts.map((part) => (
                    <div
                      key={part.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-2"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-slate-900">{part.part_name}</p>
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-xs font-medium",
                            ticketColorBadgeClass(part.color),
                          )}
                        >
                          {ticketColorLabelByValue.get(part.color) ?? part.color}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">{t("Minutes")}: {part.minutes}</p>
                      <p className="mt-1 text-xs text-slate-600">
                        {t("Comment")}: {part.comment || "-"}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{t("No part specs.")}</p>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => void handleQcDecision("pass")}
                disabled={!canQc || isMutating || selectedQcTicket.status !== "waiting_qc"}
              >
                {t("QC Pass")}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="text-rose-700"
                onClick={() => void handleQcDecision("fail")}
                disabled={!canQc || isMutating || selectedQcTicket.status !== "waiting_qc"}
              >
                {t("QC Fail")}
              </Button>
            </div>

            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold text-slate-900">{t("Ticket Transitions")}</p>
              {isLoadingQcTransitions ? (
                <p className="mt-2 text-sm text-slate-600">{t("Loading transitions...")}</p>
              ) : qcTransitions.length ? (
                <div className="mt-2 space-y-2">
                  {qcTransitions.map((transition) => (
                    <div
                      key={transition.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-2"
                    >
                      <p className="text-xs font-semibold text-slate-900">
                        {transition.action}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {transition.from_status || "-"} {"->"} {transition.to_status}
                      </p>
                      <p className="mt-1 text-xs text-slate-600">
                        {formatDate(transition.created_at)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{t("No transitions yet.")}</p>
              )}
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            {t("Select a ticket from QC queue.")}
          </p>
        )}
      </section>
    </div>
  );

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Ticket Flow")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Full lifecycle: intake, admin review/assignment, technician execution, and QC.")}
          </p>
          {!canCreate ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot create tickets.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
          {!canReview ? (
            <p className="mt-1 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot perform admin review.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
          {showWorkTab && !canWork ? (
            <p className="mt-1 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot run technician workflow.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
          {!canQc ? (
            <p className="mt-1 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot run QC pass/fail.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-10 w-full sm:w-auto"
          onClick={() => void handleRefresh()}
          disabled={
            isMutating ||
            isLoadingCategories ||
            isLoadingCreateItems ||
            isLoadingCreateItemPage ||
            isLoadingHistoryTicket ||
            isLoadingReviewTickets ||
            isLoadingWorkTickets ||
            isLoadingQcTickets ||
            isLoadingTechnicians ||
            isLoadingReviewTransitions ||
            isLoadingWorkTransitions ||
            isLoadingWorkSessionHistory ||
            isLoadingQcTransitions
          }
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          {t("Refresh")}
        </Button>
      </div>

      <FeedbackToast feedback={feedback} />

      {!visibleMenus.length ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-700">
          {t("Your current role does not have access to ticket flows in this app.")}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {canAccessCreateMenu ? (
          <button
            type="button"
            onClick={() => navigate({ name: "createList" })}
            className={cn(
              "rm-menu-btn",
              activeMenu === "create"
                ? "rm-menu-btn-active"
                : "rm-menu-btn-idle",
            )}
          >
            <span className="inline-flex items-center gap-2">
              <Ticket className="h-4 w-4" />
              {t("Create Ticket")}
            </span>
          </button>
        ) : null}

        {canAccessReviewMenu ? (
          <button
            type="button"
            onClick={() => navigate({ name: "review" })}
            className={cn(
              "rm-menu-btn",
              activeMenu === "review"
                ? "rm-menu-btn-active"
                : "rm-menu-btn-idle",
            )}
          >
            <span className="inline-flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4" />
              {t("Review Tickets")}
            </span>
          </button>
        ) : null}

        {canAccessWorkMenu ? (
          <button
            type="button"
            onClick={() => navigate({ name: "work" })}
            className={cn(
              "rm-menu-btn",
              activeMenu === "work"
                ? "rm-menu-btn-active"
                : "rm-menu-btn-idle",
            )}
          >
            <span className="inline-flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4" />
              {t("Technician Work")}
            </span>
          </button>
        ) : null}

        {canAccessQcMenu ? (
          <button
            type="button"
            onClick={() => navigate({ name: "qc" })}
            className={cn(
              "rm-menu-btn",
              activeMenu === "qc"
                ? "rm-menu-btn-active"
                : "rm-menu-btn-idle",
            )}
          >
            <span className="inline-flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4" />
              {t("QC Queue")}
            </span>
          </button>
        ) : null}
      </div>

      {visibleMenus.length ? (
        <>
          {route.name === "createList" ? renderCreateListPage() : null}
          {route.name === "createItem" ? renderCreateItemPage() : null}
          {route.name === "historyTicket" ? renderHistoryTicketPage() : null}
          {route.name === "review" ? renderReviewPage() : null}
          {route.name === "work" ? renderWorkPage() : null}
          {route.name === "qc" ? renderQcPage() : null}
        </>
      ) : null}
    </section>
  );
}
