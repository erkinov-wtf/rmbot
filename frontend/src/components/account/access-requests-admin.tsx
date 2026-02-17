import {
  CheckCircle2,
  RefreshCcw,
  Search,
  UserCheck,
  UserRound,
  UserX,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  approveAccessRequest,
  listAccessRequests,
  rejectAccessRequest,
  type AccessRequest,
  type AccessRequestStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type AccessRequestsAdminProps = {
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

const ROLE_OPTIONS: Array<{ slug: string; label: string }> = [
  { slug: "super_admin", label: "Super Admin" },
  { slug: "ops_manager", label: "Ops Manager" },
  { slug: "master", label: "Master" },
  { slug: "technician", label: "Technician" },
  { slug: "qc_inspector", label: "QC Inspector" },
];

const STATUS_OPTIONS: Array<{ value: AccessRequestStatus; label: string }> = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

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

function statusBadgeClass(status: AccessRequestStatus): string {
  if (status === "pending") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (status === "approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function statusLabel(status: AccessRequestStatus): string {
  return STATUS_OPTIONS.find((item) => item.value === status)?.label ?? status;
}

export function AccessRequestsAdmin({
  accessToken,
  canManage,
  roleSlugs,
}: AccessRequestsAdminProps) {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState<AccessRequestStatus>("pending");
  const [search, setSearch] = useState("");
  const [selectedRolesByRequest, setSelectedRolesByRequest] = useState<
    Record<number, string[]>
  >({});

  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const filteredRequests = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) {
      return requests;
    }

    return requests.filter((request) => {
      const fullName = `${request.first_name ?? ""} ${request.last_name ?? ""}`
        .trim()
        .toLowerCase();
      const username = (request.username ?? "").toLowerCase();
      const phone = (request.phone ?? "").toLowerCase();
      const note = (request.note ?? "").toLowerCase();
      const telegramId = String(request.telegram_id);

      return (
        fullName.includes(normalized) ||
        username.includes(normalized) ||
        phone.includes(normalized) ||
        note.includes(normalized) ||
        telegramId.includes(normalized)
      );
    });
  }, [requests, search]);

  const loadRequests = useCallback(async () => {
    if (!canManage) {
      setIsLoading(false);
      setRequests([]);
      return;
    }

    setIsLoading(true);
    setFeedback(null);
    try {
      const nextRequests = await listAccessRequests(accessToken, {
        status: statusFilter,
        ordering: statusFilter === "pending" ? "-created_at" : "-resolved_at",
        per_page: 200,
      });
      setRequests(nextRequests);
    } catch (error) {
      setFeedback({
        type: "error",
        message: toErrorMessage(error, "Failed to load access requests."),
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, canManage, statusFilter]);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  const runMutation = useCallback(
    async (task: () => Promise<void>, successMessage: string) => {
      setIsMutating(true);
      setFeedback(null);
      try {
        await task();
        setFeedback({ type: "success", message: successMessage });
        await loadRequests();
      } catch (error) {
        setFeedback({
          type: "error",
          message: toErrorMessage(error, "Action failed."),
        });
      } finally {
        setIsMutating(false);
      }
    },
    [loadRequests],
  );

  const toggleRole = (requestId: number, roleSlug: string) => {
    setSelectedRolesByRequest((prev) => {
      const existing = prev[requestId] ?? [];
      if (existing.includes(roleSlug)) {
        return {
          ...prev,
          [requestId]: existing.filter((slug) => slug !== roleSlug),
        };
      }
      return {
        ...prev,
        [requestId]: [...existing, roleSlug],
      };
    });
  };

  const handleApprove = async (request: AccessRequest) => {
    if (!canManage || request.status !== "pending") {
      return;
    }

    const selectedRoleSlugs = selectedRolesByRequest[request.id] ?? [];
    await runMutation(async () => {
      await approveAccessRequest(accessToken, request.id, selectedRoleSlugs);
      setSelectedRolesByRequest((prev) => {
        const next = { ...prev };
        delete next[request.id];
        return next;
      });
    }, "Access request approved.");
  };

  const handleReject = async (request: AccessRequest) => {
    if (!canManage || request.status !== "pending") {
      return;
    }

    if (!window.confirm("Reject this access request?")) {
      return;
    }

    await runMutation(async () => {
      await rejectAccessRequest(accessToken, request.id);
      setSelectedRolesByRequest((prev) => {
        const next = { ...prev };
        delete next[request.id];
        return next;
      });
    }, "Access request rejected.");
  };

  return (
    <section className="rm-panel rm-animate-enter-delayed p-4 sm:p-5">
      <div className="flex flex-col gap-3 border-b border-slate-200/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Access Requests</h2>
          <p className="mt-1 text-sm text-slate-600">
            Approve or reject bot onboarding requests and assign user roles.
          </p>
          {!canManage ? (
            <p className="mt-2 text-xs text-amber-700">
              Roles ({roleSlugs.join(", ") || "none"}) cannot manage access requests.
            </p>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-10 w-full sm:w-auto"
          onClick={() => void loadRequests()}
          disabled={isLoading || isMutating || !canManage}
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {feedback ? (
        <p
          className={cn(
            "mt-4 rounded-xl border px-3 py-2 text-sm",
            feedback.type === "error"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : "border-emerald-200 bg-emerald-50 text-emerald-700",
          )}
        >
          {feedback.message}
        </p>
      ) : null}

      {!canManage ? (
        <p className="mt-4 rounded-md border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-600">
          Access request management is available only for Super Admin and Ops Manager.
        </p>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-[200px_1fr]">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Status
              </label>
              <select
                className={cn(fieldClassName, "mt-1")}
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as AccessRequestStatus)
                }
                disabled={isLoading || isMutating}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Search
              </label>
              <div className="relative mt-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  className={cn(fieldClassName, "pl-9")}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Name, username, phone, telegram id"
                  disabled={isLoading}
                />
              </div>
            </div>
          </div>

          <section className="mt-4 rounded-lg border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <p className="text-sm font-semibold text-slate-900">
                Requests ({filteredRequests.length})
              </p>
              <span className="text-xs text-slate-500">
                Filter: {statusLabel(statusFilter)}
              </span>
            </div>

            {isLoading ? (
              <p className="px-4 py-6 text-sm text-slate-600">Loading access requests...</p>
            ) : filteredRequests.length ? (
              <div className="space-y-3 p-3">
                {filteredRequests.map((request) => (
                  <article
                    key={request.id}
                    className="rounded-md border border-slate-200 bg-slate-50 p-3"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-slate-900">
                            {request.first_name || "Unknown"} {request.last_name || ""}
                          </p>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-xs font-medium",
                              statusBadgeClass(request.status),
                            )}
                          >
                            {statusLabel(request.status)}
                          </span>
                        </div>

                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
                          <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-2 py-0.5">
                            <Users className="h-3.5 w-3.5" />
                            #{request.id}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-2 py-0.5">
                            <UserRound className="h-3.5 w-3.5" />
                            tg:{request.telegram_id}
                          </span>
                          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                            @{request.username || "-"}
                          </span>
                          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5">
                            {request.phone || "No phone"}
                          </span>
                        </div>

                        {request.note ? (
                          <p className="mt-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700">
                            Note: {request.note}
                          </p>
                        ) : null}

                        <p className="mt-2 text-xs text-slate-500">
                          Created: {formatDate(request.created_at)} | Resolved: {formatDate(request.resolved_at)}
                        </p>
                      </div>

                      {request.status === "pending" ? (
                        <div className="w-full max-w-md space-y-2 rounded-md border border-slate-200 bg-white p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                            Assign Roles On Approval (Optional)
                          </p>

                          <div className="grid gap-1 sm:grid-cols-2">
                            {ROLE_OPTIONS.map((role) => {
                              const selected =
                                (selectedRolesByRequest[request.id] ?? []).includes(
                                  role.slug,
                                );

                              return (
                                <label
                                  key={`${request.id}-${role.slug}`}
                                  className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700"
                                >
                                  <input
                                    type="checkbox"
                                    checked={selected}
                                    onChange={() => toggleRole(request.id, role.slug)}
                                    disabled={isMutating}
                                  />
                                  {role.label}
                                </label>
                              );
                            })}
                          </div>

                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              className="h-8"
                              onClick={() => void handleApprove(request)}
                              disabled={isMutating}
                            >
                              <UserCheck className="mr-1 h-3.5 w-3.5" />
                              Approve
                            </Button>

                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 text-rose-700"
                              onClick={() => void handleReject(request)}
                              disabled={isMutating}
                            >
                              <UserX className="mr-1 h-3.5 w-3.5" />
                              Reject
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Resolved
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="px-4 py-8 text-center text-sm text-slate-500">
                No access requests found.
              </p>
            )}
          </section>
        </>
      )}
    </section>
  );
}
