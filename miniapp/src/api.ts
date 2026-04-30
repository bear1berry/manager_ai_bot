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

export type MiniAppDocument = {
  id: number;
  doc_type: string;
  doc_type_label: string;
  title: string;
  status: string;
  status_label?: string;
  has_docx: boolean;
  has_pdf: boolean;
  docx_size_bytes: number;
  pdf_size_bytes: number;
  docx_size_text: string;
  pdf_size_text: string;
  download_docx_url?: string | null;
  download_pdf_url?: string | null;
  created_at: string;
  created_text: string;
  updated_at: string;
};


export type MiniAppGroup = {
  chat_id: number;
  title: string;
  username?: string | null;
  memory_enabled: boolean;
  memory_status_label: string;
  messages_total: number;
  messages_today: number;
  messages_last_hour: number;
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
    plan_badge?: string;
    positioning?: string;
    expires_at?: string | null;
    expires_text: string;
    unlocked_features?: string[];
    locked_features?: string[];
    recommended_upgrade?: string;
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
    documents_today?: number;
    feedback_total: number;
    payments_paid: number;
    stars_paid: number;
    groups_total?: number;
    groups_memory_enabled?: number;
    group_messages_today?: number;
  };
  projects: MiniAppProject[];
  latest_projects?: MiniAppProject[];
  documents?: MiniAppDocument[];
  latest_documents?: MiniAppDocument[];
  groups?: MiniAppGroup[];
  latest_groups?: MiniAppGroup[];
};

function apiBaseUrl(): string | null {
  const value = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return value ? value.replace(/\/$/, "") : null;
}

export async function loadMiniAppData(initData: string): Promise<MiniAppData | null> {
  const baseUrl = apiBaseUrl();

  if (!baseUrl) {
    return null;
  }

  const response = await fetch(`${baseUrl}/api/miniapp/me`, {
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

export async function downloadDocumentFile(
  documentId: number,
  format: "docx" | "pdf",
  initData: string,
  fallbackTitle: string
): Promise<void> {
  const baseUrl = apiBaseUrl();

  if (!baseUrl) {
    throw new Error("API base URL is not configured");
  }

  const response = await fetch(`${baseUrl}/api/documents/${documentId}/download?format=${format}`, {
    method: "GET",
    headers: {
      Authorization: `tma ${initData}`
    }
  });

  if (!response.ok) {
    let message = "Не удалось скачать файл.";

    try {
      const data = (await response.json()) as { message?: string };
      if (data.message) {
        message = data.message;
      }
    } catch {
      // ignore non-json error bodies
    }

    throw new Error(message);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = extractFilename(disposition) || safeFilename(`${fallbackTitle}.${format}`);

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

function extractFilename(contentDisposition: string): string | null {
  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    return decodeURIComponent(encodedMatch[1]);
  }

  const regularMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  if (regularMatch?.[1]) {
    return regularMatch[1];
  }

  return null;
}

function safeFilename(value: string): string {
  return value
    .replace(/[^\wа-яА-ЯёЁ.-]+/g, "_")
    .replace(/_+/g, "_")
    .slice(0, 96);
}
