const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8005/api/v1";

type PrimitiveQueryValue = string | number | boolean | null | undefined;

type ApiEnvelope<TData> = {
  success: boolean;
  message: string;
  data: TData;
};

type PaginatedEnvelope<TData> = {
  success: boolean;
  message: string;
  results: TData[];
  total_count: number;
  page: number;
  page_count: number;
  per_page: number;
};

export type LoginTokens = {
  access: string;
  refresh: string;
};

export type UserRole = {
  slug: string;
  name: string;
};

type CurrentUserRaw = {
  id: number;
  first_name: string;
  last_name: string | null;
  username: string;
  phone: string | null;
  level: number;
  roles: UserRole[];
};

export type CurrentUser = Omit<CurrentUserRaw, "roles"> & {
  roles: string[];
  role_slugs: string[];
};

type UserOptionRaw = {
  id: number;
  first_name: string;
  last_name: string | null;
  username: string;
  phone: string | null;
  level: number;
  roles: UserRole[];
};

export type UserOption = Omit<UserOptionRaw, "roles"> & {
  roles: string[];
  role_slugs: string[];
  display_name: string;
};

export type XpTransaction = {
  id: number;
  user: number;
  amount: number;
  entry_type: string;
  reference: string;
  description: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type Inventory = {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
};

export type InventoryCategory = {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
};

export type InventoryItemStatus =
  | "ready"
  | "in_service"
  | "rented"
  | "blocked"
  | "write_off";

export type InventoryItem = {
  id: number;
  name: string;
  serial_number: string;
  inventory: number;
  category: number;
  parts: number[];
  status: InventoryItemStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryPart = {
  id: number;
  category: number | null;
  inventory_item?: number | null;
  name: string;
  created_at: string;
  updated_at: string;
};

export type TicketColor = "green" | "yellow" | "red";

export type TicketStatus =
  | "under_review"
  | "new"
  | "assigned"
  | "in_progress"
  | "waiting_qc"
  | "rework"
  | "done";

export type TicketPartSpec = {
  id: number;
  part_id: number;
  part_name: string;
  color: TicketColor;
  comment: string;
  minutes: number;
  created_at: string;
  updated_at: string;
};

export type Ticket = {
  id: number;
  inventory_item: number;
  master: number;
  master_name?: string | null;
  technician: number | null;
  technician_name?: string | null;
  title: string | null;
  ticket_parts: TicketPartSpec[];
  total_duration: number;
  approved_by: number | null;
  approved_by_name?: string | null;
  approved_at: string | null;
  flag_minutes: number;
  flag_color: TicketColor;
  xp_amount: number;
  is_manual: boolean;
  status: TicketStatus;
  assigned_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TicketTransition = {
  id: number;
  ticket: number;
  from_status: TicketStatus | null;
  to_status: TicketStatus;
  action: string;
  actor: number | null;
  actor_username?: string | null;
  actor_name?: string | null;
  note: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkSessionStatus = "running" | "paused" | "stopped";

export type WorkSession = {
  id: number;
  ticket: number;
  technician: number;
  status: WorkSessionStatus;
  started_at: string;
  last_started_at: string | null;
  ended_at: string | null;
  active_seconds: number;
  created_at: string;
  updated_at: string;
};

export type WorkSessionTransitionAction =
  | "started"
  | "paused"
  | "resumed"
  | "stopped";

export type WorkSessionTransition = {
  id: number;
  work_session: number;
  ticket: number;
  from_status: WorkSessionStatus | null;
  to_status: WorkSessionStatus;
  action: WorkSessionTransitionAction;
  actor: number | null;
  actor_username?: string | null;
  actor_name?: string | null;
  event_at: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type TechnicianOption = {
  user_id: number;
  name: string;
  username: string;
  level: number;
};

export type AccessRequestStatus = "pending" | "approved" | "rejected";

export type AccessRequest = {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  note: string | null;
  status: AccessRequestStatus;
  created_at: string;
  resolved_at: string | null;
};

export type AttendancePunctuality = "early" | "on_time" | "late";

export type AttendanceRecord = {
  id: number;
  user: number;
  work_date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  punctuality_status?: AttendancePunctuality | null;
  created_at: string;
  updated_at: string;
};

export type InventoryItemQuery = {
  q?: string;
  status?: InventoryItemStatus;
  inventory?: number;
  category?: number;
  is_active?: boolean;
};

export type AttendanceRecordQuery = {
  work_date?: string;
  user_id?: number;
  punctuality?: AttendancePunctuality;
  ordering?:
    | "user_id"
    | "-user_id"
    | "check_in_at"
    | "-check_in_at"
    | "created_at"
    | "-created_at";
  page?: number;
  per_page?: number;
};

type InventoryRequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  accessToken?: string;
  body?: unknown;
};

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;
  return `${API_BASE_URL}/${normalizedPath}`;
}

function withQuery(path: string, query: Record<string, PrimitiveQueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  const queryString = params.toString();
  if (!queryString) {
    return path;
  }
  return `${path}${path.includes("?") ? "&" : "?"}${queryString}`;
}

function toErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (payload && typeof payload === "object") {
    if ("message" in payload && typeof payload.message === "string") {
      return payload.message;
    }
    if ("detail" in payload && typeof payload.detail === "string") {
      return payload.detail;
    }
  }

  return fallback;
}

async function parseJsonSafe(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function extractData<TData>(payload: unknown): TData {
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as ApiEnvelope<TData>).data;
  }
  return payload as TData;
}

function extractResults<TData>(payload: unknown): TData[] {
  if (payload && typeof payload === "object") {
    if ("results" in payload && Array.isArray(payload.results)) {
      return (payload as PaginatedEnvelope<TData>).results;
    }
    if ("data" in payload) {
      const maybeData = (payload as { data?: unknown }).data;
      if (Array.isArray(maybeData)) {
        return maybeData as TData[];
      }
    }
  }
  if (Array.isArray(payload)) {
    return payload as TData[];
  }
  return [];
}

async function apiRequest<TResponse>(
  path: string,
  options: InventoryRequestOptions = {},
): Promise<TResponse> {
  const { method = "GET", accessToken, body } = options;

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(buildApiUrl(path), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const payload =
    response.status === 204 ? null : await parseJsonSafe(response);
  if (!response.ok) {
    throw new Error(
      toErrorMessage(
        payload,
        `Request failed with status ${response.status} for ${path}`,
      ),
    );
  }

  return payload as TResponse;
}

export async function loginWithPassword(
  username: string,
  password: string,
): Promise<LoginTokens> {
  const payload = await apiRequest<unknown>("auth/login/", {
    method: "POST",
    body: { username, password },
  });
  const tokens = extractData<LoginTokens>(payload);

  if (!tokens?.access || !tokens?.refresh) {
    throw new Error("Login response is missing access/refresh tokens.");
  }

  return tokens;
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  const payload = await apiRequest<unknown>("users/me/", { accessToken });
  const user = extractData<CurrentUserRaw>(payload);
  const { roles, ...rest } = user;

  return {
    ...rest,
    roles: roles.map((role) => role.name),
    role_slugs: roles.map((role) => role.slug),
  };
}

export async function listUserOptions(
  accessToken: string,
  query: { q?: string; page?: number; per_page?: number } = {},
): Promise<UserOption[]> {
  const payload = await apiRequest<unknown>(
    withQuery("users/options/", {
      q: query.q,
      page: query.page,
      per_page: query.per_page ?? 200,
    }),
    { accessToken },
  );
  const users = extractResults<UserOptionRaw>(payload);

  return users.map((user) => {
    const fullName = `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim();
    return {
      ...user,
      roles: user.roles.map((role) => role.name),
      role_slugs: user.roles.map((role) => role.slug),
      display_name: fullName || user.username,
    };
  });
}

export async function listInventories(accessToken: string): Promise<Inventory[]> {
  const payload = await apiRequest<unknown>(
    withQuery("inventory/", { per_page: 200 }),
    { accessToken },
  );
  return extractResults<Inventory>(payload);
}

export async function createInventory(
  accessToken: string,
  name: string,
): Promise<Inventory> {
  const payload = await apiRequest<unknown>("inventory/", {
    method: "POST",
    accessToken,
    body: { name },
  });
  return extractData<Inventory>(payload);
}

export async function updateInventory(
  accessToken: string,
  id: number,
  name: string,
): Promise<Inventory> {
  const payload = await apiRequest<unknown>(`inventory/${id}/`, {
    method: "PATCH",
    accessToken,
    body: { name },
  });
  return extractData<Inventory>(payload);
}

export async function deleteInventory(
  accessToken: string,
  id: number,
): Promise<void> {
  await apiRequest<void>(`inventory/${id}/`, {
    method: "DELETE",
    accessToken,
  });
}

export async function listCategories(
  accessToken: string,
): Promise<InventoryCategory[]> {
  const payload = await apiRequest<unknown>(
    withQuery("inventory/categories/", { per_page: 200 }),
    { accessToken },
  );
  return extractResults<InventoryCategory>(payload);
}

export async function listAllCategories(
  accessToken: string,
): Promise<InventoryCategory[]> {
  const payload = await apiRequest<unknown>("inventory/categories/all/", {
    accessToken,
  });
  const data = extractData<unknown>(payload);
  if (Array.isArray(data)) {
    return data as InventoryCategory[];
  }
  return extractResults<InventoryCategory>(payload);
}

export async function createCategory(
  accessToken: string,
  name: string,
): Promise<InventoryCategory> {
  const payload = await apiRequest<unknown>("inventory/categories/", {
    method: "POST",
    accessToken,
    body: { name },
  });
  return extractData<InventoryCategory>(payload);
}

export async function updateCategory(
  accessToken: string,
  id: number,
  name: string,
): Promise<InventoryCategory> {
  const payload = await apiRequest<unknown>(`inventory/categories/${id}/`, {
    method: "PATCH",
    accessToken,
    body: { name },
  });
  return extractData<InventoryCategory>(payload);
}

export async function deleteCategory(
  accessToken: string,
  id: number,
): Promise<void> {
  await apiRequest<void>(`inventory/categories/${id}/`, {
    method: "DELETE",
    accessToken,
  });
}

export async function listInventoryItems(
  accessToken: string,
  query: InventoryItemQuery = {},
): Promise<InventoryItem[]> {
  const payload = await apiRequest<unknown>(
    withQuery("inventory/items/", {
      per_page: 200,
      q: query.q,
      status: query.status,
      inventory: query.inventory,
      category: query.category,
      is_active: query.is_active,
    }),
    { accessToken },
  );
  return extractResults<InventoryItem>(payload);
}

export async function createInventoryItem(
  accessToken: string,
  body: {
    serial_number: string;
    name?: string;
    inventory?: number;
    category?: number;
    status: InventoryItemStatus;
    is_active: boolean;
  },
): Promise<InventoryItem> {
  const payload = await apiRequest<unknown>("inventory/items/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<InventoryItem>(payload);
}

export async function getInventoryItem(
  accessToken: string,
  id: number,
): Promise<InventoryItem> {
  const payload = await apiRequest<unknown>(`inventory/items/${id}/`, {
    accessToken,
  });
  return extractData<InventoryItem>(payload);
}

export async function updateInventoryItem(
  accessToken: string,
  id: number,
  body: Partial<{
    serial_number: string;
    name: string;
    inventory: number;
    category: number;
    status: InventoryItemStatus;
    is_active: boolean;
  }>,
): Promise<InventoryItem> {
  const payload = await apiRequest<unknown>(`inventory/items/${id}/`, {
    method: "PATCH",
    accessToken,
    body,
  });
  return extractData<InventoryItem>(payload);
}

export async function deleteInventoryItem(
  accessToken: string,
  id: number,
): Promise<void> {
  await apiRequest<void>(`inventory/items/${id}/`, {
    method: "DELETE",
    accessToken,
  });
}

export async function listParts(accessToken: string): Promise<InventoryPart[]> {
  const payload = await apiRequest<unknown>(
    withQuery("inventory/parts/", { per_page: 300 }),
    { accessToken },
  );
  return extractResults<InventoryPart>(payload);
}

export async function createPart(
  accessToken: string,
  body: { category: number; name: string },
): Promise<InventoryPart> {
  const payload = await apiRequest<unknown>("inventory/parts/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<InventoryPart>(payload);
}

export async function updatePart(
  accessToken: string,
  id: number,
  body: Partial<{ category: number; name: string }>,
): Promise<InventoryPart> {
  const payload = await apiRequest<unknown>(`inventory/parts/${id}/`, {
    method: "PATCH",
    accessToken,
    body,
  });
  return extractData<InventoryPart>(payload);
}

export async function deletePart(
  accessToken: string,
  id: number,
): Promise<void> {
  await apiRequest<void>(`inventory/parts/${id}/`, {
    method: "DELETE",
    accessToken,
  });
}

export async function listTickets(
  accessToken: string,
  query: { page?: number; per_page?: number } = {},
): Promise<Ticket[]> {
  const payload = await apiRequest<unknown>(
    withQuery("tickets/", {
      page: query.page,
      per_page: query.per_page ?? 200,
    }),
    { accessToken },
  );
  return extractResults<Ticket>(payload);
}

export async function getTicket(
  accessToken: string,
  id: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${id}/`, {
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function createTicket(
  accessToken: string,
  body: {
    serial_number: string;
    title?: string;
    part_specs: Array<{
      part_id: number;
      color: TicketColor;
      comment?: string;
      minutes: number;
    }>;
  },
): Promise<Ticket> {
  const payload = await apiRequest<unknown>("tickets/create/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<Ticket>(payload);
}

export async function listTechnicianOptions(
  accessToken: string,
): Promise<TechnicianOption[]> {
  const payload = await apiRequest<unknown>("analytics/team/", { accessToken });
  const data = extractData<unknown>(payload);

  const root =
    data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  const members = Array.isArray(root?.members) ? root.members : [];

  return members
    .map((member) => {
      if (!member || typeof member !== "object") {
        return null;
      }
      const row = member as Record<string, unknown>;
      const userId = row.user_id;
      const username = row.username;

      if (typeof userId !== "number" || typeof username !== "string") {
        return null;
      }

      const name = typeof row.name === "string" ? row.name : username;
      const level = typeof row.level === "number" ? row.level : 1;

      return {
        user_id: userId,
        name: name.trim() || username,
        username,
        level,
      } satisfies TechnicianOption;
    })
    .filter((row): row is TechnicianOption => row !== null)
    .sort((left, right) => left.name.localeCompare(right.name));
}

export async function listTicketTransitions(
  accessToken: string,
  ticketId: number,
  query: { page?: number; per_page?: number } = {},
): Promise<TicketTransition[]> {
  const payload = await apiRequest<unknown>(
    withQuery(`tickets/${ticketId}/transitions/`, {
      page: query.page,
      per_page: query.per_page ?? 100,
    }),
    { accessToken },
  );
  return extractResults<TicketTransition>(payload);
}

export async function reviewApproveTicket(
  accessToken: string,
  ticketId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/review-approve/`, {
    method: "POST",
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function assignTicket(
  accessToken: string,
  ticketId: number,
  technicianId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/assign/`, {
    method: "POST",
    accessToken,
    body: { technician_id: technicianId },
  });
  return extractData<Ticket>(payload);
}

export async function startTicketWork(
  accessToken: string,
  ticketId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/start/`, {
    method: "POST",
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function moveTicketToWaitingQc(
  accessToken: string,
  ticketId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/to-waiting-qc/`, {
    method: "POST",
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function pauseTicketWorkSession(
  accessToken: string,
  ticketId: number,
): Promise<WorkSession> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/work-session/pause/`, {
    method: "POST",
    accessToken,
  });
  return extractData<WorkSession>(payload);
}

export async function resumeTicketWorkSession(
  accessToken: string,
  ticketId: number,
): Promise<WorkSession> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/work-session/resume/`, {
    method: "POST",
    accessToken,
  });
  return extractData<WorkSession>(payload);
}

export async function stopTicketWorkSession(
  accessToken: string,
  ticketId: number,
): Promise<WorkSession> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/work-session/stop/`, {
    method: "POST",
    accessToken,
  });
  return extractData<WorkSession>(payload);
}

export async function listTicketWorkSessionHistory(
  accessToken: string,
  ticketId: number,
  query: { page?: number; per_page?: number } = {},
): Promise<WorkSessionTransition[]> {
  const payload = await apiRequest<unknown>(
    withQuery(`tickets/${ticketId}/work-session/history/`, {
      page: query.page,
      per_page: query.per_page ?? 100,
    }),
    { accessToken },
  );
  return extractResults<WorkSessionTransition>(payload);
}

export async function qcPassTicket(
  accessToken: string,
  ticketId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/qc-pass/`, {
    method: "POST",
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function qcFailTicket(
  accessToken: string,
  ticketId: number,
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/qc-fail/`, {
    method: "POST",
    accessToken,
  });
  return extractData<Ticket>(payload);
}

export async function reviewTicketManualMetrics(
  accessToken: string,
  ticketId: number,
  body: { flag_color: TicketColor; xp_amount: number },
): Promise<Ticket> {
  const payload = await apiRequest<unknown>(`tickets/${ticketId}/manual-metrics/`, {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<Ticket>(payload);
}

export async function listAccessRequests(
  accessToken: string,
  query: {
    status?: AccessRequestStatus;
    ordering?: "-created_at" | "created_at" | "-resolved_at" | "resolved_at";
    page?: number;
    per_page?: number;
  } = {},
): Promise<AccessRequest[]> {
  const payload = await apiRequest<unknown>(
    withQuery("users/access-requests/", {
      status: query.status,
      ordering: query.ordering,
      page: query.page,
      per_page: query.per_page ?? 200,
    }),
    { accessToken },
  );
  return extractResults<AccessRequest>(payload);
}

export async function approveAccessRequest(
  accessToken: string,
  id: number,
  roleSlugs: string[] = [],
): Promise<AccessRequest> {
  const payload = await apiRequest<unknown>(`users/access-requests/${id}/approve/`, {
    method: "POST",
    accessToken,
    body: { role_slugs: roleSlugs },
  });
  return extractData<AccessRequest>(payload);
}

export async function rejectAccessRequest(
  accessToken: string,
  id: number,
): Promise<AccessRequest> {
  const payload = await apiRequest<unknown>(`users/access-requests/${id}/reject/`, {
    method: "POST",
    accessToken,
  });
  return extractData<AccessRequest>(payload);
}

export async function listAttendanceRecords(
  accessToken: string,
  query: AttendanceRecordQuery = {},
): Promise<AttendanceRecord[]> {
  const payload = await apiRequest<unknown>(
    withQuery("attendance/records/", {
      work_date: query.work_date,
      user_id: query.user_id,
      technician_id: query.user_id,
      punctuality: query.punctuality,
      ordering: query.ordering ?? "user_id",
      page: query.page,
      per_page: query.per_page ?? 300,
    }),
    { accessToken },
  );
  return extractResults<AttendanceRecord>(payload);
}

export async function attendanceCheckIn(
  accessToken: string,
  userId: number,
): Promise<{ attendance: AttendanceRecord; xp_awarded: number }> {
  const payload = await apiRequest<unknown>("attendance/checkin/", {
    method: "POST",
    accessToken,
    body: { user_id: userId, technician_id: userId },
  });
  return extractData<{ attendance: AttendanceRecord; xp_awarded: number }>(payload);
}

export async function attendanceCheckOut(
  accessToken: string,
  userId: number,
): Promise<AttendanceRecord> {
  const payload = await apiRequest<unknown>("attendance/checkout/", {
    method: "POST",
    accessToken,
    body: { user_id: userId, technician_id: userId },
  });
  return extractData<AttendanceRecord>(payload);
}

export async function adjustUserXp(
  accessToken: string,
  body: {
    user_id: number;
    amount: number;
    comment: string;
  },
): Promise<XpTransaction> {
  const payload = await apiRequest<unknown>("xp/adjustments/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<XpTransaction>(payload);
}
