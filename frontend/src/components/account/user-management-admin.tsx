import {
  ImagePlus,
  RefreshCcw,
  Search,
  Shield,
  UserCheck2,
  UserRoundCog,
  UserX2,
  Users,
} from "lucide-react";
import {
  type ChangeEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { AccessRequestsAdmin } from "@/components/account/access-requests-admin";
import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { useI18n } from "@/i18n";
import {
  getManagedUser,
  listManagedUsersPage,
  listRoleOptions,
  updateManagedUser,
  updateManagedUserPhoto,
  type ManagedUser,
  type ManagedUserQuery,
  type PaginationMeta,
  type RoleOption,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type UserManagementAdminProps = {
  accessToken: string;
  canManage: boolean;
  roleSlugs: string[];
};

type FeedbackState =
  | {
      type: "success" | "error";
      message: string;
    }
  | null;

type UserTab = "users" | "access_requests";
type ActivityFilter = "all" | "active" | "inactive";

const fieldClassName = "rm-input";
const USER_PER_PAGE_OPTIONS = [10, 20, 50];
const DEFAULT_USER_PER_PAGE = 20;
const MAX_AVATAR_FILE_BYTES = 3 * 1024 * 1024;
const MAX_AVATAR_FILE_LABEL = "3 MB";

const FALLBACK_ROLE_OPTIONS: RoleOption[] = [
  { slug: "super_admin", name: "Super Admin" },
  { slug: "ops_manager", name: "Ops Manager" },
  { slug: "master", name: "Master" },
  { slug: "technician", name: "Technician" },
  { slug: "qc_inspector", name: "QC Inspector" },
];

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function initialsFromName(value: string): string {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (!words.length) {
    return "?";
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return `${words[0][0] ?? ""}${words[1][0] ?? ""}`.toUpperCase();
}

function parseTabFromPath(pathname: string): UserTab {
  if (
    pathname.startsWith("/access-requests") ||
    pathname.startsWith("/users/access-requests")
  ) {
    return "access_requests";
  }
  return "users";
}

function tabPath(tab: UserTab): string {
  if (tab === "access_requests") {
    return "/users/access-requests";
  }
  return "/users";
}

function rolePillClass(slug: string): string {
  if (slug === "super_admin") {
    return "border-violet-200 bg-violet-50 text-violet-700";
  }
  if (slug === "ops_manager") {
    return "border-indigo-200 bg-indigo-50 text-indigo-700";
  }
  if (slug === "master") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  if (slug === "technician") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (slug === "qc_inspector") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function statusBadgeClass(isActive: boolean): string {
  return isActive
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-rose-200 bg-rose-50 text-rose-700";
}

function hasOwnPhoto(
  source: Record<number, string | null>,
  userId: number,
): boolean {
  return Object.prototype.hasOwnProperty.call(source, userId);
}

type LazyUserAvatarProps = {
  userId: number;
  displayName: string;
  photoUrl: string | null;
  shouldLoad: boolean;
  onVisible: (userId: number) => void;
  className: string;
};

function LazyUserAvatar({
  userId,
  displayName,
  photoUrl,
  shouldLoad,
  onVisible,
  className,
}: LazyUserAvatarProps) {
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
      onVisible(userId);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries.some((entry) => entry.isIntersecting);
        if (!isVisible) {
          return;
        }
        onVisible(userId);
        observer.disconnect();
      },
      {
        rootMargin: "220px 0px",
      },
    );
    observer.observe(root);
    return () => observer.disconnect();
  }, [onVisible, shouldLoad, userId]);

  return (
    <div ref={rootRef} className={className}>
      {photoUrl ? (
        <img
          src={photoUrl}
          alt={displayName}
          className="h-full w-full object-cover"
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-xs font-semibold text-slate-500">
          {initialsFromName(displayName)}
        </div>
      )}
    </div>
  );
}

export function UserManagementAdmin({
  accessToken,
  canManage,
  roleSlugs,
}: UserManagementAdminProps) {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<UserTab>(() =>
    parseTabFromPath(window.location.pathname),
  );

  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [usersPage, setUsersPage] = useState(1);
  const [usersPerPage, setUsersPerPage] = useState(DEFAULT_USER_PER_PAGE);
  const [usersPagination, setUsersPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_USER_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [isLoadingRoles, setIsLoadingRoles] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const [searchInput, setSearchInput] = useState("");
  const [roleFilterInput, setRoleFilterInput] = useState("");
  const [activityInput, setActivityInput] = useState<ActivityFilter>("all");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [appliedRoleFilter, setAppliedRoleFilter] = useState("");
  const [appliedActivity, setAppliedActivity] = useState<ActivityFilter>("all");

  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editRoleSlugs, setEditRoleSlugs] = useState<string[]>([]);
  const [editIsActive, setEditIsActive] = useState(true);
  const [editLevel, setEditLevel] = useState(1);
  const [editPhotoFile, setEditPhotoFile] = useState<File | null>(null);
  const [editPhotoPreview, setEditPhotoPreview] = useState<string | null>(null);
  const [editPhotoClear, setEditPhotoClear] = useState(false);
  const [lazyPhotoByUserId, setLazyPhotoByUserId] = useState<
    Record<number, string | null>
  >({});
  const queuedPhotoIdsRef = useRef<Set<number>>(new Set());
  const photoLoadQueueRef = useRef<number[]>([]);
  const isPhotoQueueRunningRef = useRef(false);
  const editingUserIdRef = useRef<number | null>(null);

  const isSuperAdmin = useMemo(
    () => roleSlugs.includes("super_admin"),
    [roleSlugs],
  );

  const roleOptionsWithFallback = useMemo(() => {
    if (roleOptions.length) {
      return roleOptions;
    }
    return FALLBACK_ROLE_OPTIONS;
  }, [roleOptions]);

  const roleNameBySlug = useMemo(() => {
    const pairs = roleOptionsWithFallback.map((role) => [role.slug, role.name] as const);
    return new Map<string, string>(pairs);
  }, [roleOptionsWithFallback]);

  const counts = useMemo(() => {
    const total = users.length;
    const active = users.filter((user) => user.is_active).length;
    const inactive = total - active;
    return { total, active, inactive };
  }, [users]);

  const fetchManagedUserPhoto = useCallback(
    async (userId: number): Promise<string | null> => {
      const detailed = await getManagedUser(accessToken, userId, {
        include_photo: true,
      });
      const nextPhotoUrl = detailed.photo_url;
      setLazyPhotoByUserId((prev) => ({
        ...prev,
        [userId]: nextPhotoUrl,
      }));
      setUsers((prev) =>
        prev.map((row) =>
          row.id === userId
            ? {
                ...row,
                photo_url: nextPhotoUrl,
              }
            : row,
        ),
      );
      return nextPhotoUrl;
    },
    [accessToken],
  );

  const processPhotoQueue = useCallback(() => {
    if (isPhotoQueueRunningRef.current) {
      return;
    }
    const nextUserId = photoLoadQueueRef.current.shift();
    if (!nextUserId) {
      return;
    }

    isPhotoQueueRunningRef.current = true;
    void fetchManagedUserPhoto(nextUserId)
      .catch(() => {
        setLazyPhotoByUserId((prev) => ({
          ...prev,
          [nextUserId]: null,
        }));
      })
      .finally(() => {
        isPhotoQueueRunningRef.current = false;
        processPhotoQueue();
      });
  }, [fetchManagedUserPhoto]);

  const queuePhotoLoad = useCallback(
    (userId: number, options: { prioritize?: boolean } = {}) => {
      const { prioritize = false } = options;
      if (queuedPhotoIdsRef.current.has(userId)) {
        return;
      }
      queuedPhotoIdsRef.current.add(userId);
      if (prioritize) {
        photoLoadQueueRef.current.unshift(userId);
      } else {
        photoLoadQueueRef.current.push(userId);
      }
      processPhotoQueue();
    },
    [processPhotoQueue],
  );

  const loadRoleOptions = useCallback(async () => {
    if (!canManage) {
      setIsLoadingRoles(false);
      setRoleOptions([]);
      return;
    }
    setIsLoadingRoles(true);
    try {
      const nextRoles = await listRoleOptions(accessToken, { per_page: 100 });
      setRoleOptions(nextRoles);
    } catch {
      setRoleOptions(FALLBACK_ROLE_OPTIONS);
    } finally {
      setIsLoadingRoles(false);
    }
  }, [accessToken, canManage]);

  const loadUsers = useCallback(async () => {
    if (!canManage) {
      setIsLoadingUsers(false);
      setUsers([]);
      setUsersPagination({
        page: 1,
        per_page: usersPerPage,
        total_count: 0,
        page_count: 1,
      });
      return;
    }

    setIsLoadingUsers(true);
    setFeedback(null);
    try {
      const query: ManagedUserQuery = {
        q: appliedSearch || undefined,
        role_slug: appliedRoleFilter || undefined,
        include_photo: false,
        ordering: "-created_at",
        page: usersPage,
        per_page: usersPerPage,
      };
      if (appliedActivity === "active") {
        query.is_active = true;
      } else if (appliedActivity === "inactive") {
        query.is_active = false;
      }
      const paginated = await listManagedUsersPage(accessToken, query);
      if (usersPage > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
        setUsersPage(paginated.pagination.page_count);
        return;
      }
      setUsers(paginated.results);
      setUsersPagination(paginated.pagination);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load users.")),
      });
    } finally {
      setIsLoadingUsers(false);
    }
  }, [
    accessToken,
    appliedActivity,
    appliedRoleFilter,
    appliedSearch,
    canManage,
    t,
    usersPage,
    usersPerPage,
  ]);

  useEffect(() => {
    const onPopState = () => {
      setActiveTab(parseTabFromPath(window.location.pathname));
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    void loadRoleOptions();
  }, [loadRoleOptions]);

  useEffect(() => {
    if (activeTab !== "users") {
      return;
    }
    void loadUsers();
  }, [activeTab, loadUsers]);

  useEffect(() => {
    const activeEditingUserId = editingUserIdRef.current;
    if (activeEditingUserId === null) {
      return;
    }
    if (editPhotoFile || editPhotoClear) {
      return;
    }
    if (!hasOwnPhoto(lazyPhotoByUserId, activeEditingUserId)) {
      return;
    }
    setEditPhotoPreview(lazyPhotoByUserId[activeEditingUserId] ?? null);
  }, [editPhotoClear, editPhotoFile, lazyPhotoByUserId]);

  const handleTabChange = (nextTab: UserTab) => {
    const nextPath = tabPath(nextTab);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setActiveTab(nextTab);
  };

  const handleApplyFilters = () => {
    setUsersPage(1);
    setAppliedSearch(searchInput.trim());
    setAppliedRoleFilter(roleFilterInput);
    setAppliedActivity(activityInput);
  };

  const handleResetFilters = () => {
    setUsersPage(1);
    setSearchInput("");
    setRoleFilterInput("");
    setActivityInput("all");
    setAppliedSearch("");
    setAppliedRoleFilter("");
    setAppliedActivity("all");
  };

  const startEdit = (user: ManagedUser) => {
    const hasCachedPhoto = hasOwnPhoto(lazyPhotoByUserId, user.id);
    const resolvedPhoto = hasCachedPhoto
      ? lazyPhotoByUserId[user.id]
      : user.photo_url;

    editingUserIdRef.current = user.id;
    setEditingUserId(user.id);
    setEditRoleSlugs([...user.role_slugs]);
    setEditIsActive(user.is_active);
    setEditLevel(user.level);
    setEditPhotoFile(null);
    setEditPhotoPreview(resolvedPhoto ?? null);
    setEditPhotoClear(false);
    setFeedback(null);

    if (!resolvedPhoto && user.has_photo) {
      queuePhotoLoad(user.id, { prioritize: true });
    }
  };

  const cancelEdit = () => {
    editingUserIdRef.current = null;
    setEditingUserId(null);
    setEditRoleSlugs([]);
    setEditPhotoFile(null);
    setEditPhotoPreview(null);
    setEditPhotoClear(false);
  };

  const handleEditPhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!selectedFile) {
      return;
    }
    if (selectedFile.size > MAX_AVATAR_FILE_BYTES) {
      setFeedback({
        type: "error",
        message: t("Avatar must be {{size}} or smaller.", {
          size: MAX_AVATAR_FILE_LABEL,
        }),
      });
      return;
    }

    setEditPhotoFile(selectedFile);
    setEditPhotoClear(false);

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setEditPhotoPreview(reader.result);
      }
    };
    reader.readAsDataURL(selectedFile);
  };

  const handleRemoveEditPhoto = (user: ManagedUser) => {
    setEditPhotoFile(null);
    setEditPhotoPreview(null);
    setEditPhotoClear(Boolean(user.photo_url));
  };

  const toggleEditRole = (roleSlug: string) => {
    setEditRoleSlugs((prev) =>
      prev.includes(roleSlug)
        ? prev.filter((slug) => slug !== roleSlug)
        : [...prev, roleSlug],
    );
  };

  const saveUserChanges = async () => {
    if (!canManage || editingUserId === null) {
      return;
    }
    setIsMutating(true);
    setFeedback(null);
    try {
      let updated = await updateManagedUser(accessToken, editingUserId, {
        role_slugs: editRoleSlugs,
        is_active: editIsActive,
        level: editLevel,
      });
      if (editPhotoFile || editPhotoClear) {
        updated = await updateManagedUserPhoto(accessToken, editingUserId, {
          photo: editPhotoFile ?? undefined,
          photo_clear: editPhotoClear,
        });
      }
      setUsers((prev) =>
        prev.map((user) => (user.id === updated.id ? updated : user)),
      );
      setLazyPhotoByUserId((prev) => ({
        ...prev,
        [updated.id]: updated.photo_url,
      }));
      queuedPhotoIdsRef.current.add(updated.id);
      setFeedback({ type: "success", message: t("User updated successfully.") });
      cancelEdit();
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to update user.")),
      });
    } finally {
      setIsMutating(false);
    }
  };

  return (
    <div className="space-y-4">
      <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
        <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{t("User Management")}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {t(
                "See who uses the system, manage user roles and account status, and process onboarding requests.",
              )}
            </p>
            {!canManage ? (
              <p className="mt-2 text-xs text-amber-700">
                {t("Roles ({{roles}}) cannot manage users.", {
                  roles: roleSlugs.join(", ") || t("none"),
                })}
              </p>
            ) : null}
          </div>

          {activeTab === "users" ? (
            <Button
              type="button"
              variant="outline"
              className="h-10 w-full sm:w-auto"
              onClick={() => {
                void Promise.all([loadRoleOptions(), loadUsers()]);
              }}
              disabled={isLoadingUsers || isMutating || !canManage}
            >
              <RefreshCcw className="mr-2 h-4 w-4" />
              {t("Refresh")}
            </Button>
          ) : null}
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            className={cn(
              "rm-menu-btn text-left",
              activeTab === "users" ? "rm-menu-btn-active" : "rm-menu-btn-idle",
            )}
            onClick={() => handleTabChange("users")}
          >
            <span className="inline-flex items-center gap-2">
              <UserRoundCog className="h-4 w-4" />
              {t("Users")}
            </span>
          </button>

          <button
            type="button"
            className={cn(
              "rm-menu-btn text-left",
              activeTab === "access_requests"
                ? "rm-menu-btn-active"
                : "rm-menu-btn-idle",
            )}
            onClick={() => handleTabChange("access_requests")}
          >
            <span className="inline-flex items-center gap-2">
              <Users className="h-4 w-4" />
              {t("Access Requests")}
            </span>
          </button>
        </div>
      </section>

      {activeTab === "access_requests" ? (
        <AccessRequestsAdmin
          accessToken={accessToken}
          canManage={canManage}
          roleSlugs={roleSlugs}
        />
      ) : (
        <section className="rm-panel p-4 sm:p-5">
          <FeedbackToast feedback={feedback} />

          {!canManage ? (
            <p className="rounded-md border border-dashed border-slate-300 px-3 py-8 text-center text-sm text-slate-600">
              {t(
                "User management is available only for Super Admin and Ops Manager.",
              )}
            </p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rm-subpanel p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    {t("Total users")}
                  </p>
                  <p className="mt-1 text-xl font-semibold text-slate-900">{counts.total}</p>
                </div>
                <div className="rm-subpanel p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("Active")}</p>
                  <p className="mt-1 text-xl font-semibold text-emerald-700">{counts.active}</p>
                </div>
                <div className="rm-subpanel p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{t("Inactive")}</p>
                  <p className="mt-1 text-xl font-semibold text-rose-700">{counts.inactive}</p>
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-[1.4fr_1fr_1fr_auto_auto]">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Search")}
                  </label>
                  <div className="relative mt-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      className={cn(fieldClassName, "pl-9")}
                      value={searchInput}
                      onChange={(event) => setSearchInput(event.target.value)}
                      placeholder={t("Name, username or phone")}
                      disabled={isMutating}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Role")}
                  </label>
                  <select
                    className={cn(fieldClassName, "mt-1")}
                    value={roleFilterInput}
                    onChange={(event) => setRoleFilterInput(event.target.value)}
                    disabled={isLoadingRoles || isMutating}
                  >
                    <option value="">{t("All roles")}</option>
                    {roleOptionsWithFallback.map((role) => (
                      <option key={role.slug} value={role.slug}>
                        {t(role.name)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                    {t("Activity")}
                  </label>
                  <select
                    className={cn(fieldClassName, "mt-1")}
                    value={activityInput}
                    onChange={(event) =>
                      setActivityInput(event.target.value as ActivityFilter)
                    }
                    disabled={isMutating}
                  >
                    <option value="all">{t("All users")}</option>
                    <option value="active">{t("Active only")}</option>
                    <option value="inactive">{t("Inactive only")}</option>
                  </select>
                </div>

                <Button
                  type="button"
                  className="mt-6 h-10"
                  onClick={handleApplyFilters}
                  disabled={isLoadingUsers || isMutating}
                >
                  {t("Apply")}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  className="mt-6 h-10"
                  onClick={handleResetFilters}
                  disabled={isLoadingUsers || isMutating}
                >
                  {t("Reset")}
                </Button>
              </div>

              <section className="mt-4 rounded-lg border border-slate-200">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">
                    {t("Users ({{count}})", { count: usersPagination.total_count })}
                  </p>
                </div>

                {isLoadingUsers ? (
                  <p className="px-4 py-8 text-sm text-slate-600">{t("Loading users...")}</p>
                ) : users.length ? (
                  <div className="space-y-3 p-3">
                    {users.map((user) => {
                      const isEditing = editingUserId === user.id;
                      const userRoles = user.role_slugs.length
                        ? user.role_slugs
                        : ["no_role"];
                      const rolesReadOnly = user.is_superuser && !isSuperAdmin;
                      const isLazyPhotoResolved = hasOwnPhoto(lazyPhotoByUserId, user.id);
                      const resolvedPhotoUrl =
                        user.photo_url
                        ?? (isLazyPhotoResolved ? lazyPhotoByUserId[user.id] ?? null : null);
                      const shouldLoadPhoto =
                        user.has_photo && !resolvedPhotoUrl && !isLazyPhotoResolved;

                      return (
                        <article
                          key={user.id}
                          className="rounded-xl border border-slate-200 bg-slate-50 p-3"
                        >
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div className="flex items-start gap-3">
                              <LazyUserAvatar
                                userId={user.id}
                                displayName={user.display_name}
                                photoUrl={resolvedPhotoUrl}
                                shouldLoad={shouldLoadPhoto}
                                onVisible={queuePhotoLoad}
                                className="h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white"
                              />
                              <div className="space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-sm font-semibold text-slate-900">
                                    {user.display_name}
                                  </p>
                                  <span
                                    className={cn(
                                      "rounded-full border px-2 py-0.5 text-xs font-medium",
                                      statusBadgeClass(user.is_active),
                                    )}
                                  >
                                    {user.is_active ? t("Active") : t("Inactive")}
                                  </span>
                                  {user.is_superuser ? (
                                    <span className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700">
                                      <Shield className="h-3.5 w-3.5" />
                                      {t("Superuser")}
                                    </span>
                                  ) : null}
                                </div>

                                <div className="grid gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
                                  <p>{t("Username")}: @{user.username}</p>
                                  <p>{t("Phone")}: {user.phone || "-"}</p>
                                  <p>{t("Level")}: L{user.level}</p>
                                  <p>{t("Last login")}: {formatDateTime(user.last_login)}</p>
                                  <p>{t("Created")}: {formatDateTime(user.created_at)}</p>
                                  <p>
                                    {t("Telegram")}:{" "}
                                    {user.telegram?.telegram_id
                                      ? `tg:${user.telegram.telegram_id}`
                                      : "-"}
                                  </p>
                                </div>

                                <div className="flex flex-wrap gap-2">
                                  {userRoles.map((roleSlug) => (
                                    <span
                                      key={`${user.id}-${roleSlug}`}
                                      className={cn(
                                        "rounded-full border px-2 py-0.5 text-xs font-medium",
                                        rolePillClass(roleSlug),
                                      )}
                                    >
                                      {t(roleNameBySlug.get(roleSlug) ?? roleSlug)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            </div>

                            <div className="flex gap-2">
                              <Button
                                type="button"
                                variant="outline"
                                className="h-9"
                                onClick={() => startEdit(user)}
                                disabled={isMutating || rolesReadOnly}
                              >
                                {t("Manage")}
                              </Button>
                            </div>
                          </div>

                          {isEditing ? (
                            <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
                              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                                {t("Edit user")}
                              </p>
                              <div className="mt-2 grid gap-3 md:grid-cols-2">
                                <div>
                                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                                    {t("Roles")}
                                  </p>
                                  <div className="grid gap-1 sm:grid-cols-2">
                                    {roleOptionsWithFallback.map((role) => {
                                      const selected = editRoleSlugs.includes(role.slug);
                                      return (
                                        <label
                                          key={`${user.id}-${role.slug}`}
                                          className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700"
                                        >
                                          <input
                                            type="checkbox"
                                            checked={selected}
                                            onChange={() => toggleEditRole(role.slug)}
                                            disabled={isMutating}
                                          />
                                          {t(role.name)}
                                        </label>
                                      );
                                    })}
                                  </div>
                                </div>

                                <div className="space-y-2">
                                  <div>
                                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                                      {t("Level")}
                                    </label>
                                    <select
                                      className={cn(fieldClassName, "mt-1")}
                                      value={editLevel}
                                      onChange={(event) =>
                                        setEditLevel(Number(event.target.value))
                                      }
                                      disabled={isMutating}
                                    >
                                      {[1, 2, 3, 4, 5].map((level) => (
                                        <option key={level} value={level}>
                                          L{level}
                                        </option>
                                      ))}
                                    </select>
                                  </div>

                                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                                    <input
                                      type="checkbox"
                                      checked={editIsActive}
                                      onChange={(event) =>
                                        setEditIsActive(event.target.checked)
                                      }
                                      disabled={isMutating}
                                    />
                                      {t("Active account")}
                                    </label>

                                  <div>
                                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                                      {t("Photo")}
                                    </p>
                                    <div className="flex items-center gap-2">
                                      <div className="h-12 w-12 overflow-hidden rounded-lg border border-slate-200 bg-white">
                                        {editPhotoPreview ? (
                                          <img
                                            src={editPhotoPreview}
                                            alt={user.display_name}
                                            className="h-full w-full object-cover"
                                          />
                                        ) : (
                                          <div className="flex h-full w-full items-center justify-center text-xs font-semibold text-slate-500">
                                            {initialsFromName(user.display_name)}
                                          </div>
                                        )}
                                      </div>
                                      <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                                        <ImagePlus className="h-3.5 w-3.5" />
                                        {t("Upload")}
                                        <input
                                          type="file"
                                          accept="image/*"
                                          className="hidden"
                                          onChange={handleEditPhotoChange}
                                          disabled={isMutating}
                                        />
                                      </label>
                                      {(editPhotoPreview || user.photo_url) ? (
                                        <Button
                                          type="button"
                                          variant="outline"
                                          className="h-7 px-2 text-xs"
                                          onClick={() => handleRemoveEditPhoto(user)}
                                          disabled={isMutating}
                                        >
                                          {t("Remove")}
                                        </Button>
                                      ) : null}
                                    </div>
                                    {editPhotoFile ? (
                                      <p className="mt-1 text-[11px] text-slate-500">
                                        {editPhotoFile.name}
                                      </p>
                                    ) : null}
                                  </div>
                                </div>
                              </div>

                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  className="h-9"
                                  onClick={() => void saveUserChanges()}
                                  disabled={isMutating}
                                >
                                  <UserCheck2 className="mr-1 h-4 w-4" />
                                  {t("Save")}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  className="h-9"
                                  onClick={cancelEdit}
                                  disabled={isMutating}
                                >
                                  <UserX2 className="mr-1 h-4 w-4" />
                                  {t("Cancel")}
                                </Button>
                              </div>
                            </div>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <p className="px-4 py-8 text-center text-sm text-slate-500">
                    {t("No users found for selected filters.")}
                  </p>
                )}

                <PaginationControls
                  page={usersPagination.page}
                  pageCount={usersPagination.page_count}
                  perPage={usersPagination.per_page}
                  totalCount={usersPagination.total_count}
                  isLoading={isLoadingUsers}
                  onPageChange={(nextPage) => setUsersPage(nextPage)}
                  onPerPageChange={(nextPerPage) => {
                    setUsersPerPage(nextPerPage);
                    setUsersPage(1);
                  }}
                  perPageOptions={USER_PER_PAGE_OPTIONS}
                />
              </section>
            </>
          )}
        </section>
      )}
    </div>
  );
}
