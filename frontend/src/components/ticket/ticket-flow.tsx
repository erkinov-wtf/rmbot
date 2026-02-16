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
import {
  createTicket,
  getInventoryItem,
  listAllCategories,
  listInventoryItems,
  listParts,
  listTicketTransitions,
  listTickets,
  reviewTicketManualMetrics,
  type InventoryCategory,
  type InventoryItem,
  type InventoryItemStatus,
  type InventoryPart,
  type Ticket as TicketModel,
  type TicketColor,
  type TicketStatus,
  type TicketTransition,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type TicketFlowProps = {
  accessToken: string;
  canCreate: boolean;
  canReview: boolean;
  roleTitles: string[];
  roleSlugs: string[];
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
  | { name: "review" };

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

const DEFAULT_ITEM_FILTERS: ItemFilterState = {
  search: "",
  categoryId: "",
  status: "all",
  activity: "all",
};

const ITEM_STATUS_OPTIONS: Array<{ value: InventoryItemStatus; label: string }> = [
  { value: "ready", label: "Ready" },
  { value: "in_service", label: "In Service" },
  { value: "rented", label: "Rented" },
  { value: "blocked", label: "Blocked" },
  { value: "write_off", label: "Write Off" },
];

const TICKET_STATUS_OPTIONS: Array<{ value: TicketStatus; label: string }> = [
  { value: "under_review", label: "Under Review" },
  { value: "new", label: "New" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In Progress" },
  { value: "waiting_qc", label: "Waiting QC" },
  { value: "rework", label: "Rework" },
  { value: "done", label: "Done" },
];

const TICKET_COLOR_OPTIONS: Array<{ value: TicketColor; label: string }> = [
  { value: "green", label: "Green" },
  { value: "yellow", label: "Yellow" },
  { value: "red", label: "Red" },
];

const fieldClassName =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-100 disabled:cursor-not-allowed disabled:bg-slate-100";

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

function parseTicketRoute(pathname: string): TicketRoute {
  const createItemMatch = pathname.match(/^\/tickets\/create\/item\/(\d+)\/?$/);
  if (createItemMatch) {
    const parsedId = Number(createItemMatch[1]);
    if (Number.isFinite(parsedId) && parsedId > 0) {
      return { name: "createItem", itemId: parsedId };
    }
  }

  if (pathname.startsWith("/tickets/review")) {
    return { name: "review" };
  }

  if (pathname.startsWith("/tickets/create")) {
    return { name: "createList" };
  }

  return { name: "createList" };
}

function toTicketPath(route: TicketRoute): string {
  if (route.name === "review") {
    return "/tickets/review";
  }
  if (route.name === "createItem") {
    return `/tickets/create/item/${route.itemId}`;
  }
  return "/tickets/create";
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

export function TicketFlow({
  accessToken,
  canCreate,
  canReview,
  roleTitles,
  roleSlugs,
}: TicketFlowProps) {
  const [route, setRoute] = useState<TicketRoute>(() =>
    parseTicketRoute(window.location.pathname),
  );

  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [isMutating, setIsMutating] = useState(false);

  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);

  const [itemFilters, setItemFilters] = useState<ItemFilterState>(DEFAULT_ITEM_FILTERS);
  const [appliedItemFilters, setAppliedItemFilters] =
    useState<ItemFilterState>(DEFAULT_ITEM_FILTERS);
  const [createItems, setCreateItems] = useState<InventoryItem[]>([]);
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

  const [reviewTickets, setReviewTickets] = useState<TicketModel[]>([]);
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
  const [reviewFlagColor, setReviewFlagColor] = useState<TicketColor>("green");
  const [reviewXpAmount, setReviewXpAmount] = useState("");

  const [inventoryCache, setInventoryCache] = useState<Record<number, InventoryItem>>(
    {},
  );

  const activeMenu: "create" | "review" =
    route.name === "review" ? "review" : "create";

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const inventoryStatusLabelByValue = useMemo(
    () => new Map(ITEM_STATUS_OPTIONS.map((option) => [option.value, option.label])),
    [],
  );

  const ticketStatusLabelByValue = useMemo(
    () => new Map(TICKET_STATUS_OPTIONS.map((option) => [option.value, option.label])),
    [],
  );

  const ticketColorLabelByValue = useMemo(
    () => new Map(TICKET_COLOR_OPTIONS.map((option) => [option.value, option.label])),
    [],
  );

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

  const reviewTicketsFiltered = useMemo(() => {
    const normalized = reviewSearch.trim().toLowerCase();

    return reviewTickets.filter((ticket) => {
      if (reviewStatusFilter !== "all" && ticket.status !== reviewStatusFilter) {
        return false;
      }

      if (!normalized) {
        return true;
      }

      const item = inventoryCache[ticket.inventory_item];
      const serial = item?.serial_number ?? "";
      const name = item?.name ?? "";
      const title = ticket.title ?? "";

      return (
        String(ticket.id).includes(normalized) ||
        serial.toLowerCase().includes(normalized) ||
        name.toLowerCase().includes(normalized) ||
        title.toLowerCase().includes(normalized) ||
        ticket.status.toLowerCase().includes(normalized)
      );
    });
  }, [inventoryCache, reviewSearch, reviewStatusFilter, reviewTickets]);

  const selectedReviewTicket = useMemo(
    () =>
      reviewTicketsFiltered.find((ticket) => ticket.id === selectedReviewTicketId) ??
      null,
    [reviewTicketsFiltered, selectedReviewTicketId],
  );

  const navigate = useCallback((nextRoute: TicketRoute) => {
    const nextPath = toTicketPath(nextRoute);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setRoute(nextRoute);
    setFeedback(null);
  }, []);

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
          message: toErrorMessage(error, "Action failed."),
        });
        throw error;
      } finally {
        setIsMutating(false);
      }
    },
    [],
  );

  const loadCategories = useCallback(async () => {
    setIsLoadingCategories(true);
    try {
      const nextCategories = await listAllCategories(accessToken);
      setCategories(nextCategories);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, "Failed to load categories."),
      });
    } finally {
      setIsLoadingCategories(false);
    }
  }, [accessToken]);

  const loadCreateItems = useCallback(
    async (filters: ItemFilterState) => {
      setIsLoadingCreateItems(true);
      try {
        const search = filters.search.trim();
        const nextItems = await listInventoryItems(accessToken, {
          q: search.length >= 2 ? search : undefined,
          category: filters.categoryId ? Number(filters.categoryId) : undefined,
          status: filters.status === "all" ? undefined : filters.status,
          is_active:
            filters.activity === "all"
              ? undefined
              : filters.activity === "active",
        });

        setCreateItems(nextItems);
        cacheInventoryItems(nextItems);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, "Failed to load inventory items."),
        });
      } finally {
        setIsLoadingCreateItems(false);
      }
    },
    [accessToken, cacheInventoryItems],
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

        const itemParts = allParts.filter((part) => part.inventory_item === item.id);
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
          message: toErrorMessage(error, "Failed to load ticket creation context."),
        });
      } finally {
        setIsLoadingCreateItemPage(false);
      }
    },
    [accessToken, cacheInventoryItems],
  );

  const loadReviewTickets = useCallback(async () => {
    setIsLoadingReviewTickets(true);
    try {
      const nextTickets = await listTickets(accessToken, { per_page: 400 });
      setReviewTickets(nextTickets);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, "Failed to load tickets for review."),
      });
    } finally {
      setIsLoadingReviewTickets(false);
    }
  }, [accessToken]);

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
          message: toErrorMessage(error, "Failed to load ticket transitions."),
        });
      } finally {
        setIsLoadingReviewTransitions(false);
      }
    },
    [accessToken],
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

  useEffect(() => {
    const onPopState = () => {
      setRoute(parseTicketRoute(window.location.pathname));
      setFeedback(null);
    };

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, []);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    if (route.name !== "createList") {
      return;
    }
    void loadCreateItems(appliedItemFilters);
  }, [appliedItemFilters, loadCreateItems, route]);

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
    if (route.name !== "review") {
      setReviewTransitions([]);
      setReviewItem(null);
      return;
    }

    void loadReviewTickets();
  }, [loadReviewTickets, route]);

  useEffect(() => {
    if (route.name !== "review") {
      return;
    }

    if (!reviewTicketsFiltered.length) {
      setSelectedReviewTicketId(null);
      return;
    }

    if (
      selectedReviewTicketId === null ||
      !reviewTicketsFiltered.some((ticket) => ticket.id === selectedReviewTicketId)
    ) {
      setSelectedReviewTicketId(reviewTicketsFiltered[0].id);
    }
  }, [reviewTicketsFiltered, route, selectedReviewTicketId]);

  useEffect(() => {
    if (!selectedReviewTicket) {
      setReviewTransitions([]);
      setReviewItem(null);
      return;
    }

    setReviewFlagColor(selectedReviewTicket.flag_color);
    setReviewXpAmount(String(selectedReviewTicket.xp_amount));

    void loadReviewTransitions(selectedReviewTicket.id);
    void loadReviewItem(selectedReviewTicket.inventory_item);
  }, [loadReviewItem, loadReviewTransitions, selectedReviewTicket]);

  const handleRefresh = async () => {
    setFeedback(null);

    if (route.name === "createList") {
      await Promise.all([loadCategories(), loadCreateItems(appliedItemFilters)]);
      return;
    }

    if (route.name === "createItem") {
      await Promise.all([loadCategories(), loadCreateItemPage(route.itemId)]);
      return;
    }

    await Promise.all([loadCategories(), loadReviewTickets()]);
    if (selectedReviewTicket) {
      await Promise.all([
        loadReviewTransitions(selectedReviewTicket.id),
        loadReviewItem(selectedReviewTicket.inventory_item),
      ]);
    }
  };

  const handleApplyItemFilters = () => {
    const trimmed = itemFilters.search.trim();
    if (trimmed.length === 1) {
      setFeedback({
        type: "info",
        message:
          "Search query starts applying from 2 characters. Showing wider result set.",
      });
    } else {
      setFeedback(null);
    }

    setAppliedItemFilters(itemFilters);
  };

  const handleResetItemFilters = () => {
    setItemFilters(DEFAULT_ITEM_FILTERS);
    setAppliedItemFilters(DEFAULT_ITEM_FILTERS);
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
        message: "Selected inventory item has no parts. Add parts before ticket intake.",
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
        message: "Select at least one part to continue.",
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
          message: "Part form state is missing. Refresh and try again.",
        });
        return;
      }

      const parsedMinutes = Number(form.minutes);
      if (!Number.isInteger(parsedMinutes) || parsedMinutes < 1) {
        setFeedback({
          type: "error",
          message: `Minutes must be at least 1 for part \"${part.name}\".`,
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
      }, "Ticket created and sent to UNDER_REVIEW.");
    } catch {
      // feedback already set
    }
  };

  const handleReviewApprove = async () => {
    if (!canReview || !selectedReviewTicket) {
      return;
    }

    const parsedXp = Number(reviewXpAmount);
    if (!Number.isInteger(parsedXp) || parsedXp < 0) {
      setFeedback({
        type: "error",
        message: "XP must be an integer greater than or equal to 0.",
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
      }, "Ticket review updated by admin.");
    } catch {
      // feedback already set
    }
  };

  const renderCreateListPage = () => {
    const oneCharSearch = itemFilters.search.trim().length === 1;

    return (
      <div className="mt-4 space-y-4">
        <section className="rounded-lg border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-900">Create Ticket</p>
          <p className="mt-1 text-sm text-slate-600">
            Pick an inventory item first. The next page shows ticket history for that
            item and the new-ticket intake form.
          </p>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_1fr_auto]">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Search
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
                  placeholder="Serial number search"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Category
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
                <option value="">All categories</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Status
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
                <option value="all">All statuses</option>
                {ITEM_STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Active
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
                <option value="all">All</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>

            <div className="flex items-end gap-2">
              <Button
                type="button"
                className="h-10"
                onClick={handleApplyItemFilters}
                disabled={isLoadingCreateItems || !hasPendingItemFilterChanges}
              >
                Apply
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={handleResetItemFilters}
                disabled={isLoadingCreateItems}
              >
                Reset
              </Button>
            </div>
          </div>

          {oneCharSearch ? (
            <p className="mt-2 text-xs text-amber-700">
              Backend search starts at 2 characters.
            </p>
          ) : null}
        </section>

        <section className="rounded-lg border border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">
              Inventory Items ({createItems.length})
            </p>
            <p className="text-xs text-slate-500">Select item to continue</p>
          </div>

          {isLoadingCreateItems ? (
            <p className="px-4 py-6 text-sm text-slate-600">Loading items...</p>
          ) : !createItems.length ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">
              No items found.
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
                      Category: {categoryNameById.get(item.category) ?? `#${item.category}`}
                    </p>
                  </button>
                ))}
              </div>

              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Serial
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Category
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Status
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Action
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
                            Select
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    );
  };

  const renderCreateItemPage = () => {
    if (isLoadingCreateItemPage) {
      return (
        <section className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="text-sm text-slate-600">Loading ticket intake page...</p>
        </section>
      );
    }

    if (!selectedItem) {
      return (
        <section className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center">
          <p className="text-sm text-slate-600">Inventory item not found.</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3 h-10"
            onClick={() => navigate({ name: "createList" })}
          >
            Back to Item List
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
          Back to item selection
        </button>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-lg font-semibold text-slate-900">{selectedItem.serial_number}</p>
          <p className="mt-1 text-sm text-slate-700">{selectedItem.name || "Unnamed item"}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
            <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
              Category: {categoryNameById.get(selectedItem.category) ?? `#${selectedItem.category}`}
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
              Previous Ticket History ({selectedItemTicketHistory.length})
            </p>

            {selectedItemTicketHistory.length ? (
              <div className="mt-3 space-y-2">
                {selectedItemTicketHistory.map((ticket) => (
                  <div
                    key={ticket.id}
                    className="rounded-md border border-slate-200 bg-white p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">Ticket #{ticket.id}</p>
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
                      Created: {formatDate(ticket.created_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Total Minutes: {ticket.total_duration} | Flag: {ticketColorLabelByValue.get(ticket.flag_color) ?? ticket.flag_color}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
                No previous tickets for this item.
              </p>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <FilePlus2 className="h-4 w-4" />
              New Ticket Intake
            </p>
            <p className="mt-1 text-xs text-slate-600">Select at least one part.</p>

            <form onSubmit={handleCreateTicket} className="mt-3 space-y-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Title (optional)
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={ticketTitle}
                  onChange={(event) => setTicketTitle(event.target.value)}
                  disabled={!canCreate || isMutating}
                  placeholder="Ticket title"
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
                          <p className="text-xs text-slate-500">Part ID: {part.id}</p>
                        </div>

                        <div className="mt-3 grid gap-2 md:grid-cols-3">
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              Color
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
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              Minutes
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
                              placeholder="e.g. 20"
                            />
                          </div>

                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                              Comment (optional)
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
                              placeholder="Part note"
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="rounded-md border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-600">
                  This item has no parts. Add parts in inventory management before ticket
                  intake.
                </p>
              )}

              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                Selected parts: {selectedPartsCount}/{selectedItemParts.length || 0}
              </div>

              {!canCreate ? (
                <p className="text-xs text-amber-700">
                  Your roles do not allow ticket creation.
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
                  Create Ticket
                </Button>
                {canReview ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10"
                    onClick={() => navigate({ name: "review" })}
                  >
                    Open Review Queue
                  </Button>
                ) : null}
              </div>
            </form>
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
          Review Queue
        </p>

        <div className="mt-3 space-y-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Search
            </label>
            <div className="relative mt-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className={cn(fieldClassName, "pl-9")}
                value={reviewSearch}
                onChange={(event) => setReviewSearch(event.target.value)}
                placeholder="Ticket id, serial, title"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
              Status
            </label>
            <select
              className={cn(fieldClassName, "mt-1")}
              value={reviewStatusFilter}
              onChange={(event) =>
                setReviewStatusFilter(event.target.value as "all" | TicketStatus)
              }
            >
              <option value="all">All statuses</option>
              {TICKET_STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {isLoadingReviewTickets ? (
          <p className="mt-3 text-sm text-slate-600">Loading tickets...</p>
        ) : reviewTicketsFiltered.length ? (
          <div className="mt-3 space-y-2">
            {reviewTicketsFiltered.map((ticket) => {
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
                  <p className="text-sm font-semibold">Ticket #{ticket.id}</p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id
                        ? "text-slate-200"
                        : "text-slate-600",
                    )}
                  >
                    {item?.serial_number ?? `Item #${ticket.inventory_item}`}
                  </p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      selectedReviewTicketId === ticket.id
                        ? "text-slate-200"
                        : "text-slate-600",
                    )}
                  >
                    {ticket.title || "No title"}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
            No tickets in review queue.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 p-4">
        {selectedReviewTicket ? (
          <div className="space-y-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold text-slate-900">
                  Ticket #{selectedReviewTicket.id}
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
                {selectedReviewTicket.title || "No title"}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Item: {reviewItem?.serial_number ?? `#${selectedReviewTicket.inventory_item}`}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Created: {formatDate(selectedReviewTicket.created_at)}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Auto/Current Minutes: {selectedReviewTicket.total_duration}
              </p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-900">Part Specs</p>

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
                        <p className="mt-1 text-xs text-slate-600">Minutes: {part.minutes}</p>
                        <p className="mt-1 text-xs text-slate-600">
                          Comment: {part.comment || "-"}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-600">No part specs.</p>
                )}
              </div>

              <div className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-900">Review Action</p>
                <p className="mt-1 text-xs text-slate-600">
                  Admin review uses backend manual metrics endpoint.
                </p>

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                      Flag Color
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
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                      XP Amount
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

                {!canReview ? (
                  <p className="mt-2 text-xs text-amber-700">
                    Your roles do not allow ticket review.
                  </p>
                ) : null}

                <div className="mt-3">
                  <Button
                    type="button"
                    className="h-10"
                    onClick={() => void handleReviewApprove()}
                    disabled={!canReview || isMutating}
                  >
                    Apply Review
                  </Button>
                </div>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 p-3">
              <p className="text-sm font-semibold text-slate-900">Ticket Transitions</p>

              {isLoadingReviewTransitions ? (
                <p className="mt-2 text-sm text-slate-600">Loading transitions...</p>
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
                <p className="mt-2 text-sm text-slate-600">No transitions yet.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-500">
            Select a ticket from the queue.
          </p>
        )}
      </section>
    </div>
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Ticket Flow</h2>
          <p className="mt-1 text-sm text-slate-600">
            Ticket intake by item with full part specs, followed by admin review.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {roleTitles.length ? (
              roleTitles.map((roleTitle) => (
                <span
                  key={roleTitle}
                  className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs text-slate-700"
                >
                  {roleTitle}
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-500">No role titles</span>
            )}
          </div>
          {!canCreate ? (
            <p className="mt-2 text-xs text-amber-700">
              Roles ({roleSlugs.join(", ") || "none"}) cannot create tickets.
            </p>
          ) : null}
          {!canReview ? (
            <p className="mt-1 text-xs text-amber-700">
              Roles ({roleSlugs.join(", ") || "none"}) cannot perform admin review.
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
            isLoadingReviewTickets ||
            isLoadingReviewTransitions
          }
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {feedback ? (
        <p
          className={cn(
            "mt-4 rounded-md border px-3 py-2 text-sm",
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

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => navigate({ name: "createList" })}
          className={cn(
            "rounded-md border px-3 py-2 text-sm font-medium transition",
            activeMenu === "create"
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
          )}
        >
          <span className="inline-flex items-center gap-2">
            <Ticket className="h-4 w-4" />
            Create Ticket
          </span>
        </button>

        <button
          type="button"
          onClick={() => navigate({ name: "review" })}
          className={cn(
            "rounded-md border px-3 py-2 text-sm font-medium transition",
            activeMenu === "review"
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
          )}
        >
          <span className="inline-flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4" />
            Review Tickets
          </span>
        </button>
      </div>

      {route.name === "createList" ? renderCreateListPage() : null}
      {route.name === "createItem" ? renderCreateItemPage() : null}
      {route.name === "review" ? renderReviewPage() : null}
    </section>
  );
}
