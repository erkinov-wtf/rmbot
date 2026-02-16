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

export type HealthResponse = {
  status: string;
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
  inventory_item: number | null;
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
  technician: number | null;
  title: string | null;
  ticket_parts: TicketPartSpec[];
  total_duration: number;
  approved_by: number | null;
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
  note: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type InventoryItemQuery = {
  q?: string;
  status?: InventoryItemStatus;
  inventory?: number;
  category?: number;
  is_active?: boolean;
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

export async function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("misc/health/");
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
  body: { inventory_item: number; name: string },
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
  body: Partial<{ inventory_item: number; name: string }>,
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
