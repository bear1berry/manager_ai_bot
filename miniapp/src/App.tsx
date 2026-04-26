import { useEffect, useMemo, useState } from "react";
import { loadMiniAppData, type MiniAppData, type MiniAppProject } from "./api";

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

type TabKey = "home" | "projects" | "docs" | "subscription" | "demo";

const tabs: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: "home", label: "Главная", icon: "⌁" },
  { key: "projects", label: "Проекты", icon: "◩" },
  { key: "docs", label: "Документы", icon: "□" },
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
    documents_generated: 1,
    feedback_total: 3,
    payments_paid: 0,
    stars_paid: 0
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

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("home");
  const [data, setData] = useState<MiniAppData>(fallbackData);
  const [loading, setLoading] = useState(true);
  const [apiStatus, setApiStatus] = useState<"loading" | "live" | "demo" | "error">("loading");

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
        <p>Премиальный рабочий кабинет для проектов, документов, подписки и быстрых AI-сценариев.</p>

        <div className="user-chip">
          <span className={apiStatus === "live" ? "pulse" : "pulse muted-pulse"} />
          <span>{firstName}</span>
          <span className="muted">
            · {apiStatus === "live" ? "real data" : apiStatus === "error" ? "API offline" : "demo"}
          </span>
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

        {!loading && activeTab === "home" && <HomeScreen data={data} />}
        {!loading && activeTab === "projects" && <ProjectsScreen data={data} />}
        {!loading && activeTab === "docs" && <DocumentsScreen data={data} />}
        {!loading && activeTab === "subscription" && <SubscriptionScreen data={data} />}
        {!loading && activeTab === "demo" && <DemoScreen />}
      </section>
    </main>
  );
}

function HomeScreen({ data }: { data: MiniAppData }) {
  return (
    <>
      <div className="section-heading">
        <span>⌁</span>
        <h2>Рабочий центр</h2>
      </div>

      <div className="metrics-grid">
        <Metric title="Тариф" value={data.subscription.plan_name} caption={`до ${data.subscription.expires_text}`} />
        <Metric title="Проекты" value={String(data.stats.projects_total)} caption="активная память" />
        <Metric title="Документы" value={String(data.stats.documents_generated)} caption="создано файлов" />
      </div>

      <div className="limit-card">
        <h3>Лимиты сегодня</h3>
        <div className="limit-row">
          <span>Текст</span>
          <strong>
            {data.limits.text.used}/{formatLimit(data.limits.text.limit)}
          </strong>
        </div>
        <div className="limit-row">
          <span>Голосовые</span>
          <strong>
            {data.limits.voice.used}/{formatLimit(data.limits.voice.limit)}
          </strong>
        </div>
      </div>

      <div className="action-list">
        <ActionCard
          title="Быстро решить задачу"
          text="Открой чат и отправь любую рабочую вводную. Бот сам определит сценарий."
          button="Открыть ассистента"
          onClick={() => sendToBot("assistant")}
        />
        <ActionCard
          title="Показать возможности"
          text="Демо помогает первому пользователю быстро понять ценность продукта."
          button="Открыть демо"
          onClick={() => sendToBot("demo")}
        />
      </div>
    </>
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

      <p className="lead">
        Рабочая память: клиенты, сроки, бюджеты, договорённости и следующий шаг.
      </p>

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
          title="Проектов пока нет"
          text="Создай первый проект в боте. После этого он появится здесь карточкой."
          button="Создать проект"
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

function DocumentsScreen({ data }: { data: MiniAppData }) {
  return (
    <>
      <div className="section-heading">
        <span>□</span>
        <h2>Документы</h2>
      </div>

      <p className="lead">
        Создано документов: <strong>{data.stats.documents_generated}</strong>. Следующий слой — история документов и
        повторное скачивание.
      </p>

      <div className="document-grid">
        <DocumentType title="КП" icon="◇" />
        <DocumentType title="План работ" icon="▦" />
        <DocumentType title="Резюме встречи" icon="≡" />
        <DocumentType title="Чек-лист" icon="☑" />
      </div>

      <button className="primary-button" onClick={() => sendToBot("documents")} type="button">
        Собрать документ
      </button>
    </>
  );
}

function SubscriptionScreen({ data }: { data: MiniAppData }) {
  return (
    <>
      <div className="section-heading">
        <span>◇</span>
        <h2>Подписка</h2>
      </div>

      <p className="lead">
        Текущий тариф: <strong>{data.subscription.plan_name}</strong>. Действует до:{" "}
        <strong>{data.subscription.expires_text}</strong>.
      </p>

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
        <button type="button" onClick={() => sendToBot("documents")}>
          Документ
        </button>
      </div>
    </article>
  );
}

function EmptyState({
  title,
  text,
  button,
  onClick
}: {
  title: string;
  text: string;
  button: string;
  onClick: () => void;
}) {
  return (
    <article className="empty-state">
      <div className="empty-icon">◌</div>
      <h3>{title}</h3>
      <p>{text}</p>
      <button type="button" onClick={onClick}>
        {button}
      </button>
    </article>
  );
}

function Metric({ title, value, caption }: { title: string; value: string; caption: string }) {
  return (
    <article className="metric">
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-caption">{caption}</div>
    </article>
  );
}

function ActionCard({
  title,
  text,
  button,
  onClick
}: {
  title: string;
  text: string;
  button: string;
  onClick: () => void;
}) {
  return (
    <article className="action-card">
      <h3>{title}</h3>
      <p>{text}</p>
      <button onClick={onClick} type="button">
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

function DocumentType({ title, icon }: { title: string; icon: string }) {
  return (
    <article className="doc-type">
      <span>{icon}</span>
      <strong>{title}</strong>
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
