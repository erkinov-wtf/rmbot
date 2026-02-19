const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
if (!rawApiBaseUrl) {
  throw new Error("Missing VITE_API_BASE_URL");
}
const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, "");

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

export type PaginationMeta = {
  page: number;
  per_page: number;
  total_count: number;
  page_count: number;
};

export type PaginatedResult<TData> = {
  results: TData[];
  pagination: PaginationMeta;
};

export type LoginTokens = {
  access: string;
  refresh: string;
};

export type UserRole = {
  slug: string;
  name: string;
};

export type TelegramProfile = {
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  language_code: string | null;
  is_bot: boolean;
  is_premium: boolean;
  verified_at: string | null;
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

export type TicketFlowPermissions = {
  can_create: boolean;
  can_review: boolean;
  can_assign: boolean;
  can_manual_metrics: boolean;
  can_qc: boolean;
  can_work: boolean;
  can_open_review_panel: boolean;
  can_approve_and_assign: boolean;
};

type MiniAppPhoneLoginRaw = {
  access: string;
  refresh: string;
  role_slugs: string[];
  roles: string[];
  permissions: TicketFlowPermissions;
  user: CurrentUserRaw;
};

export type MiniAppPhoneLogin = Omit<MiniAppPhoneLoginRaw, "user"> & {
  user: CurrentUser;
};

export type MiniAppAuthSuccess = MiniAppPhoneLogin;

type MiniAppTmaVerifyRaw = Partial<MiniAppPhoneLoginRaw> & {
  valid?: boolean;
  user_exists?: boolean;
  needs_access_request?: boolean;
  telegram_id?: number | null;
  username?: string | null;
};

export type MiniAppTmaVerifyResult =
  | ({
      valid: true;
      user_exists: true;
    } & MiniAppAuthSuccess)
  | {
      valid: true;
      user_exists: false;
      needs_access_request: boolean;
      telegram_id: number | null;
      username: string | null;
      role_slugs: string[];
      roles: string[];
      permissions: TicketFlowPermissions;
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

type ManagedUserRaw = {
  id: number;
  first_name: string;
  last_name: string | null;
  username: string;
  phone: string | null;
  level: number;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  last_login: string | null;
  roles: UserRole[];
  telegram: TelegramProfile | null;
  created_at: string;
  updated_at: string;
};

export type ManagedUser = Omit<ManagedUserRaw, "roles"> & {
  roles: string[];
  role_slugs: string[];
  display_name: string;
};

export type RoleOption = UserRole;

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

export type RulesConfig = {
  ticket_xp: {
    base_divisor: number;
    first_pass_bonus: number;
    qc_status_update_xp: number;
    flag_green_max_minutes: number;
    flag_yellow_max_minutes: number;
  };
  attendance: {
    on_time_xp: number;
    grace_xp: number;
    late_xp: number;
    on_time_cutoff: string;
    grace_cutoff: string;
    timezone: string;
  };
  work_session: {
    daily_pause_limit_minutes: number;
    timezone: string;
  };
  progression?: {
    level_thresholds?: Record<string, number>;
    weekly_coupon_amount?: number;
    weekly_target_xp?: number;
  };
};

export type RulesConfigState = {
  active_version: number;
  cache_key: string;
  checksum: string;
  config: RulesConfig;
  updated_at: string;
};

export type RulesConfigVersionAction = "bootstrap" | "update" | "rollback";

export type RulesConfigVersion = {
  id: number;
  version: number;
  action: RulesConfigVersionAction;
  reason: string | null;
  checksum: string;
  source_version: number | null;
  source_version_number: number | null;
  created_by: number | null;
  created_by_username: string | null;
  diff: Record<string, unknown>;
  config: RulesConfig;
  created_at: string;
};

export type LevelControlOverviewRow = {
  user_id: number;
  display_name: string;
  username: string;
  current_level: number;
  suggested_level_by_xp: number;
  range_xp: number;
  cumulative_xp: number;
  weekly_target_xp: number;
  range_target_xp: number;
  meets_target: boolean;
  warning_active: boolean;
  suggested_warning: boolean;
  suggested_reset_to_l1: boolean;
  latest_history_event: {
    id: number;
    source: string;
    status: string;
    previous_level: number;
    new_level: number;
    warning_active_before: boolean;
    warning_active_after: boolean;
    week_start: string | null;
    week_end: string | null;
    actor_id: number | null;
    actor_username: string | null;
    created_at: string;
    note: string | null;
  } | null;
  latest_weekly_evaluation: {
    id: number;
    week_start: string;
    week_end: string;
    raw_xp: number;
    weekly_xp: number;
    weekly_target_xp: number;
    status: string;
    warning_active_after: boolean;
    evaluated_by_id: number | null;
    evaluated_by_username: string | null;
    created_at: string;
  } | null;
};

export type LevelControlOverview = {
  date_from: string;
  date_to: string;
  range_days: number;
  weekly_target_xp: number;
  range_target_xp: number;
  rules_version: number;
  rows: LevelControlOverviewRow[];
  summary: {
    technicians_total: number;
    met_target: number;
    below_target: number;
    warning_active: number;
    suggested_warning: number;
    suggested_reset_to_l1: number;
  };
};

export type LevelControlUserHistory = {
  user: {
    id: number;
    display_name: string;
    username: string;
    is_active: boolean;
    level: number;
    warning_active_now: boolean;
  };
  range: {
    date_from: string;
    date_to: string;
  } | null;
  xp_history: Array<{
    id: number;
    amount: number;
    entry_type: string;
    reference: string;
    description: string | null;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
  weekly_evaluations: Array<{
    id: number;
    week_start: string;
    week_end: string;
    raw_xp: number;
    previous_level: number;
    new_level: number;
    is_level_up: boolean;
    target_status: string;
    weekly_xp: number;
    weekly_target_xp: number;
    met_weekly_target: boolean;
    warning_active_after: boolean;
    evaluated_by_id: number | null;
    evaluated_by_username: string | null;
    created_at: string;
  }>;
  level_history: Array<{
    id: number;
    source: string;
    status: string;
    previous_level: number;
    new_level: number;
    warning_active_before: boolean;
    warning_active_after: boolean;
    week_start: string | null;
    week_end: string | null;
    actor_id: number | null;
    actor_username: string | null;
    reference: string;
    note: string | null;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
};

export type ManualLevelSetResult = {
  user_id: number;
  display_name: string;
  username: string;
  previous_level: number;
  new_level: number;
  warning_active_before: boolean;
  warning_active_after: boolean;
  status: string;
  history_event_id: number;
  history_reference: string;
  history_created_at: string;
};

export type WeeklyLevelEvaluationSummary = {
  week_start: string;
  week_end: string;
  weekly_target_xp: number;
  evaluations_created: number;
  evaluations_skipped: number;
  level_ups: number;
  warnings_created: number;
  levels_reset_to_l1: number;
  coupon_events_created: number;
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

export type InventoryImportSummary = {
  categories_created: number;
  categories_updated: number;
  parts_created: number;
  parts_updated: number;
  items_created: number;
  items_updated: number;
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

export type PublicTechnicianLeaderboardMember = {
  user_id: number;
  name: string;
  username: string;
  level: number;
  rank: number;
  score: number;
  score_components: {
    tickets_done_points: number;
    xp_total_points: number;
    first_pass_points: number;
    quality_points: number;
    attendance_points: number;
    rework_penalty_points: number;
  };
  tickets_done_total: number;
  tickets_first_pass_total: number;
  tickets_rework_total: number;
  first_pass_rate_percent: number;
  tickets_closed_by_flag: {
    green: number;
    yellow: number;
    red: number;
  };
  xp_total: number;
  attendance_days_total: number;
  average_resolution_minutes: number;
  qc_fail_events_total: number;
};

export type PublicTechnicianLeaderboard = {
  generated_at: string;
  period?: {
    days: number;
    start_date: string;
    end_date: string;
  };
  summary: {
    technicians_total: number;
    tickets_done_total: number;
    tickets_first_pass_total: number;
    first_pass_rate_percent: number;
    xp_total: number;
    total_score: number;
  };
  members: PublicTechnicianLeaderboardMember[];
  weights: Record<string, number>;
};

export type PublicTechnicianDetail = {
  generated_at: string;
  leaderboard_position: {
    rank: number;
    total_technicians: number;
    better_than_percent: number;
    score: number;
    average_score: number;
  };
  profile: {
    user_id: number;
    name: string;
    username: string;
    level: number;
  };
  score_breakdown: {
    components: Record<string, number>;
    contribution_items: Array<{
      key: string;
      label: string;
      points: number;
      is_positive: boolean;
    }>;
    reasoning: {
      top_positive_factors: Array<{
        key: string;
        label: string;
        points: number;
        is_positive: boolean;
      }>;
      top_negative_factors: Array<{
        key: string;
        label: string;
        points: number;
        is_positive: boolean;
      }>;
    };
  };
  metrics: {
    tickets: {
      tickets_done_total: number;
      tickets_first_pass_total: number;
      tickets_rework_total: number;
      first_pass_rate_percent: number;
      tickets_closed_by_flag: {
        green: number;
        yellow: number;
        red: number;
      };
      average_resolution_minutes: number;
      status_counts: Record<string, number>;
      qc_pass_events_total: number;
      qc_fail_events_total: number;
    };
    xp: {
      xp_total: number;
      entry_type_breakdown: Array<{
        entry_type: string;
        total_amount: number;
        total_count: number;
      }>;
    };
    attendance: {
      attendance_days_total: number;
      attendance_completed_days: number;
      average_work_minutes_per_day: number;
    };
  };
  recent: {
    done_tickets: Array<{
      id: number;
      title: string | null;
      finished_at: string | null;
      total_duration: number;
      flag_color: string;
      xp_amount: number;
      is_manual: boolean;
    }>;
    xp_transactions: Array<{
      id: number;
      amount: number;
      entry_type: string;
      description: string | null;
      reference: string;
      payload: Record<string, unknown>;
      created_at: string;
    }>;
  };
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
  ordering?:
    | "created_at"
    | "-created_at"
    | "updated_at"
    | "-updated_at"
    | "serial_number"
    | "-serial_number"
    | "status"
    | "-status";
  page?: number;
  per_page?: number;
};

export type TicketListQuery = {
  q?: string;
  status?: TicketStatus;
  page?: number;
  per_page?: number;
};

export type ManagedUserQuery = {
  q?: string;
  role_slug?: string;
  is_active?: boolean;
  ordering?:
    | "created_at"
    | "-created_at"
    | "updated_at"
    | "-updated_at"
    | "username"
    | "-username"
    | "last_login"
    | "-last_login";
  page?: number;
  per_page?: number;
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

function parseFileNameFromDisposition(
  contentDisposition: string | null,
  fallback: string,
): string {
  if (!contentDisposition) {
    return fallback;
  }

  const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1]);
    } catch {
      // keep fallback behavior
    }
  }

  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  if (asciiMatch?.[1]) {
    return asciiMatch[1];
  }

  return fallback;
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

function extractPaginatedResults<TData>(
  payload: unknown,
  fallback: {
    page: number;
    per_page: number;
  },
): PaginatedResult<TData> {
  const unwrapped =
    payload && typeof payload === "object" && "data" in payload
      ? (payload as { data?: unknown }).data
      : payload;

  if (
    unwrapped &&
    typeof unwrapped === "object" &&
    "results" in unwrapped &&
    Array.isArray(unwrapped.results)
  ) {
    const envelope = unwrapped as Partial<PaginatedEnvelope<TData>>;
    const results = Array.isArray(envelope.results)
      ? (envelope.results as TData[])
      : [];
    const page =
      typeof envelope.page === "number" && envelope.page > 0
        ? envelope.page
        : fallback.page;
    const perPage =
      typeof envelope.per_page === "number" && envelope.per_page > 0
        ? envelope.per_page
        : fallback.per_page;
    const totalCount =
      typeof envelope.total_count === "number" && envelope.total_count >= 0
        ? envelope.total_count
        : results.length;
    const pageCount =
      typeof envelope.page_count === "number" && envelope.page_count > 0
        ? envelope.page_count
        : Math.max(1, Math.ceil(totalCount / Math.max(1, perPage)));

    return {
      results,
      pagination: {
        page,
        per_page: perPage,
        total_count: totalCount,
        page_count: pageCount,
      },
    };
  }

  const results = extractResults<TData>(unwrapped);
  const page = fallback.page;
  const perPage = Math.max(1, fallback.per_page);
  const totalCount = results.length;
  const pageCount = Math.max(1, Math.ceil(totalCount / perPage));
  return {
    results,
    pagination: {
      page,
      per_page: perPage,
      total_count: totalCount,
      page_count: pageCount,
    },
  };
}

function buildDisplayName(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  username: string,
): string {
  const fullName = `${firstName ?? ""} ${lastName ?? ""}`.trim();
  return fullName || username;
}

function mapUserOption(user: UserOptionRaw): UserOption {
  return {
    ...user,
    roles: user.roles.map((role) => role.name),
    role_slugs: user.roles.map((role) => role.slug),
    display_name: buildDisplayName(user.first_name, user.last_name, user.username),
  };
}

function mapCurrentUser(user: CurrentUserRaw): CurrentUser {
  const { roles, ...rest } = user;

  return {
    ...rest,
    roles: roles.map((role) => role.name),
    role_slugs: roles.map((role) => role.slug),
  };
}

function mapManagedUser(user: ManagedUserRaw): ManagedUser {
  return {
    ...user,
    roles: user.roles.map((role) => role.name),
    role_slugs: user.roles.map((role) => role.slug),
    display_name: buildDisplayName(user.first_name, user.last_name, user.username),
  };
}

function normalizeTicketFlowPermissions(
  value: unknown,
): TicketFlowPermissions {
  const source = value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
  const bool = (key: keyof TicketFlowPermissions): boolean => source[key] === true;
  return {
    can_create: bool("can_create"),
    can_review: bool("can_review"),
    can_assign: bool("can_assign"),
    can_manual_metrics: bool("can_manual_metrics"),
    can_qc: bool("can_qc"),
    can_work: bool("can_work"),
    can_open_review_panel: bool("can_open_review_panel"),
    can_approve_and_assign: bool("can_approve_and_assign"),
  };
}

async function apiRequest<TResponse>(
  path: string,
  options: InventoryRequestOptions = {},
): Promise<TResponse> {
  const { method = "GET", accessToken, body } = options;
  const isFormDataBody =
    typeof FormData !== "undefined" && body instanceof FormData;

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  if (body !== undefined && !isFormDataBody) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(buildApiUrl(path), {
    method,
    headers,
    body:
      body === undefined
        ? undefined
        : isFormDataBody
          ? body
          : JSON.stringify(body),
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

function parseMiniAppAuthSuccess(
  raw: MiniAppPhoneLoginRaw,
): MiniAppAuthSuccess {
  if (!raw?.access || !raw?.refresh) {
    throw new Error("Mini app login response is missing access/refresh tokens.");
  }
  return {
    ...raw,
    permissions: normalizeTicketFlowPermissions(raw.permissions),
    user: mapCurrentUser(raw.user),
  };
}

export async function loginMiniAppWithPhone(phone: string): Promise<MiniAppPhoneLogin> {
  const payload = await apiRequest<unknown>("auth/miniapp/phone-login/", {
    method: "POST",
    body: { phone },
  });
  const result = extractData<MiniAppPhoneLoginRaw>(payload);
  return parseMiniAppAuthSuccess(result);
}

export async function verifyMiniAppTelegramInitData(
  initData: string,
): Promise<MiniAppTmaVerifyResult> {
  const payload = await apiRequest<unknown>("auth/tma/verify/", {
    method: "POST",
    body: {
      init_data: initData,
    },
  });
  const result = extractData<MiniAppTmaVerifyRaw>(payload);
  const valid = result.valid === true;
  const userExists = result.user_exists === true;

  if (!valid) {
    throw new Error("Telegram mini app validation failed.");
  }

  if (!userExists) {
    return {
      valid: true,
      user_exists: false,
      needs_access_request: result.needs_access_request !== false,
      telegram_id:
        typeof result.telegram_id === "number" ? result.telegram_id : null,
      username: typeof result.username === "string" ? result.username : null,
      role_slugs: [],
      roles: [],
      permissions: normalizeTicketFlowPermissions(result.permissions),
    };
  }

  if (!result.access || !result.refresh || !result.user) {
    throw new Error("Telegram mini app response is missing token or user payload.");
  }

  return {
    valid: true,
    user_exists: true,
    ...parseMiniAppAuthSuccess({
      access: result.access,
      refresh: result.refresh,
      role_slugs: Array.isArray(result.role_slugs) ? result.role_slugs : [],
      roles: Array.isArray(result.roles) ? result.roles : [],
      permissions: normalizeTicketFlowPermissions(result.permissions),
      user: result.user,
    }),
  };
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  const payload = await apiRequest<unknown>("users/me/", { accessToken });
  const user = extractData<CurrentUserRaw>(payload);
  return mapCurrentUser(user);
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
  return users.map(mapUserOption);
}

export async function listRoleOptions(
  accessToken: string,
  query: { page?: number; per_page?: number } = {},
): Promise<RoleOption[]> {
  const payload = await apiRequest<unknown>(
    withQuery("users/roles/", {
      page: query.page,
      per_page: query.per_page ?? 100,
    }),
    { accessToken },
  );
  return extractResults<RoleOption>(payload);
}

export async function listManagedUsers(
  accessToken: string,
  query: ManagedUserQuery = {},
): Promise<ManagedUser[]> {
  const paginated = await listManagedUsersPage(accessToken, query);
  return paginated.results;
}

export async function listManagedUsersPage(
  accessToken: string,
  query: ManagedUserQuery = {},
): Promise<PaginatedResult<ManagedUser>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("users/management/", {
      q: query.q,
      role_slug: query.role_slug,
      is_active: query.is_active,
      ordering: query.ordering ?? "-created_at",
      page,
      per_page: perPage,
    }),
    { accessToken },
  );
  const paginated = extractPaginatedResults<ManagedUserRaw>(payload, {
    page,
    per_page: perPage,
  });
  return {
    ...paginated,
    results: paginated.results.map(mapManagedUser),
  };
}

export async function updateManagedUser(
  accessToken: string,
  id: number,
  body: Partial<{
    role_slugs: string[];
    is_active: boolean;
    level: number;
  }>,
): Promise<ManagedUser> {
  const payload = await apiRequest<unknown>(`users/management/${id}/`, {
    method: "PATCH",
    accessToken,
    body,
  });
  const updated = extractData<ManagedUserRaw>(payload);
  return mapManagedUser(updated);
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
  const paginated = await listInventoryItemsPage(accessToken, query);
  return paginated.results;
}

export async function listInventoryItemsPage(
  accessToken: string,
  query: InventoryItemQuery = {},
): Promise<PaginatedResult<InventoryItem>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("inventory/items/", {
      page,
      per_page: perPage,
      q: query.q,
      status: query.status,
      inventory: query.inventory,
      category: query.category,
      is_active: query.is_active,
      ordering: query.ordering,
    }),
    { accessToken },
  );
  return extractPaginatedResults<InventoryItem>(payload, {
    page,
    per_page: perPage,
  });
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

export async function exportInventoryWorkbookFile(
  accessToken: string,
): Promise<{ blob: Blob; fileName: string }> {
  const response = await fetch(buildApiUrl("inventory/export/"), {
    method: "GET",
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const payload = await parseJsonSafe(response);
    throw new Error(
      toErrorMessage(
        payload,
        `Request failed with status ${response.status} for inventory/export/`,
      ),
    );
  }

  const fileName = parseFileNameFromDisposition(
    response.headers.get("content-disposition"),
    "inventory_export.xlsx",
  );
  const blob = await response.blob();
  return { blob, fileName };
}

export async function importInventoryWorkbook(
  accessToken: string,
  file: File,
): Promise<InventoryImportSummary> {
  const formData = new FormData();
  formData.append("file", file);

  const payload = await apiRequest<unknown>("inventory/import/", {
    method: "POST",
    accessToken,
    body: formData,
  });
  return extractData<InventoryImportSummary>(payload);
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
  query: TicketListQuery = {},
): Promise<Ticket[]> {
  const paginated = await listTicketsPage(accessToken, query);
  return paginated.results;
}

export async function listTicketsPage(
  accessToken: string,
  query: TicketListQuery = {},
): Promise<PaginatedResult<Ticket>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("tickets/", {
      q: query.q,
      status: query.status,
      page,
      per_page: perPage,
    }),
    { accessToken },
  );
  return extractPaginatedResults<Ticket>(payload, {
    page,
    per_page: perPage,
  });
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

export async function getPublicTechnicianLeaderboard(
  query: { days?: number } = {},
): Promise<PublicTechnicianLeaderboard> {
  const payload = await apiRequest<unknown>(
    withQuery("analytics/public/leaderboard/", {
      days: query.days,
    }),
  );
  return extractData<PublicTechnicianLeaderboard>(payload);
}

export async function getPublicTechnicianDetail(
  userId: number,
): Promise<PublicTechnicianDetail> {
  const payload = await apiRequest<unknown>(
    `analytics/public/technicians/${userId}/`,
  );
  return extractData<PublicTechnicianDetail>(payload);
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
  const paginated = await listAccessRequestsPage(accessToken, query);
  return paginated.results;
}

export async function listAccessRequestsPage(
  accessToken: string,
  query: {
    status?: AccessRequestStatus;
    ordering?: "-created_at" | "created_at" | "-resolved_at" | "resolved_at";
    page?: number;
    per_page?: number;
  } = {},
): Promise<PaginatedResult<AccessRequest>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("users/access-requests/", {
      status: query.status,
      ordering: query.ordering,
      page,
      per_page: perPage,
    }),
    { accessToken },
  );
  return extractPaginatedResults<AccessRequest>(payload, {
    page,
    per_page: perPage,
  });
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
  const paginated = await listAttendanceRecordsPage(accessToken, query);
  return paginated.results;
}

export async function listAttendanceRecordsPage(
  accessToken: string,
  query: AttendanceRecordQuery = {},
): Promise<PaginatedResult<AttendanceRecord>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("attendance/records/", {
      work_date: query.work_date,
      user_id: query.user_id,
      technician_id: query.user_id,
      punctuality: query.punctuality,
      ordering: query.ordering ?? "user_id",
      page,
      per_page: perPage,
    }),
    { accessToken },
  );
  return extractPaginatedResults<AttendanceRecord>(payload, {
    page,
    per_page: perPage,
  });
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

export async function getRulesConfigState(
  accessToken: string,
): Promise<RulesConfigState> {
  const payload = await apiRequest<unknown>("rules/config/", { accessToken });
  return extractData<RulesConfigState>(payload);
}

export async function updateRulesConfigState(
  accessToken: string,
  body: {
    config: RulesConfig;
    reason?: string;
  },
): Promise<RulesConfigState> {
  const payload = await apiRequest<unknown>("rules/config/", {
    method: "PUT",
    accessToken,
    body,
  });
  return extractData<RulesConfigState>(payload);
}

export async function listRulesConfigHistory(
  accessToken: string,
  query: {
    page?: number;
    per_page?: number;
    ordering?: "version" | "-version" | "created_at" | "-created_at";
  } = {},
): Promise<RulesConfigVersion[]> {
  const paginated = await listRulesConfigHistoryPage(accessToken, query);
  return paginated.results;
}

export async function listRulesConfigHistoryPage(
  accessToken: string,
  query: {
    page?: number;
    per_page?: number;
    ordering?: "version" | "-version" | "created_at" | "-created_at";
  } = {},
): Promise<PaginatedResult<RulesConfigVersion>> {
  const page = query.page ?? 1;
  const perPage = query.per_page ?? 50;
  const payload = await apiRequest<unknown>(
    withQuery("rules/config/history/", {
      page,
      per_page: perPage,
      ordering: query.ordering ?? "-version",
    }),
    { accessToken },
  );
  return extractPaginatedResults<RulesConfigVersion>(payload, {
    page,
    per_page: perPage,
  });
}

export async function rollbackRulesConfigState(
  accessToken: string,
  body: {
    target_version: number;
    reason?: string;
  },
): Promise<RulesConfigState> {
  const payload = await apiRequest<unknown>("rules/config/rollback/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<RulesConfigState>(payload);
}

export async function getLevelControlOverview(
  accessToken: string,
  query: { date_from?: string; date_to?: string } = {},
): Promise<LevelControlOverview> {
  const payload = await apiRequest<unknown>(
    withQuery("xp/levels/overview/", {
      date_from: query.date_from,
      date_to: query.date_to,
    }),
    { accessToken },
  );
  return extractData<LevelControlOverview>(payload);
}

export async function getLevelControlUserHistory(
  accessToken: string,
  userId: number,
  query: { date_from?: string; date_to?: string; limit?: number } = {},
): Promise<LevelControlUserHistory> {
  const payload = await apiRequest<unknown>(
    withQuery(`xp/levels/users/${userId}/history/`, {
      date_from: query.date_from,
      date_to: query.date_to,
      limit: query.limit ?? 500,
    }),
    { accessToken },
  );
  return extractData<LevelControlUserHistory>(payload);
}

export async function setLevelControlUserLevel(
  accessToken: string,
  userId: number,
  body: {
    level: number;
    note?: string;
    clear_warning?: boolean;
    warning_active?: boolean;
  },
): Promise<ManualLevelSetResult> {
  const payload = await apiRequest<unknown>(
    `xp/levels/users/${userId}/set-level/`,
    {
      method: "POST",
      accessToken,
      body,
    },
  );
  return extractData<ManualLevelSetResult>(payload);
}

export async function runWeeklyLevelEvaluation(
  accessToken: string,
  body: { week_start?: string } = {},
): Promise<WeeklyLevelEvaluationSummary> {
  const payload = await apiRequest<unknown>("xp/levels/evaluate/", {
    method: "POST",
    accessToken,
    body,
  });
  return extractData<WeeklyLevelEvaluationSummary>(payload);
}
