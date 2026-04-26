export type MiniAppProject = {
  id: number;
  title: string;
  description: string;
  status: string;
  status_label?: string;
  notes_count?: number;
  last_note_preview?: string;
  created_at: string;
  updated_at: string;
  updated_text?: string;
};

export type MiniAppData = {
  ok: boolean;
  demo?: boolean;
  user: {
    telegram_id: number;
    username?: string | null;
    first_name?: string | null;
    last_name?: string | null;
  };
  subscription: {
    plan: string;
    plan_name: string;
    expires_at?: string | null;
    expires_text: string;
  };
  limits: {
    text: {
      used: number;
      limit: number;
      remaining: number;
    };
    voice: {
      used: number;
      limit: number;
      remaining: number;
    };
  };
  stats: {
    projects_total: number;
    messages_total: number;
    documents_generated: number;
    feedback_total: number;
    payments_paid: number;
    stars_paid: number;
  };
  projects: MiniAppProject[];
  latest_projects?: MiniAppProject[];
};

export async function loadMiniAppData(initData: string): Promise<MiniAppData | null> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;

  if (!apiBaseUrl) {
    return null;
  }

  const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/api/miniapp/me`, {
    method: "GET",
    headers: {
      Authorization: `tma ${initData}`,
      "Content-Type": "application/json"
    }
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return (await response.json()) as MiniAppData;
}
