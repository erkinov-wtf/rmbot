import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  LogIn,
  LogOut,
  RefreshCcw,
  Search,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { FeedbackToast } from "@/components/ui/feedback-toast";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { useI18n } from "@/i18n";
import {
  attendanceCheckIn,
  attendanceCheckOut,
  listAttendanceRecordsPage,
  listUserOptions,
  type AttendancePunctuality,
  type AttendanceRecord,
  type PaginationMeta,
  type UserOption,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type AttendanceAdminProps = {
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

const fieldClassName = "rm-input";
const BUSINESS_TIME_ZONE = import.meta.env.VITE_BUSINESS_TIMEZONE ?? "Asia/Tashkent";

const PUNCTUALITY_OPTIONS: AttendancePunctuality[] = ["early", "on_time", "late"];
const RECORDS_PER_PAGE_OPTIONS = [10, 20, 50];
const DEFAULT_RECORDS_PER_PAGE = 20;

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function businessDateInTimeZone(now: Date): string {
  try {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: BUSINESS_TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = formatter.formatToParts(now);
    const year = parts.find((part) => part.type === "year")?.value;
    const month = parts.find((part) => part.type === "month")?.value;
    const day = parts.find((part) => part.type === "day")?.value;
    if (year && month && day) {
      return `${year}-${month}-${day}`;
    }
  } catch {
    // Fall back to local date if configured timezone is invalid.
  }
  return toDateInputValue(now);
}

function shiftDate(value: string, deltaDays: number): string {
  const [year, month, day] = value.split("-").map((part) => Number(part));
  if (!year || !month || !day) {
    return value;
  }
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + deltaDays);
  return toDateInputValue(date);
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

function formatDateLabel(value: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function punctualityBadgeClass(value: AttendancePunctuality | null | undefined): string {
  if (value === "early") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (value === "on_time") {
    return "border-cyan-200 bg-cyan-50 text-cyan-700";
  }
  if (value === "late") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function punctualityLabel(
  value: AttendancePunctuality | null | undefined,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (!value) {
    return t("Not set");
  }
  if (value === "early") {
    return t("Early");
  }
  if (value === "on_time") {
    return t("On Time");
  }
  if (value === "late") {
    return t("Late");
  }
  return value;
}

export function AttendanceAdmin({
  accessToken,
  canManage,
  roleSlugs,
}: AttendanceAdminProps) {
  const { t } = useI18n();
  const [clockMs, setClockMs] = useState(() => Date.now());
  const businessTodayDate = useMemo(
    () => businessDateInTimeZone(new Date(clockMs)),
    [clockMs],
  );

  const [workDate, setWorkDate] = useState(() =>
    businessDateInTimeZone(new Date()),
  );
  const [filterUserId, setFilterUserId] = useState<number | "">("");
  const [actionUserId, setActionUserId] = useState<number | "">("");
  const [userSearch, setUserSearch] = useState("");
  const [punctuality, setPunctuality] = useState<AttendancePunctuality | "">("");

  const [users, setUsers] = useState<UserOption[]>([]);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [recordsPage, setRecordsPage] = useState(1);
  const [recordsPerPage, setRecordsPerPage] = useState(DEFAULT_RECORDS_PER_PAGE);
  const [recordsPagination, setRecordsPagination] = useState<PaginationMeta>({
    page: 1,
    per_page: DEFAULT_RECORDS_PER_PAGE,
    total_count: 0,
    page_count: 1,
  });
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [isLoadingRecords, setIsLoadingRecords] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const usersById = useMemo(() => {
    return new Map<number, UserOption>(users.map((user) => [user.id, user]));
  }, [users]);

  const selectableUsers = useMemo(() => {
    const normalized = userSearch.trim().toLowerCase();
    if (!normalized) {
      return users;
    }
    return users.filter((user) => {
      return (
        user.display_name.toLowerCase().includes(normalized) ||
        user.username.toLowerCase().includes(normalized) ||
        (user.phone ?? "").toLowerCase().includes(normalized)
      );
    });
  }, [userSearch, users]);

  const selectedActionUser = useMemo(() => {
    if (typeof actionUserId !== "number") {
      return null;
    }
    return usersById.get(actionUserId) ?? null;
  }, [actionUserId, usersById]);

  const isActionDateToday = useMemo(
    () => workDate === businessTodayDate,
    [workDate, businessTodayDate],
  );

  const loadUsers = useCallback(async () => {
    if (!canManage) {
      setUsers([]);
      setActionUserId("");
      setFilterUserId("");
      return;
    }

    setIsLoadingUsers(true);
    try {
      const nextUsers = await listUserOptions(accessToken, { per_page: 500 });
      setUsers(nextUsers);
      setActionUserId((prev) => {
        if (typeof prev === "number" && nextUsers.some((user) => user.id === prev)) {
          return prev;
        }
        return nextUsers[0]?.id ?? "";
      });
      setFilterUserId((prev) => {
        if (typeof prev === "number" && nextUsers.some((user) => user.id === prev)) {
          return prev;
        }
        return "";
      });
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load users.")),
      });
    } finally {
      setIsLoadingUsers(false);
    }
  }, [accessToken, canManage, t]);

  const loadRecords = useCallback(async () => {
    if (!canManage) {
      setRecords([]);
      setRecordsPagination({
        page: 1,
        per_page: recordsPerPage,
        total_count: 0,
        page_count: 1,
      });
      return;
    }

    setIsLoadingRecords(true);
    try {
      const paginated = await listAttendanceRecordsPage(accessToken, {
        work_date: workDate,
        user_id: typeof filterUserId === "number" ? filterUserId : undefined,
        punctuality: punctuality || undefined,
        ordering: "user_id",
        page: recordsPage,
        per_page: recordsPerPage,
      });
      if (recordsPage > paginated.pagination.page_count && paginated.pagination.page_count > 0) {
        setRecordsPage(paginated.pagination.page_count);
        return;
      }
      setRecords(paginated.results);
      setRecordsPagination(paginated.pagination);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, t("Failed to load attendance records.")),
      });
    } finally {
      setIsLoadingRecords(false);
    }
  }, [
    accessToken,
    canManage,
    filterUserId,
    punctuality,
    recordsPage,
    recordsPerPage,
    t,
    workDate,
  ]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    setRecordsPage(1);
  }, [workDate, filterUserId, punctuality]);

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setClockMs(Date.now());
    }, 30_000);
    return () => {
      window.clearInterval(timerId);
    };
  }, []);

  const runAttendanceAction = useCallback(
    async (action: "checkin" | "checkout", userId: number) => {
      if (!isActionDateToday) {
        setFeedback({
          type: "error",
          message: t(
            "Attendance actions are allowed only for today ({{date}}, {{timezone}}).",
            {
              date: businessTodayDate,
              timezone: BUSINESS_TIME_ZONE,
            },
          ),
        });
        return;
      }

      setIsMutating(true);
      setFeedback(null);

      try {
        if (action === "checkin") {
          const payload = await attendanceCheckIn(accessToken, userId);
          const signed = payload.xp_awarded >= 0 ? `+${payload.xp_awarded}` : `${payload.xp_awarded}`;
          setFeedback({
            type: "success",
            message: t("Check-in saved. XP awarded: {{xp}}.", { xp: signed }),
          });
        } else {
          await attendanceCheckOut(accessToken, userId);
          setFeedback({
            type: "success",
            message: t("Check-out saved."),
          });
        }

        if (workDate !== businessTodayDate) {
          setWorkDate(businessTodayDate);
        } else {
          await loadRecords();
        }
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(
            error,
            action === "checkin"
              ? t("Failed to mark check-in.")
              : t("Failed to mark check-out."),
          ),
        });
      } finally {
        setIsMutating(false);
      }
    },
    [accessToken, businessTodayDate, isActionDateToday, loadRecords, t, workDate],
  );

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div
        className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{t("Attendance")}</h2>
          <p className="mt-1 text-sm text-slate-600">
            {t("Review attendance by day and mark check-in/check-out for any user.")}
          </p>
          {!canManage ? (
            <p className="mt-2 text-xs text-amber-700">
              {t("Roles ({{roles}}) cannot manage attendance.", {
                roles: roleSlugs.join(", ") || t("none"),
              })}
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-10 w-full sm:w-auto"
          onClick={() => {
            void Promise.all([loadUsers(), loadRecords()]);
          }}
          disabled={!canManage || isLoadingUsers || isLoadingRecords || isMutating}
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          {t("Refresh")}
        </Button>
      </div>

      <FeedbackToast feedback={feedback} />

      {!canManage ? (
        <p
          className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-600"
        >
          {t("Attendance management is available only for admin roles.")}
        </p>
      ) : (
        <>
          <section className="rm-subpanel mt-4 p-3 sm:p-4">
            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Work Date")}
                </label>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 px-3"
                    onClick={() => setWorkDate((prev) => shiftDate(prev, -1))}
                    disabled={isLoadingRecords || isMutating}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>

                  <input
                    type="date"
                    className={cn(fieldClassName, "w-[170px]")}
                    value={workDate}
                    onChange={(event) => setWorkDate(event.target.value)}
                    disabled={isLoadingRecords || isMutating}
                  />

                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 px-3"
                    onClick={() => setWorkDate((prev) => shiftDate(prev, 1))}
                    disabled={isLoadingRecords || isMutating}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    className="h-10"
                    onClick={() => setWorkDate(businessTodayDate)}
                    disabled={isLoadingRecords || isMutating}
                  >
                    {t("Today")}
                  </Button>
                </div>
                <p className="mt-1 text-xs text-slate-500">{formatDateLabel(workDate)}</p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Filter User")}
                </label>
                <select
                  className={cn(fieldClassName, "mt-1")}
                  value={filterUserId}
                  onChange={(event) => {
                    const raw = event.target.value;
                    if (!raw) {
                      setFilterUserId("");
                      return;
                    }
                    const parsed = Number(raw);
                    setFilterUserId(Number.isInteger(parsed) && parsed > 0 ? parsed : "");
                  }}
                  disabled={isLoadingUsers || isLoadingRecords || isMutating}
                >
                  <option value="">{t("All users")}</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.display_name} (@{user.username})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Punctuality")}
                </label>
                <select
                  className={cn(fieldClassName, "mt-1 min-w-[160px]")}
                  value={punctuality}
                  onChange={(event) =>
                    setPunctuality(event.target.value as AttendancePunctuality | "")
                  }
                  disabled={isLoadingRecords || isMutating}
                >
                  <option value="">{t("All")}</option>
                  {PUNCTUALITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {punctualityLabel(option, t)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="rm-subpanel mt-4 p-3 sm:p-4">
            <p className="text-sm font-semibold text-slate-900">
              {t("Mark Attendance (today)")}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {t(
                "Check-in/check-out endpoints apply to the current business day ({{timezone}}).",
                {
                  timezone: BUSINESS_TIME_ZONE,
                },
              )}
            </p>
            {!isActionDateToday ? (
              <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {t("Selected date is not today")}
              </p>
            ) : null}

            <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Search User")}
                </label>
                <div className="relative mt-1">
                  <Search
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    className={cn(fieldClassName, "pl-9")}
                    value={userSearch}
                    onChange={(event) => setUserSearch(event.target.value)}
                    placeholder={t("Name, username, phone")}
                    disabled={isLoadingUsers || isMutating}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {t("Action User")}
                </label>
                <select
                  className={cn(fieldClassName, "mt-1")}
                  value={actionUserId}
                  onChange={(event) => {
                    const raw = event.target.value;
                    if (!raw) {
                      setActionUserId("");
                      return;
                    }
                    const parsed = Number(raw);
                    setActionUserId(Number.isInteger(parsed) && parsed > 0 ? parsed : "");
                  }}
                  disabled={isLoadingUsers || isMutating || selectableUsers.length === 0}
                >
                  {selectableUsers.length === 0 ? (
                    <option value="">{t("No users found")}</option>
                  ) : null}
                  {selectableUsers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.display_name} (@{user.username})
                    </option>
                  ))}
                </select>
              </div>

              <Button
                type="button"
                className="h-10 self-end"
                disabled={
                  isMutating ||
                  isLoadingUsers ||
                  !isActionDateToday ||
                  typeof actionUserId !== "number" ||
                  !selectedActionUser
                }
                onClick={() => {
                  if (typeof actionUserId === "number") {
                    void runAttendanceAction("checkin", actionUserId);
                  }
                }}
              >
                <LogIn className="mr-2 h-4 w-4" />
                {t("Mark Check-In")}
              </Button>

              <Button
                type="button"
                variant="outline"
                className="h-10 self-end"
                disabled={
                  isMutating ||
                  isLoadingUsers ||
                  !isActionDateToday ||
                  typeof actionUserId !== "number" ||
                  !selectedActionUser
                }
                onClick={() => {
                  if (typeof actionUserId === "number") {
                    void runAttendanceAction("checkout", actionUserId);
                  }
                }}
              >
                <LogOut className="mr-2 h-4 w-4" />
                {t("Mark Check-Out")}
              </Button>
            </div>
          </section>

          <section className="mt-4 rounded-lg border border-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                <CalendarDays className="h-4 w-4" />
                {t("Attendance Records")}
              </p>
              <span className="text-xs text-slate-500">
                {t("Rows: {{count}}", { count: recordsPagination.total_count })}
              </span>
            </div>

            {isLoadingRecords ? (
              <p className="px-4 py-6 text-sm text-slate-600">
                {t("Loading attendance records...")}
              </p>
            ) : records.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("User")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("Check-In")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("Check-Out")}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("Punctuality")}
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-600">
                        {t("Actions")}
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {records.map((record) => {
                      const user = usersById.get(record.user);
                      const canMarkIn = isActionDateToday && !record.check_in_at;
                      const canMarkOut =
                        isActionDateToday &&
                        Boolean(record.check_in_at) &&
                        !record.check_out_at;

                      return (
                        <tr key={record.id} className="bg-white">
                          <td className="px-4 py-3">
                            <p className="inline-flex items-center gap-2 text-sm font-medium text-slate-900">
                              <UserRound className="h-4 w-4 text-slate-500" />
                              {user?.display_name ?? `user#${record.user}`}
                            </p>
                            {user ? (
                              <p className="mt-1 text-xs text-slate-500">@{user.username}</p>
                            ) : null}
                          </td>

                          <td className="px-4 py-3 text-sm text-slate-700">
                            <span className="inline-flex items-center gap-1">
                              <Clock3 className="h-4 w-4 text-slate-400" />
                              {formatDateTime(record.check_in_at)}
                            </span>
                          </td>

                          <td className="px-4 py-3 text-sm text-slate-700">
                            <span className="inline-flex items-center gap-1">
                              <Clock3 className="h-4 w-4 text-slate-400" />
                              {formatDateTime(record.check_out_at)}
                            </span>
                          </td>

                          <td className="px-4 py-3">
                            <span
                              className={cn(
                                "rounded-full border px-2 py-0.5 text-xs font-medium",
                                punctualityBadgeClass(record.punctuality_status ?? null),
                              )}
                            >
                              {punctualityLabel(record.punctuality_status ?? null, t)}
                            </span>
                          </td>

                          <td className="px-4 py-3">
                            <div className="flex justify-end gap-2">
                              <Button
                                type="button"
                                size="sm"
                                className="h-8 px-3"
                                disabled={!canMarkIn || isMutating}
                                onClick={() => {
                                  void runAttendanceAction("checkin", record.user);
                                }}
                              >
                                {t("In")}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 px-3"
                                disabled={!canMarkOut || isMutating}
                                onClick={() => {
                                  void runAttendanceAction("checkout", record.user);
                                }}
                              >
                                {t("Out")}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-4 py-6 text-sm text-slate-600">
                {t("No attendance records for this date and filter combination.")}
              </p>
            )}

            <PaginationControls
              page={recordsPagination.page}
              pageCount={recordsPagination.page_count}
              perPage={recordsPagination.per_page}
              totalCount={recordsPagination.total_count}
              isLoading={isLoadingRecords}
              onPageChange={(nextPage) => setRecordsPage(nextPage)}
              onPerPageChange={(nextPerPage) => {
                setRecordsPerPage(nextPerPage);
                setRecordsPage(1);
              }}
              perPageOptions={RECORDS_PER_PAGE_OPTIONS}
            />
          </section>
        </>
      )}
    </section>
  );
}
