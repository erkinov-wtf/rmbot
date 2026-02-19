import {
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  PlusSquare,
  RefreshCcw,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import {
  assignTicket,
  createTicket,
  getInventoryItem,
  listInventoryItems,
  listParts,
  listTechnicianOptions,
  listTickets,
  qcFailTicket,
  qcPassTicket,
  reviewApproveTicket,
  reviewTicketManualMetrics,
  type InventoryItem,
  type InventoryPart,
  type TechnicianOption,
  type Ticket,
  type TicketColor,
  type TicketFlowPermissions,
  type TicketStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type MobileTicketFlowProps = {
  accessToken: string;
  permissions: TicketFlowPermissions;
};

type MiniTab = "create" | "review" | "qc";

type FeedbackState =
  | {
      type: "success" | "error" | "info";
      message: string;
    }
  | null;

type PartDraft = {
  selected: boolean;
  color: TicketColor;
  minutes: string;
  comment: string;
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
const INVENTORY_SEARCH_MIN_CHARS = 2;

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

function distinctNumbers(values: number[]): number[] {
  return [...new Set(values)];
}

export function MobileTicketFlow({ accessToken, permissions }: MobileTicketFlowProps) {
  const { t } = useI18n();
  const availableTabs = useMemo(
    () =>
      (Object.keys(TAB_META) as MiniTab[]).filter(
        (tab) => permissions[TAB_META[tab].permission],
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

  const [qcTickets, setQcTickets] = useState<Ticket[]>([]);
  const [isLoadingQcTickets, setIsLoadingQcTickets] = useState(false);
  const [qcSearch, setQcSearch] = useState("");
  const [selectedQcTicketId, setSelectedQcTicketId] = useState<number | null>(null);
  const [isRunningQcAction, setIsRunningQcAction] = useState(false);

  const statusLabel = useCallback(
    (status: TicketStatus) => t(STATUS_LABEL[status]),
    [t],
  );
  const colorLabel = useCallback(
    (color: TicketColor) => t(COLOR_LABEL[color]),
    [t],
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
      const search = createSearch.trim();
      const hasSearch = search.length >= INVENTORY_SEARCH_MIN_CHARS;
      const items = await listInventoryItems(accessToken, {
        q: hasSearch ? search : undefined,
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
          color: "green",
          minutes: "",
          comment: "",
        };
      });
      return next;
    });
  }, [selectedCreateItem, selectedCreateParts]);

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

  const updatePartDraft = useCallback(
    (partId: number, patch: Partial<PartDraft>) => {
      setPartDrafts((prev) => ({
        ...prev,
        [partId]: {
          ...(prev[partId] ?? {
            selected: false,
            color: "green",
            minutes: "",
            comment: "",
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
      .map((part) => {
        const draft = partDrafts[part.id];
        const parsedMinutes = Number.parseInt(draft.minutes, 10);
        return {
          part_id: part.id,
          color: draft.color,
          comment: draft.comment.trim(),
          minutes: parsedMinutes,
        };
      });

    if (!selectedPartSpecs.length) {
      setFeedback({
        type: "info",
        message: t("Select at least one part for the ticket."),
      });
      return;
    }
    if (
      selectedPartSpecs.some(
        (spec) => !Number.isFinite(spec.minutes) || spec.minutes <= 0,
      )
    ) {
      setFeedback({
        type: "error",
        message: t("Each selected part needs a valid minutes value (> 0)."),
      });
      return;
    }

    setIsCreatingTicket(true);
    try {
      await createTicket(accessToken, {
        serial_number: selectedCreateItem.serial_number,
        title: ticketTitle.trim() || undefined,
        part_specs: selectedPartSpecs.map((spec) => ({
          part_id: spec.part_id,
          color: spec.color,
          comment: spec.comment || undefined,
          minutes: spec.minutes,
        })),
      });
      setFeedback({
        type: "success",
        message: t("Ticket created successfully."),
      });
      setSelectedCreateItemId(null);
      setPartDrafts({});
      setTicketTitle("");
      void Promise.all([refreshReviewTickets(), refreshQcTickets()]);
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
    partDrafts,
    refreshQcTickets,
    refreshReviewTickets,
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
      await refreshReviewTickets();
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

  const handleQcDecision = useCallback(
    async (decision: "pass" | "fail") => {
      if (!selectedQcTicket) {
        return;
      }
      setIsRunningQcAction(true);
      try {
        if (decision === "pass") {
          await qcPassTicket(accessToken, selectedQcTicket.id);
        } else {
          await qcFailTicket(accessToken, selectedQcTicket.id);
        }
        setFeedback({
          type: "success",
          message:
            decision === "pass"
              ? t("QC passed for ticket #{{id}}.", { id: selectedQcTicket.id })
              : t("QC failed for ticket #{{id}}.", { id: selectedQcTicket.id }),
        });
        await Promise.all([refreshQcTickets(), refreshReviewTickets()]);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Could not process QC action.")),
        });
      } finally {
        setIsRunningQcAction(false);
      }
    },
    [accessToken, refreshQcTickets, refreshReviewTickets, selectedQcTicket, t],
  );

  const tabGridClass =
    availableTabs.length === 1
      ? "grid-cols-1"
      : availableTabs.length === 2
        ? "grid-cols-2"
        : "grid-cols-3";

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
                    color: "green" as TicketColor,
                    minutes: "",
                    comment: "",
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

                      {draft.selected ? (
                        <div className="mt-3 space-y-2">
                          <div className="grid grid-cols-3 gap-2">
                            {(["green", "yellow", "red"] as TicketColor[]).map((color) => (
                              <button
                                key={`${part.id}-${color}`}
                                type="button"
                                onClick={() => updatePartDraft(part.id, { color })}
                                className={cn(
                                  "rounded-lg border px-2 py-2 text-xs font-semibold",
                                  colorPickerButtonClass(color, draft.color === color),
                                )}
                              >
                                {colorLabel(color)}
                              </button>
                            ))}
                          </div>
                          <input
                            className="rm-input h-10"
                            type="number"
                            min={1}
                            value={draft.minutes}
                            onChange={(event) =>
                              updatePartDraft(part.id, { minutes: event.target.value })
                            }
                            placeholder={t("Minutes")}
                          />
                          <textarea
                            className="rm-input min-h-[80px] resize-y py-2"
                            value={draft.comment}
                            onChange={(event) =>
                              updatePartDraft(part.id, { comment: event.target.value })
                            }
                            placeholder={t("Comment")}
                          />
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-700">
                {t("No parts are configured for this item category.")}
              </p>
            )}

            <Button
              type="button"
              className="h-11 w-full"
              disabled={
                isCreatingTicket ||
                isLoadingParts ||
                !selectedCreateItem ||
                !selectedCreateParts.length
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
                    selectedQcTicketId === ticket.id
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-900",
                  )}
                >
                  <p className="text-sm font-semibold">#{ticket.id}</p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedQcTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {serial}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedQcTicketId === ticket.id ? "text-slate-200" : "text-slate-600",
                    )}
                  >
                    {statusLabel(ticket.status)}
                  </p>
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
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
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
              <p className="mt-1 text-xs text-slate-600">
                {
                  inventoryCache[selectedQcTicket.inventory_item]?.serial_number ??
                  t("Item #{{id}}", { id: selectedQcTicket.inventory_item })
                }
              </p>
            </div>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-white px-3 py-3">
              <p className="text-sm font-semibold text-slate-900">{t("Part specs")}</p>
              {selectedQcTicket.ticket_parts.length ? (
                selectedQcTicket.ticket_parts.map((part) => (
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

            {permissions.can_qc ? (
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
                    isRunningQcAction || selectedQcTicket.status !== "waiting_qc"
                  }
                >
                  {t("QC Fail")}
                </Button>
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

  return (
    <section className="space-y-3 pb-24">
      {feedback ? (
        <p
          className={cn(
            "rounded-xl border px-3 py-2 text-sm",
            feedback.type === "error"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : feedback.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-sky-200 bg-sky-50 text-sky-700",
          )}
        >
          {feedback.message}
        </p>
      ) : null}

      {!availableTabs.length ? (
        <section className="rm-panel p-4">
          <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 px-3 py-3">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-amber-800">
              <ShieldAlert className="h-4 w-4" />
              {t("No ticket permissions")}
            </p>
            <p className="mt-2 text-xs text-amber-700">
              {t("Your account does not have create/review/qc access.")}
            </p>
          </div>
        </section>
      ) : activeTab === "create" ? (
        renderCreateTab()
      ) : activeTab === "review" ? (
        renderReviewTab()
      ) : (
        renderQcTab()
      )}

      {availableTabs.length ? (
        <nav className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3">
          <div
            className={cn(
              "mx-auto grid max-w-md gap-2 rounded-2xl border border-white/80 bg-white/95 p-2 shadow-[0_16px_32px_-22px_rgba(15,23,42,0.55)] backdrop-blur",
              tabGridClass,
            )}
          >
            {availableTabs.map((tab) => {
              const Icon = TAB_META[tab].icon;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "rounded-xl px-3 py-2.5 text-xs font-semibold transition",
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
