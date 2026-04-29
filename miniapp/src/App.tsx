import { useEffect, useMemo, useState } from "react";
import {
  downloadDocumentFile,
  loadMiniAppData,
  type MiniAppData,
  type MiniAppDocument,
  type MiniAppGroup,
  type MiniAppProject
} from "./api";

type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  close: () => void;
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id?: number;
      username?: string;
      first_name?: string;
      last_name?: string;
    };
  };
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

type TabKey = "home" | "projects" | "docs" | "groups" | "subscription" | "demo";
type ApiStatus = "loading" | "live" | "demo" | "error";

const tabs: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: "home", label: "Главная", icon: "⌁" },
  { key: "projects", label: "Проекты", icon: "◩" },
  { key: "docs", label: "Документы", icon: "□" },
  { key: "groups", label: "Группы", icon: "◉" },
  { key: "subscription", label: "Подписка", icon: "◇" },
  { key: "demo", label: "Демо", icon: "◎" }
];

const fallbackData: MiniAppData = {
  ok: true,
  demo: true,
  user: {
    telegram_id: 0,
    username: "demo",
    first_name: "Demo",
    last_name: null
  },
  subscription: {
    plan: "free",
    plan_name: "Free",
    expires_text: "—"
  },
  limits: {
    text: { used: 3, limit: 20, remaining: 17 },
    voice: { used: 1, limit: 3, remaining: 2 }
  },
  stats: {
    projects_total: 2,
    messages_total: 14,
    documents_generated: 2,
    documents_today: 1,
    feedback_total: 3,
    payments_paid: 0,
    stars_paid: 0,
    groups_total: 2,
    groups_memory_enabled: 1,
    group_messages_today: 12
  },
  projects: [
    {
      id: 1,
      title: "Запуск Telegram-бота",
      description: "Mini App, подписка Stars, документы, проекты, HTTPS API и подготовка к первым пользователям.",
      status: "active",
      status_label: "Активен",
      notes_count: 3,
      last_note_preview: "Следующий шаг — карточки проектов и история документов.",
      created_at: "demo",
      updated_at: "demo",
      updated_text: "сегодня"
    },
    {
      id: 2,
      title: "Клиент Иванова",
      description: "Бюджет 450 000 ₽, дедлайн 20 мая, нужно подготовить КП и не выйти за бюджет.",
      status: "active",
      status_label: "Активен",
      notes_count: 1,
      last_note_preview: "Клиент просит показать поэтапный план работ.",
      created_at: "demo",
      updated_at: "demo",
      updated_text: "вчера"
    }
  ],
  documents: [
    {
      id: 1,
      doc_type: "commercial_offer",
      doc_type_label: "КП",
      title: "КП на настройку рекламы",
      status: "created",
      status_label: "Готов",
      has_docx: true,
      has_pdf: true,
      docx_size_bytes: 38400,
      pdf_size_bytes: 124000,
      docx_size_text: "38 КБ",
      pdf_size_text: "121 КБ",
      download_docx_url: "/api/documents/1/download?format=docx",
      download_pdf_url: "/api/documents/1/download?format=pdf",
      created_at: "demo",
      created_text: "сегодня",
      updated_at: "demo"
    },
    {
      id: 2,
      doc_type: "work_plan",
      doc_type_label: "План работ",
      title: "План запуска Mini App",
      status: "created",
      status_label: "Готов",
      has_docx: true,
      has_pdf: false,
      docx_size_bytes: 42000,
      pdf_size_bytes: 0,
      docx_size_text: "41 КБ",
      pdf_size_text: "—",
      download_docx_url: "/api/documents/2/download?format=docx",
      download_pdf_url: null,
      created_at: "demo",
      created_text: "вчера",
      updated_at: "demo"
    }
  ],
  groups: [
    {
      chat_id: -1001111111111,
      title: "Команда запуска",
      username: null,
      memory_enabled: true,
      memory_status_label: "Память включена",
      messages_total: 48,
      messages_today: 12,
      messages_last_hour: 4,
      created_at: "demo",
      updated_at: "demo",
      updated_text: "сегодня"
    },
    {
      chat_id: -1002222222222,
      title: "Клиентский проект",
      username: null,
      memory_enabled: false,
      memory_status_label: "Память выключена",
      messages_total: 9,
      messages_today: 0,
      messages_last_hour: 0,
      created_at: "demo",
      updated_at: "demo",
      updated_text: "вчера"
    }
  ]
};

function getWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

function sendToBot(text: string) {
  const encoded = encodeURIComponent(text);
  window.location.href = `https://t.me/user_managerGPT_Bot?start=${encoded}`;
}

function formatLimit(value: number): string {
  if (value >= 999999999) {
    return "∞";
  }

  return String(value);
}

function statusLabel(status: ApiStatus): string {
  if (status === "live") {
    return "Синхронизировано";
  }

  if (status === "demo") {
    return "Демо-режим";
  }

  if (status === "error") {
    return "Нет связи";
  }

  return "Загрузка";
}

function statusDescription(status: ApiStatus): string {
  if (status === "live") {
    return "Кабинет получает реальные данные из backend API.";
  }

  if (status === "demo") {
    return "Сейчас показаны демонстрационные данные. Подключи backend API для live-режима.";
  }

  if (status === "error") {
    return "Mini App открыт, но backend API сейчас недоступен. Проверь туннель или сервер.";
  }

  return "Собираю данные кабинета.";
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("home");
  const [data, setData] = useState<MiniAppData>(fallbackData);
  const [loading, setLoading] = useState(true);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("loading");

  const webApp = useMemo(() => getWebApp(), []);
  const telegramUser = webApp?.initDataUnsafe?.user;

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
  }, [webApp]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const loaded = await loadMiniAppData(webApp?.initData || "");

        if (cancelled) {
          return;
        }

        if (loaded) {
          setData(loaded);
          setApiStatus(loaded.demo ? "demo" : "live");
        } else {
          setData({
            ...fallbackData,
            user: {
              ...fallbackData.user,
              first_name: telegramUser?.first_name || fallbackData.user.first_name,
              username: telegramUser?.username || fallbackData.user.username
            }
          });
          setApiStatus("demo");
        }
      } catch {
        if (!cancelled) {
          setApiStatus("error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [telegramUser?.first_name, telegramUser?.username, webApp?.initData]);

  const firstName = data.user.first_name || telegramUser?.first_name || "Александр";

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-topline">Telegram Mini App</div>
        <h1>Менеджер ИИ</h1>
        <p>Рабочий кабинет для проектов, документов, подписки и быстрых AI-сценариев.</p>

        <div className="hero-actions">
          <div className="user-chip">
            <span className={apiStatus === "live" ? "pulse" : apiStatus === "error" ? "pulse danger-pulse" : "pulse muted-pulse"} />
            <span>{firstName}</span>
            <span className="muted">· {statusLabel(apiStatus)}</span>
          </div>

          <button className="ghost-button" type="button" onClick={() => sendToBot("assistant")}>
            Открыть чат
          </button>
        </div>
      </section>

      <nav className="tabs" aria-label="Mini App navigation">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? "tab active" : "tab"}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      <section className="content-card">
        {loading && <div className="loading">Загружаю данные кабинета…</div>}

        {!loading && activeTab === "home" && <HomeScreen data={data} apiStatus={apiStatus} />}
        {!loading && activeTab === "projects" && <ProjectsScreen data={data} />}
        {!loading && activeTab === "docs" && <DocumentsScreen data={data} initData={webApp?.initData || ""} />}
        {!loading && activeTab === "groups" && <GroupsScreen data={data} />}
        {!loading && activeTab === "subscription" && <SubscriptionScreen data={data} />}
        {!loading && activeTab === "demo" && <DemoScreen />}
      </section>
    </main>
  );
}

function HomeScreen({ data, apiStatus }: { data: MiniAppData; apiStatus: ApiStatus }) {
  const textLimit = formatLimit(data.limits.text.limit);
  const voiceLimit = formatLimit(data.limits.voice.limit);

  return (
    <>
      <div className="section-heading">
        <span>⌁</span>
        <h2>Рабочий центр</h2>
      </div>

      <StatusPanel status={apiStatus} />

      <div className="today-grid">
        <TodayCard label="Тариф" value={data.subscription.plan_name} caption={`до ${data.subscription.expires_text}`} />
        <TodayCard label="Текст" value={`${data.limits.text.used}/${textLimit}`} caption="лимит сегодня" />
        <TodayCard label="Голос" value={`${data.limits.voice.used}/${voiceLimit}`} caption="лимит сегодня" />
        <TodayCard label="Документы" value={String(data.stats.documents_today || 0)} caption="создано сегодня" />
        <TodayCard label="Группы" value={String(data.stats.groups_total || 0)} caption="AI-секретарь" />
      </div>

      <section className="premium-panel">
        <div>
          <span className="panel-kicker">Быстрый старт</span>
          <h3>Что сделать сейчас?</h3>
          <p>Выбери сценарий — Mini App отправит тебя в нужную точку бота.</p>
        </div>

        <div className="quick-grid">
          <QuickAction title="Спросить ассистента" text="Любая задача, идея или вопрос." onClick={() => sendToBot("assistant")} />
          <QuickAction title="Создать КП" text="Коммерческое предложение в DOCX/PDF." onClick={() => sendToBot("documents")} />
          <QuickAction title="Открыть проекты" text="Память по клиентам, срокам и договорённостям." onClick={() => sendToBot("projects")} />
          <QuickAction title="Усилить тариф" text="Больше лимитов и рабочих возможностей." onClick={() => sendToBot("subscription")} />
        </div>
      </section>

      <section className="summary-strip">
        <div>
          <strong>{data.stats.projects_total}</strong>
          <span>проектов</span>
        </div>
        <div>
          <strong>{data.stats.documents_generated}</strong>
          <span>документов</span>
        </div>
        <div>
          <strong>{data.stats.messages_total}</strong>
          <span>сообщений</span>
        </div>
      </section>
    </>
  );
}

function StatusPanel({ status }: { status: ApiStatus }) {
  return (
    <article className={`status-panel status-${status}`}>
      <div>
        <span>{statusLabel(status)}</span>
        <p>{statusDescription(status)}</p>
      </div>
    </article>
  );
}

function ProjectsScreen({ data }: { data: MiniAppData }) {
  const projects = data.latest_projects || data.projects || [];

  return (
    <>
      <div className="section-heading">
        <span>◩</span>
        <h2>Проекты</h2>
      </div>

      <p className="lead">Рабочая память: клиенты, сроки, бюджеты, договорённости и следующий шаг.</p>

      <div className="project-actions">
        <button type="button" onClick={() => sendToBot("projects")}>
          Открыть проекты
        </button>
        <button type="button" onClick={() => sendToBot("new_project")}>
          Создать проект
        </button>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon="◩"
          title="Проектов пока нет"
          text="Создай первый проект, чтобы бот начал помнить клиентов, сроки, бюджеты и договорённости."
          button="Создать первый проект"
          onClick={() => sendToBot("new_project")}
        />
      ) : (
        <div className="project-grid">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </>
  );
}

function DocumentsScreen({ data, initData }: { data: MiniAppData; initData: string }) {
  const documents = data.latest_documents || data.documents || [];

  return (
    <>
      <div className="section-heading">
        <span>□</span>
        <h2>Документы</h2>
      </div>

      <p className="lead">
        Создано документов: <strong>{data.stats.documents_generated}</strong>. Сегодня:{" "}
        <strong>{data.stats.documents_today || 0}</strong>.
      </p>

      <div className="document-actions">
        <button type="button" onClick={() => sendToBot("documents")}>
          Создать документ
        </button>
        <button type="button" onClick={() => sendToBot("demo_document")}>
          Демо документа
        </button>
      </div>

      {documents.length === 0 ? (
        <EmptyState
          icon="□"
          title="Документов пока нет"
          text="Собери первый файл: КП, план работ, резюме встречи или чек-лист. История появится здесь автоматически."
          button="Создать первый документ"
          onClick={() => sendToBot("documents")}
        />
      ) : (
        <div className="document-history">
          {documents.map((document) => (
            <DocumentCard key={document.id} document={document} initData={initData} />
          ))}
        </div>
      )}
    </>
  );
}


function GroupsScreen({ data }: { data: MiniAppData }) {
  const groups = data.latest_groups || data.groups || [];
  const enabledCount = groups.filter((group) => group.memory_enabled).length;
  const todayMessages = groups.reduce((sum, group) => sum + (group.messages_today || 0), 0);

  return (
    <>
      <div className="section-heading">
        <span>◉</span>
        <h2>Группы</h2>
      </div>

      <p className="lead">
        AI-секретарь для Telegram-групп: память, сводки, web-поиск и документы по переписке.
      </p>

      <div className="group-summary">
        <TodayCard label="Групп" value={String(groups.length)} caption="в кабинете" />
        <TodayCard label="Память" value={`${enabledCount}/${groups.length || 0}`} caption="включена" />
        <TodayCard label="Сегодня" value={String(todayMessages)} caption="сообщений" />
      </div>

      <div className="group-actions">
        <button type="button" onClick={() => sendToBot("grouphelp")}>
          Инструкция
        </button>
        <button type="button" onClick={() => sendToBot("assistant")}>
          Открыть чат
        </button>
      </div>

      {groups.length === 0 ? (
        <EmptyState
          icon="◉"
          title="Групп пока нет"
          text="Добавь бота в Telegram-группу, включи /group_on и напиши несколько сообщений. После этого группа появится здесь."
          button="Как включить"
          onClick={() => sendToBot("grouphelp")}
        />
      ) : (
        <div className="group-grid">
          {groups.map((group) => (
            <GroupCard key={group.chat_id} group={group} />
          ))}
        </div>
      )}
    </>
  );
}

function GroupCard({ group }: { group: MiniAppGroup }) {
  const updatedText = group.updated_text || group.updated_at || "—";
  const memoryClass = group.memory_enabled ? "group-memory enabled" : "group-memory disabled";

  return (
    <article className="group-card">
      <div className="group-card-header">
        <div>
          <div className={memoryClass}>{group.memory_status_label}</div>
          <h3>{group.title}</h3>
        </div>
        <span>{updatedText}</span>
      </div>

      <div className="group-metrics">
        <div>
          <strong>{group.messages_last_hour}</strong>
          <span>за 60 минут</span>
        </div>
        <div>
          <strong>{group.messages_today}</strong>
          <span>сегодня</span>
        </div>
        <div>
          <strong>{group.messages_total}</strong>
          <span>всего</span>
        </div>
      </div>

      <div className="group-hint">
        <span>Команды</span>
        <strong>/group_status · /group_on · /group_clear</strong>
      </div>

      <div className="group-card-actions">
        <button type="button" onClick={() => sendToBot("grouphelp")}>
          Настроить
        </button>
        <button type="button" onClick={() => sendToBot("documents")}>
          Документы
        </button>
      </div>
    </article>
  );
}

function SubscriptionScreen({ data }: { data: MiniAppData }) {
  return (
    <>
      <div className="section-heading">
        <span>◇</span>
        <h2>Подписка</h2>
      </div>

      <section className="subscription-hero">
        <span className="panel-kicker">Текущий тариф</span>
        <h3>{data.subscription.plan_name}</h3>
        <p>
          Действует до: <strong>{data.subscription.expires_text}</strong>
        </p>
      </section>

      <div className="plans">
        <Plan title="Pro" price="299 ⭐" items={["больше запросов", "больше голосовых", "DOCX/PDF", "проекты"]} />
        <Plan
          title="Business"
          price="999 ⭐"
          items={["максимальные лимиты", "активная работа", "документы", "будущие шаблоны"]}
        />
      </div>

      <button className="primary-button" onClick={() => sendToBot("subscription")} type="button">
        Открыть оплату
      </button>
    </>
  );
}

function DemoScreen() {
  return (
    <>
      <div className="section-heading">
        <span>◎</span>
        <h2>Демо</h2>
      </div>

      <p className="lead">Быстрый маршрут для первого пользователя: понять, зачем нужен бот, без длинных инструкций.</p>

      <div className="feature-list">
        <Feature title="Разобрать хаос" text="Сырые мысли → структура, риски, следующий шаг." />
        <Feature title="Сохранить проект" text="Клиент, бюджет, сроки, заметки — в рабочую память." />
        <Feature title="Собрать документ" text="Из вводных → DOCX/PDF файл." />
      </div>

      <button className="primary-button" onClick={() => sendToBot("demo")} type="button">
        Запустить демо
      </button>
    </>
  );
}

function TodayCard({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <article className="today-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{caption}</small>
    </article>
  );
}

function QuickAction({ title, text, onClick }: { title: string; text: string; onClick: () => void }) {
  return (
    <button className="quick-action" type="button" onClick={onClick}>
      <strong>{title}</strong>
      <span>{text}</span>
    </button>
  );
}

function ProjectCard({ project }: { project: MiniAppProject }) {
  const notesCount = project.notes_count || 0;
  const updatedText = project.updated_text || project.updated_at || "—";
  const lastNote = project.last_note_preview || "";

  return (
    <article className="project-card">
      <div className="project-card-header">
        <div>
          <div className="project-status">{project.status_label || project.status || "Проект"}</div>
          <h3>{project.title}</h3>
        </div>
        <span className="project-date">{updatedText}</span>
      </div>

      <p>{project.description}</p>

      {lastNote && (
        <div className="project-note">
          <span>Последняя заметка</span>
          <strong>{lastNote}</strong>
        </div>
      )}

      <div className="project-meta">
        <span>{notesCount} заметок</span>
        <span>ID #{project.id}</span>
      </div>

      <div className="project-card-actions">
        <button type="button" onClick={() => sendToBot(`project_${project.id}`)}>
          Открыть
        </button>
        <button type="button" onClick={() => sendToBot(`project_doc_${project.id}`)}>
          Документ
        </button>
      </div>
    </article>
  );
}

function DocumentCard({ document, initData }: { document: MiniAppDocument; initData: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorText, setErrorText] = useState("");

  async function handleDownload(format: "docx" | "pdf") {
    setStatus("loading");
    setErrorText("");

    try {
      await downloadDocumentFile(document.id, format, initData, document.title);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setErrorText(error instanceof Error ? error.message : "Не удалось скачать файл.");
    }
  }

  return (
    <article className="history-document-card">
      <div className="history-document-top">
        <div>
          <div className="document-badge">{document.doc_type_label}</div>
          <h3>{document.title}</h3>
        </div>
        <span>{document.created_text}</span>
      </div>

      <div className="document-file-row">
        <span className={document.has_docx ? "file-pill active" : "file-pill"}>DOCX · {document.docx_size_text}</span>
        <span className={document.has_pdf ? "file-pill active" : "file-pill"}>PDF · {document.pdf_size_text}</span>
      </div>

      <div className="document-status-row">
        <span>{document.status_label || document.status}</span>
        <span>ID #{document.id}</span>
      </div>

      {status === "error" && <div className="download-error">{errorText}</div>}

      <div className="document-card-actions download-actions">
        <button type="button" disabled={!document.has_docx || status === "loading"} onClick={() => handleDownload("docx")}>
          {status === "loading" ? "..." : "DOCX"}
        </button>
        <button type="button" disabled={!document.has_pdf || status === "loading"} onClick={() => handleDownload("pdf")}>
          {status === "loading" ? "..." : "PDF"}
        </button>
      </div>
    </article>
  );
}

function EmptyState({
  icon,
  title,
  text,
  button,
  onClick
}: {
  icon: string;
  title: string;
  text: string;
  button: string;
  onClick: () => void;
}) {
  return (
    <article className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{text}</p>
      <button type="button" onClick={onClick}>
        {button}
      </button>
    </article>
  );
}

function Feature({ title, text }: { title: string; text: string }) {
  return (
    <article className="feature">
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}

function Plan({ title, price, items }: { title: string; price: string; items: string[] }) {
  return (
    <article className="plan">
      <div className="plan-header">
        <h3>{title}</h3>
        <strong>{price}</strong>
      </div>
      <ul>
        {items.map((item) => (
          <li key={item}>— {item}</li>
        ))}
      </ul>
    </article>
  );
}

export default App;
