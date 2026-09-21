const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    let msg: any = text;
    try {
      const j = JSON.parse(text);
      msg = j.detail ?? j.message ?? text;
    } catch {
      /* ignore */
    }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json();
}

export type AuthUser = {
  email: string;
  name: string;
  is_admin: boolean;
  sent_today: number;
  daily_limit: number;
};

export const api = {
  health: () => req<{ ok: boolean; turso: boolean }>("/api/health"),
  meta: () =>
    req<{ presets: Record<string, any>; var_tags: { label: string; tag: string }[]; gmail_daily_limit: number }>(
      "/api/meta"
    ),
  login: (email: string, password: string, display_name?: string) =>
    req<AuthUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  topics: () => req<any[]>("/api/topics"),
  createTopic: (name: string, created_by: string) =>
    req<{ id: number }>("/api/topics", {
      method: "POST",
      body: JSON.stringify({ name, created_by, default_preset: "기본형" }),
    }),
  setTopicPreset: (id: number, preset: string) =>
    req(`/api/topics/${id}/preset?preset=${encodeURIComponent(preset)}`, { method: "PATCH" }),
  templates: (owner: string) => req<any[]>(`/api/templates?owner_email=${encodeURIComponent(owner)}`),
  saveTemplate: (body: any) => req("/api/templates", { method: "POST", body: JSON.stringify(body) }),
  getTemplate: (owner: string, name: string) =>
    req<any>(`/api/templates/${encodeURIComponent(name)}?owner_email=${encodeURIComponent(owner)}`),
  preview: (body: any) =>
    req<{ subject: string; html: string }>("/api/preview", { method: "POST", body: JSON.stringify(body) }),
  upsertRecipients: (items: any[]) =>
    req<{ id_map: Record<string, number>; count: number }>("/api/recipients/upsert", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  topicStatus: (topicId: number) => req<Record<string, any>>(`/api/topics/${topicId}/status`),
  topicLogs: (topicId: number, senderEmail?: string) => {
    const q = senderEmail ? `?sender_email=${encodeURIComponent(senderEmail)}` : "";
    return req<any[]>(`/api/topics/${topicId}/logs${q}`);
  },
  send: (body: any) =>
    req<{ sent: number; skipped: number; failed: number; errors: string[] }>("/api/send", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stats: () => req<{ recipients: number; sent_today: Record<string, number>; logs_lite: any[] }>("/api/stats"),
  senders: () => req<any[]>("/api/senders"),
  upsertSender: (body: {
    email: string;
    display_name?: string;
    is_admin?: boolean;
    is_active?: boolean;
  }) => req("/api/senders", { method: "POST", body: JSON.stringify(body) }),
  getPrefs: (email: string) => req<any>(`/api/prefs?email=${encodeURIComponent(email)}`),
  savePrefs: (email: string, prefs: any) =>
    req("/api/prefs", { method: "POST", body: JSON.stringify({ email, prefs }) }),
};

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const s = String(reader.result || "");
      const i = s.indexOf(",");
      resolve(i >= 0 ? s.slice(i + 1) : s);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
