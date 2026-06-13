# NeuroHub

**Настоящее desktop-приложение для общения с нейросетями на ПК** — OpenAI, Anthropic, Gemini, OpenRouter, DeepSeek, Groq.

NeuroHub теперь запускается как отдельное окно, а не как браузерная страница и не как голая консоль.

## Быстрый старт на Windows

1. Открой папку проекта: `C:\Users\Nestr\OneDrive\Desktop\neurohub1`.
2. Дважды кликни `start.bat`.
3. Откроется окно **NeuroHub Desktop**.
4. Нажми **API keys**, выбери провайдера, вставь ключ, выбери модель и пиши сообщение.

```bat
cd C:\Users\Nestr\OneDrive\Desktop\neurohub1
pip install -e .
neurohub
```

> В `cmd.exe` нет команды `cp`. Если всё-таки нужен `.env`, используй `copy .env.example .env`.
> Но для desktop-приложения это не обязательно: ключ добавляется прямо в окне.

## Что теперь есть в desktop-приложении

- **Настоящее окно приложения** на Tkinter: без браузера и без консольного чата.
- **Современный app-shell**: тёмный сайдбар, рабочая область, верхний статус, центрированный welcome-экран и большой composer.
- **Интерфейс в стиле современных AI desktop-клиентов**: быстрые модельные чипы, suggestion-кнопки, панель инструментов и аккуратные message bubbles.
- **Нормальное добавление API-ключей** через кнопку **API keys**.
- **Локальное хранение настроек** в профиле пользователя: `~/.neurohub/desktop-settings.json`.
- **Опциональное сохранение ключей**: если не включать галочку, ключ не будет записан в файл настроек.
- **Markdown-ish ответы**: заголовки, списки и блоки кода форматируются в окне чата.
- **Понятные ошибки**: 401/403/404/429 показываются в чате нормальным текстом, а не traceback-ом.
- **Быстрый выбор моделей**: GPT, Claude, DeepSeek, Groq, Gemini.
- **Очистка чата** кнопкой **New**.
- **Экспорт истории** кнопкой **Export** в JSON.

## Команды запуска

```bash
# Desktop-приложение по умолчанию
neurohub

# То же самое явно
neurohub-desktop

# Старый web UI оставлен запасным вариантом
neurohub-web

# Консольный режим для тех, кто любит терминал
neurohub-cli "Объясни async/await в Python"
```

## Исправление `InvalidURL` и странных символов

NeuroHub очищает значения ключей и URL от скрытых управляющих символов, например `\x16`,
которые иногда попадают при копировании и приводят к ошибке:

```text
InvalidURL: Invalid non-printable ASCII character in URL
```

Если URL всё равно некорректный, приложение покажет понятную ошибку.

## Python API

```python
import asyncio
from neurohub import NeuroClient, Conversation

async def main():
    client = NeuroClient.from_env("openai")

    answer = await client.ask("Привет!")
    print(answer)

    conv = Conversation(system_prompt="Ты — эксперт Python")
    await conv.send("Что такое GIL?")
    await conv.send("А как обойти?")

asyncio.run(main())
```

## Провайдеры

| Провайдер   | Env переменная       | Модель по умолчанию          |
|-------------|----------------------|------------------------------|
| OpenAI      | `OPENAI_API_KEY`     | `gpt-4o-mini`                |
| Anthropic   | `ANTHROPIC_API_KEY`  | `claude-3-5-sonnet-20241022` |
| Gemini      | `GEMINI_API_KEY`     | `gemini-2.0-flash`           |
| OpenRouter  | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini`         |
| DeepSeek    | `DEEPSEEK_API_KEY`   | `deepseek-chat`              |
| Groq        | `GROQ_API_KEY`       | `llama-3.3-70b-versatile`    |

## Архитектура

```text
neurohub/
├── desktop_app.py     # настоящее desktop-приложение на Tkinter
├── web_app.py         # запасной локальный web-сервер
├── static/            # HTML/CSS/JS для web-режима
├── client.py          # NeuroClient — единая async-точка входа
├── conversation.py    # многоходовые сессии + экспорт
├── config.py          # настройки, очистка ключей/URL от скрытых символов
├── providers/         # OpenAI-compatible, Anthropic, Gemini
└── cli.py             # опциональный консольный режим neurohub-cli
```
