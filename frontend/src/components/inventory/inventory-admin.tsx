import {
  Boxes,
  FolderTree,
  Layers,
  Package,
  PencilLine,
  RefreshCcw,
  Search,
  Trash2,
  Wrench,
} from "lucide-react";
import {
  type ComponentType,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import {
  createCategory,
  createInventory,
  createInventoryItem,
  createPart,
  deleteCategory,
  deleteInventory,
  deleteInventoryItem,
  deletePart,
  listCategories,
  listInventories,
  listInventoryItems,
  listParts,
  type Inventory,
  type InventoryCategory,
  type InventoryItem,
  type InventoryItemStatus,
  type InventoryPart,
  updateCategory,
  updateInventory,
  updateInventoryItem,
  updatePart,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type InventoryAdminProps = {
  accessToken: string;
  canManage: boolean;
  roleTitles: string[];
  roleSlugs: string[];
};

type FeedbackState = {
  type: "success" | "error";
  message: string;
} | null;

type InventoryTab = "items" | "inventories" | "categories" | "parts";

const INVENTORY_TABS: Array<{
  id: InventoryTab;
  label: string;
  icon: ComponentType<{ className?: string }>;
}> = [
  { id: "items", label: "Items", icon: Package },
  { id: "inventories", label: "Inventories", icon: Boxes },
  { id: "categories", label: "Categories", icon: FolderTree },
  { id: "parts", label: "Parts", icon: Wrench },
];

const ITEM_STATUSES: InventoryItemStatus[] = [
  "ready",
  "in_service",
  "rented",
  "blocked",
  "write_off",
];

const fieldClassName =
  "h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200";

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function RoleBadge({ value }: { value: string }) {
  return (
    <span className="rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">
      {value}
    </span>
  );
}

export function InventoryAdmin({
  accessToken,
  canManage,
  roleTitles,
  roleSlugs,
}: InventoryAdminProps) {
  const [activeTab, setActiveTab] = useState<InventoryTab>("items");
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [inventories, setInventories] = useState<Inventory[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [parts, setParts] = useState<InventoryPart[]>([]);

  const [itemSearchInput, setItemSearchInput] = useState("");
  const [itemSearchApplied, setItemSearchApplied] = useState("");

  const [inventoryName, setInventoryName] = useState("");
  const [editingInventoryId, setEditingInventoryId] = useState<number | null>(null);

  const [categoryName, setCategoryName] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);

  const [itemSerialNumber, setItemSerialNumber] = useState("");
  const [itemName, setItemName] = useState("");
  const [itemInventoryId, setItemInventoryId] = useState("");
  const [itemCategoryId, setItemCategoryId] = useState("");
  const [itemStatus, setItemStatus] = useState<InventoryItemStatus>("ready");
  const [itemIsActive, setItemIsActive] = useState(true);
  const [editingItemId, setEditingItemId] = useState<number | null>(null);

  const [partName, setPartName] = useState("");
  const [partInventoryItemId, setPartInventoryItemId] = useState("");
  const [editingPartId, setEditingPartId] = useState<number | null>(null);

  const inventoryNameById = useMemo(
    () => new Map(inventories.map((inventory) => [inventory.id, inventory.name])),
    [inventories],
  );
  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );
  const itemLabelById = useMemo(
    () =>
      new Map(
        items.map((item) => [
          item.id,
          `${item.serial_number}${item.name ? ` - ${item.name}` : ""}`,
        ]),
      ),
    [items],
  );

  const resetInventoryForm = () => {
    setInventoryName("");
    setEditingInventoryId(null);
  };

  const resetCategoryForm = () => {
    setCategoryName("");
    setEditingCategoryId(null);
  };

  const resetItemForm = () => {
    setItemSerialNumber("");
    setItemName("");
    setItemInventoryId("");
    setItemCategoryId("");
    setItemStatus("ready");
    setItemIsActive(true);
    setEditingItemId(null);
  };

  const resetPartForm = () => {
    setPartName("");
    setPartInventoryItemId("");
    setEditingPartId(null);
  };

  const loadInventoryData = useCallback(async () => {
    setIsLoading(true);
    setFeedback(null);

    try {
      const query =
        itemSearchApplied.trim().length >= 2
          ? { q: itemSearchApplied.trim() }
          : undefined;
      const [nextInventories, nextCategories, nextItems, nextParts] =
        await Promise.all([
          listInventories(accessToken),
          listCategories(accessToken),
          listInventoryItems(accessToken, query),
          listParts(accessToken),
        ]);

      setInventories(nextInventories);
      setCategories(nextCategories);
      setItems(nextItems);
      setParts(nextParts);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(
          error,
          "Failed to load inventory management data.",
        ),
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, itemSearchApplied]);

  useEffect(() => {
    void loadInventoryData();
  }, [loadInventoryData]);

  const runMutation = useCallback(
    async (task: () => Promise<void>, successMessage: string) => {
      setIsMutating(true);
      setFeedback(null);
      try {
        await task();
        setFeedback({ type: "success", message: successMessage });
        await loadInventoryData();
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, "Inventory action failed."),
        });
      } finally {
        setIsMutating(false);
      }
    },
    [loadInventoryData],
  );

  const handleInventorySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const trimmed = inventoryName.trim();
    if (!trimmed) {
      setFeedback({ type: "error", message: "Inventory name is required." });
      return;
    }

    await runMutation(async () => {
      if (editingInventoryId) {
        await updateInventory(accessToken, editingInventoryId, trimmed);
      } else {
        await createInventory(accessToken, trimmed);
      }
      resetInventoryForm();
    }, editingInventoryId ? "Inventory updated." : "Inventory created.");
  };

  const handleCategorySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const trimmed = categoryName.trim();
    if (!trimmed) {
      setFeedback({ type: "error", message: "Category name is required." });
      return;
    }

    await runMutation(async () => {
      if (editingCategoryId) {
        await updateCategory(accessToken, editingCategoryId, trimmed);
      } else {
        await createCategory(accessToken, trimmed);
      }
      resetCategoryForm();
    }, editingCategoryId ? "Category updated." : "Category created.");
  };

  const handleItemSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const trimmedSerial = itemSerialNumber.trim();
    if (!trimmedSerial) {
      setFeedback({ type: "error", message: "Serial number is required." });
      return;
    }

    await runMutation(async () => {
      const basePayload = {
        serial_number: trimmedSerial,
        name: itemName.trim() || undefined,
        inventory: itemInventoryId ? Number(itemInventoryId) : undefined,
        category: itemCategoryId ? Number(itemCategoryId) : undefined,
        status: itemStatus,
        is_active: itemIsActive,
      };

      if (editingItemId) {
        await updateInventoryItem(accessToken, editingItemId, basePayload);
      } else {
        await createInventoryItem(accessToken, basePayload);
      }
      resetItemForm();
    }, editingItemId ? "Inventory item updated." : "Inventory item created.");
  };

  const handlePartSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage) {
      return;
    }

    const trimmedName = partName.trim();
    if (!trimmedName) {
      setFeedback({ type: "error", message: "Part name is required." });
      return;
    }
    if (!partInventoryItemId) {
      setFeedback({
        type: "error",
        message: "Select an inventory item for this part.",
      });
      return;
    }

    await runMutation(async () => {
      const payload = {
        inventory_item: Number(partInventoryItemId),
        name: trimmedName,
      };
      if (editingPartId) {
        await updatePart(accessToken, editingPartId, payload);
      } else {
        await createPart(accessToken, payload);
      }
      resetPartForm();
    }, editingPartId ? "Part updated." : "Part created.");
  };

  const handleInventoryDelete = async (id: number) => {
    if (!canManage || !window.confirm("Delete this inventory?")) {
      return;
    }
    await runMutation(async () => {
      await deleteInventory(accessToken, id);
      if (editingInventoryId === id) {
        resetInventoryForm();
      }
    }, "Inventory deleted.");
  };

  const handleCategoryDelete = async (id: number) => {
    if (!canManage || !window.confirm("Delete this category?")) {
      return;
    }
    await runMutation(async () => {
      await deleteCategory(accessToken, id);
      if (editingCategoryId === id) {
        resetCategoryForm();
      }
    }, "Category deleted.");
  };

  const handleItemDelete = async (id: number) => {
    if (!canManage || !window.confirm("Delete this inventory item?")) {
      return;
    }
    await runMutation(async () => {
      await deleteInventoryItem(accessToken, id);
      if (editingItemId === id) {
        resetItemForm();
      }
    }, "Inventory item deleted.");
  };

  const handlePartDelete = async (id: number) => {
    if (!canManage || !window.confirm("Delete this part?")) {
      return;
    }
    await runMutation(async () => {
      await deletePart(accessToken, id);
      if (editingPartId === id) {
        resetPartForm();
      }
    }, "Part deleted.");
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur sm:p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 sm:text-2xl">
            Inventory Administration
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Manage inventories, categories, items, and parts.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {roleTitles.map((title) => (
              <RoleBadge key={title} value={title} />
            ))}
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto">
          <Button
            variant="outline"
            className="h-11 w-full sm:w-auto"
            onClick={() => void loadInventoryData()}
            disabled={isLoading || isMutating}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh Data
          </Button>
          {!canManage ? (
            <p className="text-xs text-amber-700">
              Your roles ({roleSlugs.join(", ") || "none"}) can view inventory
              data but cannot modify it.
            </p>
          ) : null}
        </div>
      </div>

      {feedback ? (
        <div
          className={cn(
            "mt-4 rounded-md border px-3 py-2 text-sm",
            feedback.type === "error"
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700",
          )}
          aria-live="polite"
        >
          {feedback.message}
        </div>
      ) : null}

      <div className="mt-5 grid gap-2 sm:grid-cols-2 md:grid-cols-4">
        {INVENTORY_TABS.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              className={cn(
                "flex h-11 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition",
                activeTab === tab.id
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              )}
              onClick={() => setActiveTab(tab.id)}
            >
              <TabIcon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <p className="mt-5 text-sm text-slate-600">Loading inventory data...</p>
      ) : null}

      {!isLoading && activeTab === "inventories" ? (
        <div className="mt-5 space-y-4">
          <form
            onSubmit={handleInventorySubmit}
            className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
          >
            <p className="mb-3 text-sm font-semibold text-slate-700">
              {editingInventoryId ? "Edit inventory" : "Create inventory"}
            </p>
            <div className="flex flex-col gap-3 md:flex-row">
              <input
                value={inventoryName}
                onChange={(event) => setInventoryName(event.target.value)}
                className={fieldClassName}
                placeholder="Inventory name"
                disabled={!canManage || isMutating}
              />
              {canManage ? (
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    className="h-11"
                    disabled={isMutating}
                  >
                    {editingInventoryId ? "Update" : "Create"}
                  </Button>
                  {editingInventoryId ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="h-11"
                      onClick={resetInventoryForm}
                      disabled={isMutating}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Created</th>
                  {canManage ? <th className="px-4 py-3">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {inventories.map((inventory) => (
                  <tr key={inventory.id} className="border-t border-slate-200">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {inventory.name}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(inventory.created_at)}
                    </td>
                    {canManage ? (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs"
                            onClick={() => {
                              setInventoryName(inventory.name);
                              setEditingInventoryId(inventory.id);
                            }}
                            disabled={isMutating}
                          >
                            <PencilLine className="mr-1 h-3.5 w-3.5" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs text-red-700"
                            onClick={() => void handleInventoryDelete(inventory.id)}
                            disabled={isMutating}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {!isLoading && activeTab === "categories" ? (
        <div className="mt-5 space-y-4">
          <form
            onSubmit={handleCategorySubmit}
            className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
          >
            <p className="mb-3 text-sm font-semibold text-slate-700">
              {editingCategoryId ? "Edit category" : "Create category"}
            </p>
            <div className="flex flex-col gap-3 md:flex-row">
              <input
                value={categoryName}
                onChange={(event) => setCategoryName(event.target.value)}
                className={fieldClassName}
                placeholder="Category name"
                disabled={!canManage || isMutating}
              />
              {canManage ? (
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    className="h-11"
                    disabled={isMutating}
                  >
                    {editingCategoryId ? "Update" : "Create"}
                  </Button>
                  {editingCategoryId ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="h-11"
                      onClick={resetCategoryForm}
                      disabled={isMutating}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Created</th>
                  {canManage ? <th className="px-4 py-3">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {categories.map((category) => (
                  <tr key={category.id} className="border-t border-slate-200">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {category.name}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(category.created_at)}
                    </td>
                    {canManage ? (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
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
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs text-red-700"
                            onClick={() => void handleCategoryDelete(category.id)}
                            disabled={isMutating}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {!isLoading && activeTab === "items" ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-semibold text-slate-700">
                Search inventory items
              </p>
              <p className="text-xs text-slate-500">
                Search uses serial suggestions and requires at least 2 chars.
              </p>
            </div>
            <form
              className="mt-3 flex flex-col gap-2 sm:flex-row"
              onSubmit={(event) => {
                event.preventDefault();
                if (
                  itemSearchInput.trim().length > 0 &&
                  itemSearchInput.trim().length < 2
                ) {
                  setFeedback({
                    type: "error",
                    message: "Search query must be at least 2 characters.",
                  });
                  return;
                }
                setItemSearchApplied(itemSearchInput.trim());
              }}
            >
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  className={cn(fieldClassName, "pl-9")}
                  value={itemSearchInput}
                  onChange={(event) => setItemSearchInput(event.target.value)}
                  placeholder="Search by serial number"
                />
              </div>
              <Button type="submit" variant="outline" className="h-11 sm:w-auto">
                Apply
              </Button>
              {itemSearchApplied ? (
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 sm:w-auto"
                  onClick={() => {
                    setItemSearchInput("");
                    setItemSearchApplied("");
                  }}
                >
                  Clear
                </Button>
              ) : null}
            </form>
          </div>

          <form
            onSubmit={handleItemSubmit}
            className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
          >
            <p className="mb-3 text-sm font-semibold text-slate-700">
              {editingItemId ? "Edit inventory item" : "Create inventory item"}
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <input
                className={fieldClassName}
                placeholder="Serial number (RM-...)"
                value={itemSerialNumber}
                onChange={(event) => setItemSerialNumber(event.target.value)}
                disabled={!canManage || isMutating}
              />
              <input
                className={fieldClassName}
                placeholder="Name (optional)"
                value={itemName}
                onChange={(event) => setItemName(event.target.value)}
                disabled={!canManage || isMutating}
              />
              <select
                className={fieldClassName}
                value={itemInventoryId}
                onChange={(event) => setItemInventoryId(event.target.value)}
                disabled={!canManage || isMutating}
              >
                <option value="">Default inventory</option>
                {inventories.map((inventory) => (
                  <option key={inventory.id} value={inventory.id}>
                    {inventory.name}
                  </option>
                ))}
              </select>
              <select
                className={fieldClassName}
                value={itemCategoryId}
                onChange={(event) => setItemCategoryId(event.target.value)}
                disabled={!canManage || isMutating}
              >
                <option value="">Default category</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
              <select
                className={fieldClassName}
                value={itemStatus}
                onChange={(event) =>
                  setItemStatus(event.target.value as InventoryItemStatus)
                }
                disabled={!canManage || isMutating}
              >
                {ITEM_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
              <label className="inline-flex h-11 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={itemIsActive}
                  onChange={(event) => setItemIsActive(event.target.checked)}
                  disabled={!canManage || isMutating}
                />
                Active item
              </label>
            </div>
            {canManage ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="submit" className="h-11" disabled={isMutating}>
                  {editingItemId ? "Update item" : "Create item"}
                </Button>
                {editingItemId ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11"
                    onClick={resetItemForm}
                    disabled={isMutating}
                  >
                    Cancel
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Serial</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Inventory</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Active</th>
                  {canManage ? <th className="px-4 py-3">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-t border-slate-200">
                    <td className="px-4 py-3 font-semibold text-slate-900">
                      {item.serial_number}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.name}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {inventoryNameById.get(item.inventory) ?? `#${item.inventory}`}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {categoryNameById.get(item.category) ?? `#${item.category}`}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.status}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {item.is_active ? "yes" : "no"}
                    </td>
                    {canManage ? (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs"
                            onClick={() => {
                              setEditingItemId(item.id);
                              setItemSerialNumber(item.serial_number);
                              setItemName(item.name ?? "");
                              setItemInventoryId(String(item.inventory));
                              setItemCategoryId(String(item.category));
                              setItemStatus(item.status);
                              setItemIsActive(item.is_active);
                            }}
                            disabled={isMutating}
                          >
                            <PencilLine className="mr-1 h-3.5 w-3.5" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs text-red-700"
                            onClick={() => void handleItemDelete(item.id)}
                            disabled={isMutating}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {!isLoading && activeTab === "parts" ? (
        <div className="mt-5 space-y-4">
          <form
            onSubmit={handlePartSubmit}
            className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
          >
            <p className="mb-3 text-sm font-semibold text-slate-700">
              {editingPartId ? "Edit part" : "Create part"}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <select
                className={fieldClassName}
                value={partInventoryItemId}
                onChange={(event) => setPartInventoryItemId(event.target.value)}
                disabled={!canManage || isMutating}
              >
                <option value="">Select inventory item</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.serial_number} - {item.name}
                  </option>
                ))}
              </select>
              <input
                className={fieldClassName}
                placeholder="Part name"
                value={partName}
                onChange={(event) => setPartName(event.target.value)}
                disabled={!canManage || isMutating}
              />
            </div>
            {canManage ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="submit" className="h-11" disabled={isMutating}>
                  {editingPartId ? "Update part" : "Create part"}
                </Button>
                {editingPartId ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11"
                    onClick={resetPartForm}
                    disabled={isMutating}
                  >
                    Cancel
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Part</th>
                  <th className="px-4 py-3">Inventory Item</th>
                  <th className="px-4 py-3">Created</th>
                  {canManage ? <th className="px-4 py-3">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {parts.map((part) => (
                  <tr key={part.id} className="border-t border-slate-200">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      <div className="inline-flex items-center gap-1.5">
                        <Layers className="h-4 w-4 text-slate-500" />
                        {part.name}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {part.inventory_item
                        ? itemLabelById.get(part.inventory_item) ??
                          `#${part.inventory_item}`
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(part.created_at)}
                    </td>
                    {canManage ? (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs"
                            onClick={() => {
                              setEditingPartId(part.id);
                              setPartName(part.name);
                              setPartInventoryItemId(
                                part.inventory_item
                                  ? String(part.inventory_item)
                                  : "",
                              );
                            }}
                            disabled={isMutating}
                          >
                            <PencilLine className="mr-1 h-3.5 w-3.5" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-8 px-2 text-xs text-red-700"
                            onClick={() => void handlePartDelete(part.id)}
                            disabled={isMutating}
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
