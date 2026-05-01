import { useEffect, useMemo, useState } from "react";
import {
  downloadDocumentFile,
  loadMiniAppData,
  type MiniAppAdminDashboard,
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

type TabKey = "home" | "projects" | "docs" | "groups" | "subscription" | "admin" | "demo";
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
    plan_badge: "🆓 Free",
    positioning: "Стартовый контур: попробовать AI-менеджера, понять ценность и базовые сценарии.",
    expires_text: "—",
    unlocked_features: [
      "универсальный AI-ассистент",
      "режимы: клиент, хаос, план, продукт, стратег",
      "базовая работа с проектами",
      "Mini App как кабинет"
    ],
    locked_features: [
      "Deep Research",
      "DOCX/PDF документы",
      "документ из диалога",
      "документ из проекта",
      "групповые документы",
      "память Telegram-группы",
      "командные сценарии Business"
    ],
    recommended_upgrade:
      "💎 Рекомендуемый апгрейд: Pro\nСтоимость: 299 ⭐ / 30 дней.\n\nПочему Pro\n— открывает Deep Research;\n— включает DOCX/PDF;\n— превращает диалог в документ;\n— даёт больше лимитов;\n— подходит для личной рабочей продуктивности."
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
  admin_dashboard: null,
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
      documents_total: 2,
      documents: [
        {
          id: 1,
          doc_type: "meeting_summary",
          doc_type_label: "Резюме встречи",
          title: "Протокол обсуждения запуска",
          status: "created",
          status_label: "Готов",
          group_chat_id: -1001111111111,
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
          title: "План действий по группе",
          status: "created",
          status_label: "Готов",
          group_chat_id: -1001111111111,
          has_docx: true,
          has_pdf: false,
          docx_size_bytes: 42000,
          pdf_size_bytes: 0,
          docx_size_text: "41 КБ",
          pdf_size_text: "—",
          download_docx_url: "/api/documents/2/download?format=docx",
          download_pdf_url: null,
          created_at: "demo",
          created_text: "сегодня",
          updated_at: "demo"
        }
      ],
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
      documents_total: 0,
      documents: [],
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
  const availableTabs = useMemo(() => {
    if (!data.admin_dashboard?.is_admin) {
      return tabs;
    }

    const withoutAdmin = tabs.filter((tab) => tab.key !== "admin");
    return [
      ...withoutAdmin.slice(0, 5),
      { key: "admin" as TabKey, label: "Admin", icon: "▣" },
      ...withoutAdmin.slice(5)
    ];
  }, [data.admin_dashboard?.is_admin]);


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
        {availableTabs.map((tab) => (
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
        {!loading && activeTab === "groups" && <GroupsScreen data={data} initData={webApp?.initData || ""} />}
        {!loading && activeTab === "subscription" && <SubscriptionScreen data={data} />}
        {!loading && activeTab === "admin" && <AdminScreen dashboard={data.admin_dashboard || null} />}
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


function GroupsScreen({ data, initData }: { data: MiniAppData; initData: string }) {
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
            <GroupCard key={group.chat_id} group={group} initData={initData} />
          ))}
        </div>
      )}
    </>
  );
}

function GroupCard({ group, initData }: { group: MiniAppGroup; initData: string }) {
  const updatedText = group.updated_text || group.updated_at || "—";
  const memoryClass = group.memory_enabled ? "group-memory enabled" : "group-memory disabled";
  const documents = group.documents || [];

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

      <div className="group-documents-block">
        <div className="group-documents-head">
          <span>Документы группы</span>
          <strong>{documents.length}</strong>
        </div>

        {documents.length === 0 ? (
          <div className="group-documents-empty">
            Протоколов пока нет. В группе попроси: <strong>сделай протокол по переписке</strong>.
          </div>
        ) : (
          <div className="group-documents-list">
            {documents.map((document) => (
              <GroupDocumentMiniCard key={document.id} document={document} initData={initData} />
            ))}
          </div>
        )}
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

function GroupDocumentMiniCard({ document, initData }: { document: MiniAppDocument; initData: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");

  async function handleDownload(format: "docx" | "pdf") {
    setStatus("loading");

    try {
      await downloadDocumentFile(document.id, format, initData, document.title);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <article className="group-document-mini-card">
      <div>
        <span>{document.doc_type_label}</span>
        <strong>{document.title}</strong>
        <small>{document.created_text}</small>
      </div>

      <div className="group-document-actions">
        <button type="button" disabled={!document.has_docx || status === "loading"} onClick={() => handleDownload("docx")}>
          DOCX
        </button>
        <button type="button" disabled={!document.has_pdf || status === "loading"} onClick={() => handleDownload("pdf")}>
          PDF
        </button>
      </div>

      {status === "error" && <p className="group-document-error">Не удалось скачать файл.</p>}
    </article>
  );
}

function SubscriptionScreen({ data }: { data: MiniAppData }) {
  const textLimit = formatLimit(data.limits.text.limit);
  const voiceLimit = formatLimit(data.limits.voice.limit);
  const unlocked = data.subscription.unlocked_features || [];
  const locked = data.subscription.locked_features || [];
  const planBadge = data.subscription.plan_badge || data.subscription.plan_name;
  const positioning = data.subscription.positioning || "Рабочий AI-контур под твои задачи.";

  return (
    <>
      <div className="section-heading">
        <span>◇</span>
        <h2>Подписка</h2>
      </div>

      <section className="subscription-dashboard-hero">
        <div>
          <span className="panel-kicker">Текущий тариф</span>
          <h3>{planBadge}</h3>
          <p>{positioning}</p>
        </div>

        <div className="subscription-expiry">
          <span>Действует до</span>
          <strong>{data.subscription.expires_text}</strong>
        </div>
      </section>

      <div className="subscription-metrics-grid">
        <TodayCard label="Текст" value={`${data.limits.text.used}/${textLimit}`} caption={`осталось ${formatLimit(data.limits.text.remaining)}`} />
        <TodayCard label="Голос" value={`${data.limits.voice.used}/${voiceLimit}`} caption={`осталось ${formatLimit(data.limits.voice.remaining)}`} />
        <TodayCard label="Оплаты" value={String(data.stats.payments_paid)} caption="успешных" />
        <TodayCard label="Stars" value={String(data.stats.stars_paid)} caption="оплачено" />
      </div>

      <section className="subscription-access-grid">
        <article className="access-card unlocked">
          <div className="access-card-title">
            <span>✅</span>
            <h3>Открыто сейчас</h3>
          </div>
          <FeatureList items={unlocked} empty="Базовые функции доступны." />
        </article>

        <article className="access-card locked">
          <div className="access-card-title">
            <span>🔒</span>
            <h3>Закрыто</h3>
          </div>
          <FeatureList items={locked} empty="Все ключевые функции уже открыты." />
        </article>
      </section>

      <section className="upgrade-panel">
        <span className="panel-kicker">Рекомендация</span>
        <FormattedText text={data.subscription.recommended_upgrade || "Открой подписку в боте, чтобы усилить рабочий контур."} />
      </section>

      <div className="plans">
        <Plan
          title="Free"
          price="0 ⭐"
          items={["базовый ассистент", "режимы", "Mini App", "лимиты на день"]}
        />
        <Plan
          title="Pro"
          price="299 ⭐"
          items={["Deep Research", "DOCX/PDF", "документы из диалога", "повышенные лимиты"]}
        />
        <Plan
          title="Business"
          price="999 ⭐"
          items={["всё из Pro", "память группы", "групповые документы", "максимальные лимиты"]}
        />
      </div>

      <button className="primary-button" onClick={() => sendToBot("subscription")} type="button">
        Открыть подписку в боте
      </button>
    </>
  );
}

function FeatureList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) {
    return <p className="feature-empty">{empty}</p>;
  }

  return (
    <ul className="feature-list-compact">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function FormattedText({ text }: { text: string }) {
  return (
    <div className="formatted-text">
      {text.split("\n").map((line, index) => {
        if (!line.trim()) {
          return <br key={`br-${index}`} />;
        }

        return <p key={`${line}-${index}`}>{line}</p>;
      })}
    </div>
  );
}


function AdminScreen({ dashboard }: { dashboard: MiniAppAdminDashboard | null }) {
  if (!dashboard?.is_admin) {
    return (
      <EmptyState
        icon="▣"
        title="Admin недоступен"
        text="Эта вкладка доступна только владельцам и администраторам продукта."
        button="Открыть чат"
        onClick={() => sendToBot("assistant")}
      />
    );
  }

  const queue = dashboard.queue.by_status;
  const warnings = dashboard.warnings || [];

  return (
    <>
      <div className="section-heading">
        <span>▣</span>
        <h2>Admin Dashboard</h2>
      </div>

      <p className="lead">
        Центр управления продуктом: очередь, worker, LLM, платежи, backup, abuse и audit.
      </p>

      {warnings.length > 0 ? (
        <section className="admin-warning-panel">
          <span>⚠️ Зоны внимания</span>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : (
        <section className="admin-ok-panel">
          <span>✅ Система выглядит здоровой</span>
          <p>Критичных предупреждений сейчас нет.</p>
        </section>
      )}

      <div className="admin-grid">
        <AdminCard
          title="System"
          accent="Состояние"
          rows={[
            ["App", dashboard.system.app_name],
            ["Env", dashboard.system.env],
            ["Mini App API", dashboard.system.miniapp_api ? "enabled" : "disabled"]
          ]}
          command="admin_status"
        />

        <AdminCard
          title="Product"
          accent="Активность"
          rows={[
            ["Users", String(dashboard.product.users_total)],
            ["New today", String(dashboard.product.users_today)],
            ["Messages today", String(dashboard.product.messages_today)],
            ["Docs today", String(dashboard.product.documents_today)]
          ]}
          command="stats"
        />

        <AdminCard
          title="Queue"
          accent="Worker flow"
          rows={[
            ["Pending", String(queue.pending || 0)],
            ["Processing", String(queue.processing || 0)],
            ["Done", String(queue.done || 0)],
            ["Failed", String(queue.failed || 0)]
          ]}
          command="queue_status"
        />

        <AdminCard
          title="Worker"
          accent="Parallelism"
          rows={[
            ["Slots", String(dashboard.worker.concurrency)],
            ["Heavy slots", String(dashboard.worker.heavy_concurrency)],
            ["Poll", `${dashboard.worker.poll_interval_seconds}s`],
            ["Attempts", String(dashboard.worker.max_attempts)]
          ]}
          command="admin_status"
        />

        <AdminCard
          title="LLM"
          accent="Cost ledger"
          rows={[
            ["Requests 24h", String(dashboard.llm.requests_24h)],
            ["Input tokens", String(dashboard.llm.input_tokens_24h)],
            ["Output tokens", String(dashboard.llm.output_tokens_24h)],
            ["Cost 24h", `$${dashboard.llm.estimated_cost_usd_24h.toFixed(6)}`]
          ]}
          command="admin_llm_usage"
        />

        <AdminCard
          title="Payments"
          accent="Stars"
          rows={[
            ["Paid", String(dashboard.payments.paid)],
            ["Created", String(dashboard.payments.created)],
            ["Rejected", String(dashboard.payments.rejected)],
            ["Stars", String(dashboard.payments.stars_paid)]
          ]}
          command="payments"
        />

        <AdminCard
          title="Backup"
          accent="Recovery"
          rows={[
            ["Latest", dashboard.backup.latest?.name || "—"],
            ["Kind", dashboard.backup.latest?.kind || "—"],
            ["Size", dashboard.backup.latest?.size_text || "—"],
            ["Created", dashboard.backup.latest?.created_at || "—"]
          ]}
          command="admin_backup"
        />

        <AdminCard
          title="Security"
          accent="Abuse / Audit"
          rows={[
            ["Abuse blocked 24h", String(dashboard.abuse.blocked_24h)],
            ["Audit events 24h", String(dashboard.audit.events_24h)],
            ["Web", dashboard.web.enabled ? "enabled" : "disabled"],
            ["Web key", dashboard.web.api_key]
          ]}
          command="admin_security"
        />
      </div>

      <section className="admin-kind-panel">
        <div className="admin-kind-head">
          <span>Queue by kind</span>
          <button type="button" onClick={() => sendToBot("queue_failed")}>
            Failed
          </button>
        </div>

        {dashboard.queue.by_kind.length === 0 ? (
          <p>Очередь пока пустая.</p>
        ) : (
          <div className="admin-kind-list">
            {dashboard.queue.by_kind.map((item) => (
              <div key={`${item.kind}-${item.status}`}>
                <strong>{item.kind}</strong>
                <span>{item.status}</span>
                <b>{item.count}</b>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="admin-actions">
        <button type="button" onClick={() => sendToBot("admin_status")}>/admin_status</button>
        <button type="button" onClick={() => sendToBot("queue_status")}>/queue_status</button>
        <button type="button" onClick={() => sendToBot("admin_backup_now")}>Backup now</button>
        <button type="button" onClick={() => sendToBot("admin_audit")}>Audit</button>
      </div>
    </>
  );
}

function AdminCard({
  title,
  accent,
  rows,
  command
}: {
  title: string;
  accent: string;
  rows: Array<[string, string]>;
  command: string;
}) {
  return (
    <article className="admin-card">
      <div className="admin-card-top">
        <div>
          <span>{accent}</span>
          <h3>{title}</h3>
        </div>
        <button type="button" onClick={() => sendToBot(command)}>
          открыть
        </button>
      </div>

      <div className="admin-card-rows">
        {rows.map(([label, value]) => (
          <div key={`${title}-${label}`}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </article>
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
