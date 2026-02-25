import {
  ArrowLeft,
  Download,
  FolderTree,
  Package,
  PencilLine,
  Plus,
  RefreshCcw,
  Search,
  Trash2,
  Upload,
  Wrench,
} from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { useI18n } from "@/i18n";
import {
  createCategory,
  createInventoryItem,
  createPart,
  deleteCategory,
  deleteInventoryItem,
  deletePart,
  exportInventoryWorkbookFile,
  getInventoryItem,
  importInventoryWorkbook,
  listAllCategories,
  listInventoryItemsPage,
  listParts,
  type InventoryCategory,
  type InventoryItem,
  type InventoryItemStatus,
  type InventoryPart,
  type PaginationMeta,
  updateCategory,
  updateInventoryItem,
  updatePart,
} from "@/lib/api";
import {
  buildInventorySerialSearchQuery,
  normalizeInventorySerialSearchQuery,
} from "@/lib/inventory-search";
import { cn } from "@/lib/utils";

type InventoryAdminProps = {
  accessToken: string;
  canManage: boolean;
  roleSlugs: string[];
};

type FeedbackState =
  | {
      type: "success" | "error" | "info";
      message: string;
    }
  | null;

type InventoryRoute =
  | { name: "categories" }
  | { name: "items" }
  | { name: "itemDetail"; itemId: number };

type ItemFilters = {
  search: string;
  categoryId: string;
  status: "all" | InventoryItemStatus;
  activity: "all" | "active" | "inactive";
};

type ItemFormState = {
  serialNumber: string;
  name: string;
  categoryId: string;
  status: InventoryItemStatus;
  isActive: boolean;
};

const DEFAULT_ITEM_FILTERS: ItemFilters = {
  search: "",
  categoryId: "",
  status: "all",
  activity: "all",
};

const DEFAULT_ITEM_FORM: ItemFormState = {
  serialNumber: "",
  name: "",
  categoryId: "",
  status: "ready",
  isActive: true,
};

const ITEM_STATUS_OPTIONS: InventoryItemStatus[] = [
  "ready",
  "in_service",
  "rented",
  "blocked",
  "write_off",
];

const ITEM_PER_PAGE_OPTIONS = [10, 20, 50];
const DEFAULT_ITEM_PER_PAGE = 20;

const fieldClassName = "rm-input";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function statusBadgeClass(status: InventoryItemStatus): string {
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

function statusLabel(
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

function parseInventoryRoute(pathname: string): InventoryRoute {
  const detailMatch = pathname.match(/^\/inventory\/items\/(\d+)\/?$/);
  if (detailMatch) {
    const parsedId = Number(detailMatch[1]);
    if (Number.isFinite(parsedId) && parsedId > 0) {
      return { name: "itemDetail", itemId: parsedId };
    }
  }

  if (pathname.startsWith("/inventory/categories")) {
    return { name: "categories" };
  }

  if (pathname.startsWith("/inventory/items")) {
    return { name: "items" };
  }

  return { name: "items" };
}

function toInventoryPath(route: InventoryRoute): string {
  if (route.name === "categories") {
    return "/inventory/categories";
  }
  if (route.name === "itemDetail") {
    return `/inventory/items/${route.itemId}`;
  }
  return "/inventory/items";
}

function areFiltersEqual(left: ItemFilters, right: ItemFilters): boolean {
  return (
    left.search === right.search &&
    left.categoryId === right.categoryId &&
    left.status === right.status &&
    left.activity === right.activity
  );
}

export function InventoryAdmin({
  accessToken,
  canManage,
  roleSlugs,
}: InventoryAdminProps) {
  const { t } = useI18n();
  const [route, setRoute] = useState<InventoryRoute>(() =>
    parseInventoryRoute(window.location.pathname),
  );

  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [allParts, setAllParts] = useState<InventoryPart[]>([]);
  const [itemPage, setItemPage] = useState(1);
  const [itemPerPage, setItemPerPage] = useState(DEFAULT_ITEM_PER_PAGE);
  const [itemPagination, setItemPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_ITEM_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });

  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [isLoadingItems, setIsLoadingItems] = useState(true);
  const [isLoadingParts, setIsLoadingParts] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const [itemFilters, setItemFilters] = useState<ItemFilters>(DEFAULT_ITEM_FILTERS);
  const [appliedFilters, setAppliedFilters] =
    useState<ItemFilters>(DEFAULT_ITEM_FILTERS);

  const [isCreateItemOpen, setIsCreateItemOpen] = useState(false);
  const [createItemForm, setCreateItemForm] =
    useState<ItemFormState>(DEFAULT_ITEM_FORM);

  const [categoryName, setCategoryName] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [partCategoryId, setPartCategoryId] = useState("");

  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null);
  const [detailItemForm, setDetailItemForm] = useState<ItemFormState | null>(null);
  const [detailParts, setDetailParts] = useState<InventoryPart[]>([]);

  const [partName, setPartName] = useState("");
  const [editingPartId, setEditingPartId] = useState<number | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);

  const activeMenu: "categories" | "items" =
    route.name === "categories" ? "categories" : "items";

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const statusLabelByValue = useMemo(
    () =>
      new Map(ITEM_STATUS_OPTIONS.map((option) => [option, statusLabel(option, t)])),
    [t],
  );

  const categoryParts = useMemo(() => {
    const parsedCategoryId = Number(partCategoryId);
    if (!parsedCategoryId) {
      return [];
    }
    return allParts.filter((part) => part.category === parsedCategoryId);
  }, [allParts, partCategoryId]);

  const partCountByCategory = useMemo(() => {
    const counts = new Map<number, number>();
    allParts.forEach((part) => {
      if (!part.category) {
        return;
      }
      counts.set(part.category, (counts.get(part.category) ?? 0) + 1);
    });
    return counts;
  }, [allParts]);

  const selectedPartCategory = useMemo(
    () => categories.find((category) => String(category.id) === partCategoryId) ?? null,
    [categories, partCategoryId],
  );

  const hasPendingFilterChanges = useMemo(
    () => !areFiltersEqual(itemFilters, appliedFilters),
    [itemFilters, appliedFilters],
  );

  const navigate = useCallback((nextRoute: InventoryRoute) => {
    const nextPath = toInventoryPath(nextRoute);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setRoute(nextRoute);
    setFeedback(null);
  }, []);

  const resetCategoryForm = () => {
    setCategoryName("");
    setEditingCategoryId(null);
  };

  const resetPartForm = () => {
    setPartName("");
    setEditingPartId(null);
  };

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

  const loadParts = useCallback(async () => {
    setIsLoadingParts(true);
    try {
      const nextParts = await listParts(accessToken);
      setAllParts(nextParts);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load category parts.")),
      });
    } finally {
      setIsLoadingParts(false);
    }
  }, [accessToken, t]);

  const loadItems = useCallback(
    async (filters: ItemFilters, page: number, perPage: number) => {
      setIsLoadingItems(true);
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
          setItemPage(paginated.pagination.page_count);
          return;
        }
        setItems(paginated.results);
        setItemPagination(paginated.pagination);
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load inventory items.")),
        });
      } finally {
        setIsLoadingItems(false);
      }
    },
    [accessToken, t],
  );

  const loadItemDetail = useCallback(
    async (itemId: number) => {
      setIsLoadingDetail(true);
      try {
        const item = await getInventoryItem(accessToken, itemId);

        setDetailItem(item);
        setDetailItemForm({
          serialNumber: item.serial_number,
          name: item.name ?? "",
          categoryId: String(item.category),
          status: item.status,
          isActive: item.is_active,
        });

        let partRows = allParts;
        if (!partRows.length) {
          partRows = await listParts(accessToken);
          setAllParts(partRows);
        }

        setDetailParts(partRows.filter((part) => part.category === item.category));
        resetPartForm();
      } catch (error) {
        setDetailItem(null);
        setDetailItemForm(null);
        setDetailParts([]);
        setFeedback({
          type: "error",
          message: toErrorMessage(error, t("Failed to load inventory item details.")),
        });
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [accessToken, allParts, t],
  );

  useEffect(() => {
    const onPopState = () => {
      setRoute(parseInventoryRoute(window.location.pathname));
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
    void loadParts();
  }, [loadParts]);

  useEffect(() => {
    void loadItems(appliedFilters, itemPage, itemPerPage);
  }, [appliedFilters, itemPage, itemPerPage, loadItems]);

  useEffect(() => {
    if (itemFilters.search === appliedFilters.search) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setItemPage(1);
      setAppliedFilters((prev) => ({
        ...prev,
        search: itemFilters.search,
      }));
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [appliedFilters.search, itemFilters.search]);

  useEffect(() => {
    if (route.name !== "itemDetail") {
      setDetailItem(null);
      setDetailItemForm(null);
      setDetailParts([]);
      resetPartForm();
      return;
    }

    void loadItemDetail(route.itemId);
  }, [route, loadItemDetail]);

  useEffect(() => {
    if (!categories.length) {
      setCreateItemForm((prev) => ({ ...prev, categoryId: "" }));
      setPartCategoryId("");
      return;
    }

    setCreateItemForm((prev) => {
      if (prev.categoryId) {
        return prev;
      }
      return {
        ...prev,
        categoryId: String(categories[0].id),
      };
    });

    setPartCategoryId((prev) => {
      if (prev && categories.some((category) => String(category.id) === prev)) {
        return prev;
      }
      return String(categories[0].id);
    });
  }, [categories]);

  useEffect(() => {
    if (!detailItemForm || !categories.length) {
      return;
    }

    const stillExists = categories.some(
      (category) => String(category.id) === detailItemForm.categoryId,
    );
    if (!stillExists) {
      setDetailItemForm((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          categoryId: String(categories[0].id),
        };
      });
    }
  }, [categories, detailItemForm]);

  useEffect(() => {
    if (!detailItem) {
      setDetailParts([]);
      return;
    }
    setDetailParts(allParts.filter((part) => part.category === detailItem.category));
  }, [allParts, detailItem]);

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

  const handleRefresh = async () => {
    setFeedback(null);
    await Promise.all([
      loadCategories(),
      loadItems(appliedFilters, itemPage, itemPerPage),
      loadParts(),
    ]);
    if (route.name === "itemDetail") {
      await loadItemDetail(route.itemId);
    }
  };

  const handleExport = async () => {
    setFeedback(null);
    setIsExporting(true);
    try {
      const { blob, fileName } = await exportInventoryWorkbookFile(accessToken);
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to export inventory workbook.")),
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";

    if (!selectedFile || !canManage) {
      return;
    }

    setFeedback(null);
    setIsImporting(true);
    try {
      const summary = await importInventoryWorkbook(accessToken, selectedFile);
      await Promise.all([
        loadCategories(),
        loadItems(appliedFilters, itemPage, itemPerPage),
        loadParts(),
      ]);
      if (route.name === "itemDetail") {
        await loadItemDetail(route.itemId);
      }
      setFeedback({
        type: "success",
        message: t(
          "Import completed. Created: categories {{categoriesCreated}}, parts {{partsCreated}}, items {{itemsCreated}}. Updated: categories {{categoriesUpdated}}, parts {{partsUpdated}}, items {{itemsUpdated}}.",
          {
            categoriesCreated: summary.categories_created,
            partsCreated: summary.parts_created,
            itemsCreated: summary.items_created,
            categoriesUpdated: summary.categories_updated,
            partsUpdated: summary.parts_updated,
            itemsUpdated: summary.items_updated,
          },
        ),
      });
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to import inventory workbook.")),
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleApplyFilters = () => {
    const normalizedSearch = normalizeInventorySerialSearchQuery(itemFilters.search);
    if (normalizedSearch.length === 1) {
      setFeedback({
        type: "info",
        message: t("Search query starts applying from 2 characters. Showing wider result set."),
      });
    } else {
      setFeedback(null);
    }

    setItemPage(1);
    setAppliedFilters(itemFilters);
  };

  const handleResetFilters = () => {
    setItemFilters(DEFAULT_ITEM_FILTERS);
    setAppliedFilters(DEFAULT_ITEM_FILTERS);
    setItemPage(1);
    setFeedback(null);
  };

  const handleCategorySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const trimmedName = categoryName.trim();
    if (!trimmedName) {
      setFeedback({ type: "error", message: t("Category name is required.") });
      return;
    }

    try {
      await runMutation(async () => {
        if (editingCategoryId) {
          await updateCategory(accessToken, editingCategoryId, trimmedName);
        } else {
          await createCategory(accessToken, trimmedName);
        }

        resetCategoryForm();
        await Promise.all([
          loadCategories(),
          loadItems(appliedFilters, itemPage, itemPerPage),
        ]);
      }, editingCategoryId ? t("Category updated.") : t("Category created."));
    } catch {
      // feedback already set
    }
  };

  const handleCategoryDelete = async (categoryId: number) => {
    if (!canManage || !window.confirm(t("Delete this category?"))) {
      return;
    }

    try {
      await runMutation(async () => {
        await deleteCategory(accessToken, categoryId);
        if (editingCategoryId === categoryId) {
          resetCategoryForm();
        }
        if (partCategoryId === String(categoryId)) {
          resetPartForm();
        }
        await Promise.all([
          loadCategories(),
          loadItems(appliedFilters, itemPage, itemPerPage),
          loadParts(),
        ]);
      }, t("Category deleted."));
    } catch {
      // feedback already set
    }
  };

  const handleCreateItemSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const serialNumber = createItemForm.serialNumber.trim();
    if (!serialNumber) {
      setFeedback({ type: "error", message: t("Serial number is required.") });
      return;
    }

    const categoryId = Number(createItemForm.categoryId);
    if (!categoryId) {
      setFeedback({ type: "error", message: t("Select a category.") });
      return;
    }

    try {
      await runMutation(async () => {
        const created = await createInventoryItem(accessToken, {
          serial_number: serialNumber,
          name: createItemForm.name.trim() || undefined,
          category: categoryId,
          status: createItemForm.status,
          is_active: createItemForm.isActive,
        });

        setCreateItemForm((prev) => ({
          ...prev,
          serialNumber: "",
          name: "",
          status: "ready",
          isActive: true,
        }));
        setIsCreateItemOpen(false);

        await loadItems(appliedFilters, itemPage, itemPerPage);
        navigate({ name: "itemDetail", itemId: created.id });
      }, t("Inventory item created."));
    } catch {
      // feedback already set
    }
  };

  const handleDetailItemSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage || !detailItem || !detailItemForm) {
      return;
    }

    const serialNumber = detailItemForm.serialNumber.trim();
    if (!serialNumber) {
      setFeedback({ type: "error", message: t("Serial number is required.") });
      return;
    }

    const categoryId = Number(detailItemForm.categoryId);
    if (!categoryId) {
      setFeedback({ type: "error", message: t("Select a category.") });
      return;
    }

    try {
      await runMutation(async () => {
        const updated = await updateInventoryItem(accessToken, detailItem.id, {
          serial_number: serialNumber,
          name: detailItemForm.name.trim(),
          category: categoryId,
          status: detailItemForm.status,
          is_active: detailItemForm.isActive,
        });

        setDetailItem(updated);
        setDetailItemForm({
          serialNumber: updated.serial_number,
          name: updated.name ?? "",
          categoryId: String(updated.category),
          status: updated.status,
          isActive: updated.is_active,
        });

        await loadItems(appliedFilters, itemPage, itemPerPage);
      }, t("Inventory item updated."));
    } catch {
      // feedback already set
    }
  };

  const handleDetailItemDelete = async () => {
    if (
      !canManage ||
      !detailItem ||
      !window.confirm(t("Delete this inventory item?"))
    ) {
      return;
    }

    try {
      await runMutation(async () => {
        await deleteInventoryItem(accessToken, detailItem.id);
        setDetailItem(null);
        setDetailItemForm(null);
        setDetailParts([]);
        resetPartForm();

        await loadItems(appliedFilters, itemPage, itemPerPage);
        navigate({ name: "items" });
      }, t("Inventory item deleted."));
    } catch {
      // feedback already set
    }
  };

  const handlePartSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const selectedPartCategoryId = Number(partCategoryId);
    if (!selectedPartCategoryId) {
      setFeedback({ type: "error", message: t("Select a category for part management.") });
      return;
    }

    const trimmedPartName = partName.trim();
    if (!trimmedPartName) {
      setFeedback({ type: "error", message: t("Part name is required.") });
      return;
    }

    try {
      await runMutation(async () => {
        if (editingPartId) {
          await updatePart(accessToken, editingPartId, {
            category: selectedPartCategoryId,
            name: trimmedPartName,
          });
        } else {
          await createPart(accessToken, {
            category: selectedPartCategoryId,
            name: trimmedPartName,
          });
        }

        await loadParts();
        resetPartForm();
      }, editingPartId ? t("Part updated.") : t("Part created."));
    } catch {
      // feedback already set
    }
  };

  const handlePartDelete = async (partId: number) => {
    if (!canManage || !window.confirm(t("Delete this part?"))) {
      return;
    }

    try {
      await runMutation(async () => {
        await deletePart(accessToken, partId);
        await loadParts();
        if (editingPartId === partId) {
          resetPartForm();
        }
      }, t("Part deleted."));
    } catch {
      // feedback already set
    }
  };

  const renderCategoryPage = () => (
    <div className="mt-4 grid gap-4 xl:grid-cols-[340px_1fr_1fr]">
      <form onSubmit={handleCategorySubmit} className="rounded-lg border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-900">
          {editingCategoryId ? t("Edit Category") : t("Create Category")}
        </p>

        <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-600">
          {t("Category Name")}
        </label>
        <input
          className={cn(fieldClassName, "mt-1")}
          value={categoryName}
          onChange={(event) => setCategoryName(event.target.value)}
          disabled={!canManage || isMutating}
          placeholder={t("Enter category name")}
        />

        {canManage ? (
          <div className="mt-3 flex gap-2">
            <Button type="submit" className="h-10" disabled={isMutating}>
              {editingCategoryId ? t("Update") : t("Create")}
            </Button>
            {editingCategoryId ? (
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={resetCategoryForm}
                disabled={isMutating}
              >
                {t("Cancel")}
              </Button>
            ) : null}
          </div>
        ) : null}
      </form>

      <div className="rounded-lg border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-900">
          {t("Categories ({{count}})", { count: categories.length })}
        </p>

        {isLoadingCategories ? (
          <p className="mt-4 text-sm text-slate-600">{t("Loading categories...")}</p>
        ) : categories.length ? (
          <div className="mt-3 space-y-2">
            {categories.map((category) => (
              <div
                key={category.id}
                className="flex flex-col gap-2 rounded-md border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">{category.name}</p>
                  <p className="text-xs text-slate-500">{formatDate(category.created_at)}</p>
                </div>

                {canManage ? (
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2 text-xs"
                      onClick={() => {
                        setCategoryName(category.name);
                        setEditingCategoryId(category.id);
                      }}
                      disabled={isMutating}
                    >
                      <PencilLine className="mr-1 h-3.5 w-3.5" />
                      {t("Edit")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2 text-xs text-rose-700"
                      onClick={() => void handleCategoryDelete(category.id)}
                      disabled={isMutating}
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      {t("Delete")}
                    </Button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
            {t("No categories yet.")}
          </p>
        )}
      </div>

      <section className="rounded-lg border border-slate-200 p-4">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Package className="h-4 w-4" />
          {t("Category Parts")}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {t("Parts are shared by all inventory items inside the selected category.")}
        </p>

        <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-600">
          {t("Category")}
        </label>
        <select
          className={cn(fieldClassName, "mt-1")}
          value={partCategoryId}
          onChange={(event) => {
            setPartCategoryId(event.target.value);
            resetPartForm();
          }}
          disabled={!categories.length || isMutating}
        >
          <option value="">{t("Select category")}</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>

        <form
          onSubmit={handlePartSubmit}
          className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3"
        >
          <p className="text-sm font-semibold text-slate-800">
            {editingPartId ? t("Edit Part") : t("Add Part")}
          </p>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              className={fieldClassName}
              value={partName}
              onChange={(event) => setPartName(event.target.value)}
              placeholder={t("Part name")}
              disabled={!canManage || isMutating || !partCategoryId}
            />
            {canManage ? (
              <div className="flex gap-2">
                <Button
                  type="submit"
                  className="h-10"
                  disabled={isMutating || !partCategoryId}
                >
                  {editingPartId ? t("Update") : t("Add")}
                </Button>
                {editingPartId ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10"
                    onClick={resetPartForm}
                    disabled={isMutating}
                  >
                    {t("Cancel")}
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        </form>

        <div className="mt-3 space-y-2">
          {isLoadingParts ? (
            <p className="text-sm text-slate-600">{t("Loading parts...")}</p>
          ) : categoryParts.length ? (
            categoryParts.map((part) => (
              <div
                key={part.id}
                className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">{part.name}</p>
                  <p className="text-xs text-slate-500">{formatDate(part.updated_at)}</p>
                </div>

                {canManage ? (
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2 text-xs"
                      onClick={() => {
                        setPartName(part.name);
                        setEditingPartId(part.id);
                        setPartCategoryId(String(part.category));
                      }}
                      disabled={isMutating}
                    >
                      <PencilLine className="mr-1 h-3.5 w-3.5" />
                      {t("Edit")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-2 text-xs text-rose-700"
                      onClick={() => void handlePartDelete(part.id)}
                      disabled={isMutating}
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" />
                      {t("Delete")}
                    </Button>
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <p className="rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
              {t("No parts for this category.")}
            </p>
          )}
        </div>
      </section>
    </div>
  );

  const renderItemsListPage = () => {
    const oneCharSearch =
      normalizeInventorySerialSearchQuery(itemFilters.search).length === 1;

    return (
      <div className="mt-4 space-y-4">
        <section className="rounded-lg border border-slate-200 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900">{t("Inventory Items")}</p>
              <p className="text-sm text-slate-600">
                {t(
                  "Full-screen list view with top filters. Open any item for details and inherited category parts.",
                )}
              </p>
            </div>

            {canManage ? (
              <Button
                type="button"
                variant={isCreateItemOpen ? "outline" : "default"}
                className="h-10 w-full sm:w-auto"
                onClick={() => setIsCreateItemOpen((prev) => !prev)}
                disabled={isMutating || isLoadingCategories}
              >
                <Plus className="mr-2 h-4 w-4" />
                {isCreateItemOpen ? t("Close Create") : t("Create Item")}
              </Button>
            ) : null}
          </div>

          {isCreateItemOpen && canManage ? (
            <form
              onSubmit={handleCreateItemSubmit}
              className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <p className="text-sm font-semibold text-slate-800">{t("Create Inventory Item")}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Serial Number")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    value={createItemForm.serialNumber}
                    onChange={(event) =>
                      setCreateItemForm((prev) => ({
                        ...prev,
                        serialNumber: event.target.value,
                      }))
                    }
                    disabled={isMutating}
                    placeholder={t("Enter serial number")}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Name")}
                  </label>
                  <input
                    className={cn(fieldClassName, "mt-1")}
                    value={createItemForm.name}
                    onChange={(event) =>
                      setCreateItemForm((prev) => ({
                        ...prev,
                        name: event.target.value,
                      }))
                    }
                    disabled={isMutating}
                    placeholder={t("Display name")}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Category")}
                  </label>
                  <select
                    className={cn(fieldClassName, "mt-1")}
                    value={createItemForm.categoryId}
                    onChange={(event) =>
                      setCreateItemForm((prev) => ({
                        ...prev,
                        categoryId: event.target.value,
                      }))
                    }
                    disabled={isMutating || !categories.length}
                  >
                    <option value="">{t("Select category")}</option>
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
                    value={createItemForm.status}
                    onChange={(event) =>
                      setCreateItemForm((prev) => ({
                        ...prev,
                        status: event.target.value as InventoryItemStatus,
                      }))
                    }
                    disabled={isMutating}
                  >
                    {ITEM_STATUS_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {statusLabel(option, t)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Active")}
                  </label>
                  <label className="mt-1 inline-flex h-10 w-full items-center rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={createItemForm.isActive}
                      onChange={(event) =>
                        setCreateItemForm((prev) => ({
                          ...prev,
                          isActive: event.target.checked,
                        }))
                      }
                      disabled={isMutating}
                    />
                    <span className="ml-2">{t("Active item")}</span>
                  </label>
                </div>
              </div>

              <div className="mt-3 flex gap-2">
                <Button
                  type="submit"
                  className="h-10"
                  disabled={isMutating || !categories.length}
                >
                  {t("Create Item")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10"
                  onClick={() => setIsCreateItemOpen(false)}
                  disabled={isMutating}
                >
                  {t("Cancel")}
                </Button>
              </div>
            </form>
          ) : null}

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
                    handleApplyFilters();
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
                    status: event.target.value as ItemFilters["status"],
                  }))
                }
              >
                <option value="all">{t("All statuses")}</option>
                {ITEM_STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {statusLabel(option, t)}
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
                    activity: event.target.value as ItemFilters["activity"],
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
                onClick={handleApplyFilters}
                disabled={isLoadingItems || !hasPendingFilterChanges}
              >
                {t("Apply")}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={handleResetFilters}
                disabled={isLoadingItems}
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
              {t("Results ({{count}})", { count: itemPagination.total_count })}
            </p>
            <p className="text-xs text-slate-500">{t("Click any row to open details")}</p>
          </div>

          {isLoadingItems ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t("Loading inventory items...")}</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">
              {t("No inventory items found for selected filters.")}
            </p>
          ) : (
            <>
              <div className="space-y-2 p-3 md:hidden">
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="w-full rounded-md border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-300"
                    onClick={() => navigate({ name: "itemDetail", itemId: item.id })}
                  >
                    <p className="text-sm font-semibold text-slate-900">{item.serial_number}</p>
                    <p className="text-sm text-slate-700">{item.name || "-"}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {t("Category")}: {categoryNameById.get(item.category) ?? `#${item.category}`}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-xs font-medium",
                          statusBadgeClass(item.status),
                        )}
                      >
                        {statusLabelByValue.get(item.status) ?? item.status}
                      </span>
                      <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-xs text-slate-600">
                        {item.is_active ? t("Active") : t("Inactive")}
                      </span>
                    </div>
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
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Active")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Updated")}
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t("Action")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {items.map((item) => (
                      <tr
                        key={item.id}
                        className="cursor-pointer transition hover:bg-slate-50"
                        onClick={() => navigate({ name: "itemDetail", itemId: item.id })}
                      >
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
                              statusBadgeClass(item.status),
                            )}
                          >
                            {statusLabelByValue.get(item.status) ?? item.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700">
                          {item.is_active ? t("Yes") : t("No")}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-500">
                          {formatDate(item.updated_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8"
                            onClick={(event) => {
                              event.stopPropagation();
                              navigate({ name: "itemDetail", itemId: item.id });
                            }}
                          >
                            {t("Open")}
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
            page={itemPagination.page}
            pageCount={itemPagination.page_count}
            perPage={itemPagination.per_page}
            totalCount={itemPagination.total_count}
            isLoading={isLoadingItems}
            onPageChange={(nextPage) => setItemPage(nextPage)}
            onPerPageChange={(nextPerPage) => {
              setItemPerPage(nextPerPage);
              setItemPage(1);
            }}
            perPageOptions={ITEM_PER_PAGE_OPTIONS}
          />
        </section>
      </div>
    );
  };

  const renderItemDetailsPage = () => {
    if (isLoadingDetail) {
      return (
        <div className="mt-4 rounded-lg border border-slate-200 p-4">
          <p className="text-sm text-slate-600">{t("Loading item details...")}</p>
        </div>
      );
    }

    if (!detailItem || !detailItemForm) {
      return (
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center">
          <p className="text-sm text-slate-600">
            {t("Item not found or unavailable. Go back to the list and try again.")}
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-3 h-10"
            onClick={() => navigate({ name: "items" })}
          >
            {t("Back to Items")}
          </Button>
        </div>
      );
    }

    return (
      <div className="mt-4 space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={() => navigate({ name: "items" })}
            className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("Back to items")}
          </button>

          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-xs font-medium",
              statusBadgeClass(detailItem.status),
            )}
          >
            {statusLabelByValue.get(detailItem.status) ?? detailItem.status}
          </span>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-lg font-semibold text-slate-900">{detailItem.serial_number}</p>
          <p className="mt-1 text-sm text-slate-600">{detailItem.name || t("Unnamed item")}</p>
          <p className="mt-2 text-xs text-slate-500">
            {t("Created")}: {formatDate(detailItem.created_at)} | {t("Updated")}:{" "}
            {formatDate(detailItem.updated_at)}
          </p>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <form
            onSubmit={handleDetailItemSubmit}
            className="rounded-lg border border-slate-200 p-4"
          >
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Wrench className="h-4 w-4" />
              {t("Item Details")}
            </p>

            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Serial Number")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={detailItemForm.serialNumber}
                  onChange={(event) =>
                    setDetailItemForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            serialNumber: event.target.value,
                          }
                        : prev,
                    )
                  }
                  disabled={!canManage || isMutating}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Name")}
                </label>
                <input
                  className={cn(fieldClassName, "mt-1")}
                  value={detailItemForm.name}
                  onChange={(event) =>
                    setDetailItemForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            name: event.target.value,
                          }
                        : prev,
                    )
                  }
                  disabled={!canManage || isMutating}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Category")}
                </label>
                <select
                  className={cn(fieldClassName, "mt-1")}
                  value={detailItemForm.categoryId}
                  onChange={(event) =>
                    setDetailItemForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            categoryId: event.target.value,
                          }
                        : prev,
                    )
                  }
                  disabled={!canManage || isMutating || !categories.length}
                >
                  <option value="">{t("Select category")}</option>
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
                  value={detailItemForm.status}
                  onChange={(event) =>
                    setDetailItemForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            status: event.target.value as InventoryItemStatus,
                          }
                        : prev,
                    )
                  }
                  disabled={!canManage || isMutating}
                >
                  {ITEM_STATUS_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {statusLabel(option, t)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-3">
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={detailItemForm.isActive}
                  onChange={(event) =>
                    setDetailItemForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            isActive: event.target.checked,
                          }
                        : prev,
                    )
                  }
                  disabled={!canManage || isMutating}
                />
                {t("Active item")}
              </label>
            </div>

            {canManage ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="submit" className="h-10" disabled={isMutating}>
                  {t("Save Changes")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 text-rose-700"
                  onClick={() => void handleDetailItemDelete()}
                  disabled={isMutating}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  {t("Delete Item")}
                </Button>
              </div>
            ) : null}
          </form>

          <section className="rounded-lg border border-slate-200 p-4">
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Package className="h-4 w-4" />
              {t("Inherited Category Parts ({{count}})", { count: detailParts.length })}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {t(
                "These parts come from the selected category and are shared across all items in that category. Manage them in the Categories tab.",
              )}
            </p>

            <div className="mt-3 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
              {detailParts.length ? (
                detailParts.map((part) => (
                  <div
                    key={part.id}
                    className="flex flex-col gap-2 rounded-md border border-slate-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-900">{part.name}</p>
                      <p className="text-xs text-slate-500">{formatDate(part.updated_at)}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="rounded-md border border-dashed border-slate-300 px-3 py-5 text-center text-sm text-slate-500">
                  {t("No parts for this category.")}
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    );
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Inventory Management")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Categories and inventory are split into dedicated screens for large data.")}
          </p>
          {!canManage ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Roles ({{roles}}) can view inventory data but cannot modify it.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
        </div>

        <div className="flex w-full flex-wrap items-center justify-end gap-2 sm:w-auto">
          {canManage ? (
            <>
              <input
                ref={importFileInputRef}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="hidden"
                onChange={(event) => void handleImportFile(event)}
              />
              <Button
                type="button"
                variant="outline"
                className="h-10"
                onClick={() => importFileInputRef.current?.click()}
                disabled={
                  isImporting ||
                  isMutating ||
                  isLoadingCategories ||
                  isLoadingItems ||
                  isLoadingParts ||
                  isLoadingDetail
                }
              >
                <Upload className="mr-2 h-4 w-4" />
                {isImporting ? t("Importing...") : t("Import")}
              </Button>
            </>
          ) : null}

          <Button
            type="button"
            className="h-10"
            onClick={() => void handleExport()}
            disabled={isExporting || isImporting || isMutating}
          >
            <Download className="mr-2 h-4 w-4" />
            {isExporting ? t("Exporting...") : t("Export")}
          </Button>

          <Button
            type="button"
            variant="outline"
            className="h-10"
            onClick={() => void handleRefresh()}
            disabled={
              isExporting ||
              isImporting ||
              isMutating ||
              isLoadingCategories ||
              isLoadingItems ||
              isLoadingParts ||
              isLoadingDetail
            }
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
          onClick={() => navigate({ name: "categories" })}
          className={cn(
            "rm-menu-btn",
            activeMenu === "categories"
              ? "rm-menu-btn-active"
              : "rm-menu-btn-idle",
          )}
        >
          <span className="inline-flex items-center gap-2">
            <FolderTree className="h-4 w-4" />
            {t("Categories")}
          </span>
        </button>

        <button
          type="button"
          onClick={() => navigate({ name: "items" })}
          className={cn(
            "rm-menu-btn",
            activeMenu === "items"
              ? "rm-menu-btn-active"
              : "rm-menu-btn-idle",
          )}
        >
          <span className="inline-flex items-center gap-2">
            <Package className="h-4 w-4" />
            {t("Inventory Items")}
          </span>
        </button>
      </div>

      {route.name === "categories" ? renderCategoryPage() : null}
      {route.name === "items" ? renderItemsListPage() : null}
      {route.name === "itemDetail" ? renderItemDetailsPage() : null}
    </section>
  );
}
