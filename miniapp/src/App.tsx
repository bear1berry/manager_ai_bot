import { useEffect, useMemo, useState } from "react";

type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  close: () => void;
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };
  initDataUnsafe?: {
    user?: {
      id?: number;
      username?: string;
      first_name?: string;
      last_name?: string;
    };
  };
  colorScheme?: "light" | "dark";
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

function getWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

function sendToBot(text: string) {
  const encoded = encodeURIComponent(text);
  window.location.href = `https://t.me/user_managerGPT_Bot?start=${encoded}`;
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("home");

  const webApp = useMemo(() => getWebApp(), []);
  const user = webApp?.initDataUnsafe?.user;
  const firstName = user?.first_name || "Александр";

  useEffect(() => {
    webApp?.ready();
    webApp?.expand();
  }, [webApp]);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-topline">Telegram Mini App</div>
        <h1>Менеджер ИИ</h1>
        <p>
          Премиальный рабочий кабинет для проектов, документов, подписки и быстрых AI-сценариев.
        </p>

        <div className="user-chip">
          <span className="pulse" />
          <span>{firstName}</span>
          <span className="muted">· MVP кабинет</span>
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
        {activeTab === "home" && <HomeScreen />}
        {activeTab === "projects" && <ProjectsScreen />}
        {activeTab === "docs" && <DocumentsScreen />}
        {activeTab === "subscription" && <SubscriptionScreen />}
        {activeTab === "demo" && <DemoScreen />}
      </section>
    </main>
  );
}

function HomeScreen() {
  return (
    <>
      <div className="section-heading">
        <span>⌁</span>
        <h2>Рабочий центр</h2>
      </div>

      <div className="metrics-grid">
        <Metric title="Тариф" value="Free / Pro" caption="подключается через Stars" />
        <Metric title="Проекты" value="Память" caption="клиенты, сроки, заметки" />
        <Metric title="Документы" value="DOCX/PDF" caption="КП, планы, чек-листы" />
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

function ProjectsScreen() {
  return (
    <>
      <div className="section-heading">
        <span>◩</span>
        <h2>Проекты</h2>
      </div>

      <p className="lead">
        Проекты — это рабочая память: клиенты, сроки, бюджеты, договорённости и заметки.
      </p>

      <div className="feature-list">
        <Feature title="Создать проект" text="Сохрани вводные по клиенту или задаче." />
        <Feature title="Добавить заметку" text="Докинь новую договорённость без потери контекста." />
        <Feature title="Спросить по проекту" text="Например: «Что у нас по Ивановой?»" />
      </div>

      <button className="primary-button" onClick={() => sendToBot("projects")} type="button">
        Открыть проекты в боте
      </button>
    </>
  );
}

function DocumentsScreen() {
  return (
    <>
      <div className="section-heading">
        <span>□</span>
        <h2>Документы</h2>
      </div>

      <p className="lead">
        Превращай сырые вводные в аккуратные документы: КП, план работ, резюме встречи или чек-лист.
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

function SubscriptionScreen() {
  return (
    <>
      <div className="section-heading">
        <span>◇</span>
        <h2>Подписка</h2>
      </div>

      <p className="lead">
        Оплата проходит через Telegram Stars. После оплаты тариф активируется автоматически.
      </p>

      <div className="plans">
        <Plan
          title="Pro"
          price="299 ⭐"
          items={["больше запросов", "больше голосовых", "DOCX/PDF", "проекты"]}
        />
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

      <p className="lead">
        Быстрый маршрут для первого пользователя: понять, зачем нужен бот, без длинных инструкций.
      </p>

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
