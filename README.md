# Менеджер ИИ

Telegram AI-ассистент для малого бизнеса, самозанятых и рабочих задач.

## Что умеет MVP

- Текстовый AI-ассистент.
- Голосовые через SQLite queue + worker.
- Идемпотентность через `dedupe_key`.
- Проекты.
- DOCX/PDF документы.
- Free/Pro/Business лимиты.
- Нижний таскбар без inline-кнопок.
- Деплой через systemd.

## Быстрый запуск на MacBook Air 2025

```bash
git clone <your_repo_url>
cd manager_ai_bot

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env

python -m compileall app
python -m app.main
```

Минимум в `.env`:

```env
BOT_TOKEN=telegram_bot_token
LLM_API_KEY=llm_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

## Запуск на Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python -m compileall app
python -m app.main
```

## Деплой на Ubuntu / Yandex Cloud

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git fonts-dejavu-core

sudo mkdir -p /opt/manager_ai_bot
sudo chown -R $USER:$USER /opt/manager_ai_bot
cd /opt/manager_ai_bot

git clone <your_repo_url> .

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env

python -m compileall app
python -m app.main
```

Если ручной запуск успешный:

```bash
sudo cp systemd/manager-ai-bot.service /etc/systemd/system/manager-ai-bot.service
sudo chown -R www-data:www-data /opt/manager_ai_bot
sudo systemctl daemon-reload
sudo systemctl enable manager-ai-bot
sudo systemctl start manager-ai-bot
sudo journalctl -u manager-ai-bot -f
```

## Админ-команда

```text
/setplan telegram_id free
/setplan telegram_id pro
/setplan telegram_id business
```

## Важно

Для PDF с кириллицей на Linux желательно:

```bash
sudo apt install fonts-dejavu-core
```
