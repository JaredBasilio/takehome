export interface User {
  user_id: string;
  name: string;
  role: "agent" | "team_lead" | "head_of_support";
  agent_id: string | null;
  manages_queue_ids: string[] | null;
}

export interface NotificationScope {
  agent_ids?: string[] | null;
  queue_ids?: string[] | null;
}

export interface NotificationConfig {
  config_id: string;
  user_id: string;
  assigned_to_user_ids: string[];
  label: string;
  event_type: string;
  field: string;
  comparator: string;
  value: unknown;
  value_mode: "absolute" | "pct_of_sla";
  scope: NotificationScope | null;
  filter: Record<string, unknown> | null;
  is_shared: boolean;
}

export interface Notification {
  notification_id: string;
  user_id: string;
  config_id: string;
  config_label: string;
  triggered_by_event_id: string;
  triggered_at: string;
  last_seen_at: string;
  message: string;
  read: boolean;
  is_shared: boolean;
}

export interface NotificationHistoryItem {
  notification_id: string;
  user_id: string;
  config_id: string;
  config_label: string;
  triggered_at: string;
  resolved_at: string;
  resolved_by_event_id: string;
  message: string;
  is_shared: boolean;
}

export interface ReplayStatus {
  is_running: boolean;
  current_index: number;
  total_events: number;
  current_ts: string | null;
  speed: string;
}

export interface CreateConfigPayload {
  label: string;
  event_type: string;
  field: string;
  comparator: string;
  value: unknown;
  value_mode: "absolute" | "pct_of_sla";
  scope?: NotificationScope | null;
  filter?: Record<string, unknown> | null;
}

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  users: {
    list: () => get<User[]>("/users"),
  },
  notifications: {
    list: (userId: string) => get<Notification[]>(`/users/${userId}/notifications`),
    history: (userId: string) => get<NotificationHistoryItem[]>(`/users/${userId}/notifications/history`),
    markRead: (userId: string, notifId: string) =>
      patch<Notification>(`/users/${userId}/notifications/${notifId}/read`),
    dismiss: (userId: string, notifId: string) =>
      del<{ status: string }>(`/users/${userId}/notifications/${notifId}`),
  },
  configs: {
    list: (userId: string) => get<NotificationConfig[]>(`/users/${userId}/configs`),
    create: (userId: string, payload: CreateConfigPayload) =>
      post<NotificationConfig>(`/users/${userId}/configs`, payload),
    update: (userId: string, configId: string, payload: CreateConfigPayload) =>
      put<NotificationConfig>(`/users/${userId}/configs/${configId}`, payload),
    delete: (userId: string, configId: string) =>
      del<void>(`/users/${userId}/configs/${configId}`),
    push: (userId: string, configId: string) =>
      post<NotificationConfig>(`/users/${userId}/configs/${configId}/push`),
  },
  replay: {
    start: (speed: string) => post<ReplayStatus>("/replay/start", { speed }),
    reset: () => post<ReplayStatus>("/replay/reset"),
    status: () => get<ReplayStatus>("/replay/status"),
    events: () => get<Array<{ index: number; ts: string }>>("/replay/events"),
    seek: (index: number) => post<ReplayStatus>("/replay/seek", { index }),
  },
};
