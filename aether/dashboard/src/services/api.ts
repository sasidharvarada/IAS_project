/**
 * API Service Configuration
 *
 * User Management currently runs on BASE_URL directly.
 * Gateway v1 endpoints are available under /v1 for deployment orchestration.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

export const auth = {
  getToken: (): string | null => localStorage.getItem("aether_token"),
  setToken: (token: string) => localStorage.setItem("aether_token", token),
  clearToken: () => localStorage.removeItem("aether_token"),
  isLoggedIn: (): boolean => !!localStorage.getItem("aether_token"),
};

function authHeaders(): HeadersInit {
  const token = auth.getToken();
  return token
    ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

export const api = {
  login: async (credentials: { username: string; password: string }) => {
    const res = await fetch(`${BASE_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail ?? "Login failed");
    }
    return res.json();
  },

  register: async (userData: { username: string; password: string; email?: string; role?: string }) => {
    const res = await fetch(`${BASE_URL}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(err.detail ?? "Registration failed");
    }
    return res.json();
  },

  getMe: async () => {
    const res = await fetch(`${BASE_URL}/me`, { headers: authHeaders() });
    if (res.status === 401) throw new Error("UNAUTHORIZED");
    if (!res.ok) throw new Error("Failed to fetch user profile");
    return res.json();
  },

  getApps: async () => {
    const res = await fetch(`${BASE_URL}/v1/apps`);
    if (!res.ok) {
      throw new Error("Failed to fetch apps");
    }

    const payload = await res.json();
    return Array.isArray(payload) ? payload : payload.apps ?? [];
  },

  getAppDetails: async (id: string) => {
    const res = await fetch(`${BASE_URL}/v1/apps/${id}/overview`);
    if (!res.ok) {
      throw new Error("Failed to fetch app details");
    }
    return res.json();
  },

  validateApp: async (file: File): Promise<{ passed: boolean; errors: string[]; warnings: string[] }> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/validate`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Validation failed" }));
      throw new Error(err.detail ?? "Validation failed");
    }
    return res.json();
  },

  deployApp: async (
    file: File,
    onStatusUpdate: (status: string) => void,
    options?: { skipDependencyCheck?: boolean; skipSyntaxCheck?: boolean; secrets?: string }
  ) => {
    onStatusUpdate("Uploading ZIP to Gateway...");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("vm_pool_path", "infra/vm_pool.json");
    formData.append("ssh_user", "ubuntu");
    if (options?.skipDependencyCheck !== undefined) {
      formData.append("skip_dependency_check", String(options.skipDependencyCheck));
    }
    if (options?.skipSyntaxCheck !== undefined) {
      formData.append("skip_syntax_check", String(options.skipSyntaxCheck));
    }
    if (options?.secrets) {
      formData.append("secrets", options.secrets);
    }

    const res = await fetch(`${BASE_URL}/v1/apps/deploy/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Deploy failed" }));
      throw new Error(JSON.stringify(err.detail ?? err));
    }
    onStatusUpdate("Deployment pipeline completed.");
    return res.json();
  },

  deployFromSource: async (payload: {
    source: string;
    config_path?: string;
    vm_pool_path?: string;
    ssh_key?: string;
    ssh_user?: string;
  }) => {
    const res = await fetch(`${BASE_URL}/v1/apps/deploy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Deploy failed" }));
      throw new Error(JSON.stringify(err.detail ?? err));
    }
    return res.json();
  },

  appAction: async (id: string, action: "start" | "stop" | "restart" | "scale", replicas?: number) => {
    const res = await fetch(`${BASE_URL}/v1/apps/${id}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, replicas }),
    });
    if (!res.ok) throw new Error(`Failed to ${action} app`);
    return res.json();
  },

  runApp: async (id: string, payload: Record<string, unknown>) => {
    const res = await fetch(`${BASE_URL}/v1/apps/${id}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Run failed" }));
      throw new Error(err.detail ?? "Run failed");
    }
    return res.json();
  },

  deleteApp: async (id: string) => {
    const res = await fetch(`${BASE_URL}/v1/apps/${id}`, { method: "DELETE" });
    if (res.status === 404) {
      throw new Error("App not found");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Delete failed" }));
      throw new Error(err.detail ?? "Delete failed");
    }
    return res.json();
  },
};
