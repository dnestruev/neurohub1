# NeuroHub

**Красивое локальное web-приложение для общения с нейросетями** — OpenAI, Anthropic, Gemini, OpenRouter, DeepSeek, Groq.

## Быстрый старт на Windows

1. Открой папку проекта: `C:\Users\Nestr\OneDrive\Desktop\neurohub1`.
2. Дважды кликни `start.bat`.
3. Браузер откроет локальный NeuroHub.
4. Выбери провайдера, вставь API ключ в левую панель и отправь сообщение.

> В `cmd.exe` нет команды `cp`. Если всё-таки нужен `.env`, используй `copy .env.example .env`.
> Но для web-приложения это не обязательно: ключ можно вставить прямо в интерфейсе.

## Запуск командами

```bat
cd C:\Users\Nestr\OneDrive\Desktop\neurohub1
pip install -e .
neurohub
```

После запуска откроется браузер. Если он не открылся автоматически, перейди по адресу из консоли, обычно:

```text
http://127.0.0.1:8765
```

## Что теперь умеет приложение

- **Нормальное добавление ключа** в интерфейсе, без ручного редактирования `.env`.
- **Ключ не сохраняется на сервере**. По желанию его можно сохранить только в localStorage браузера.
- **Markdown-ответы**: заголовки, списки, ссылки, inline-code и блоки кода.
- **Красивый UI** вместо голой консоли.
- **Понятные ошибки**: 401/403/429 показываются в чате, а не роняют приложение traceback-ом.
- **Экспорт чата** в JSON.
- **Новый чат** одной кнопкой.

## Исправление `InvalidURL` и странных символов

NeuroHub очищает значения ключей и URL от скрытых управляющих символов, например `\x16`,
которые иногда попадают при копировании и приводят к ошибке:

```text
InvalidURL: Invalid non-printable ASCII character in URL
```

Если URL всё равно некорректный, приложение покажет понятную ошибку в интерфейсе.

## CLI остался для тех, кто хочет консоль

```bash
neurohub-cli "Объясни async/await в Python"
neurohub-cli -p anthropic -m claude-3-5-sonnet-20241022
```

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
├── web_app.py         # локальный web-сервер без дополнительных backend-зависимостей
├── static/            # HTML/CSS/JS интерфейс
├── client.py          # NeuroClient — единая async-точка входа
├── conversation.py    # многоходовые сессии + экспорт
├── config.py          # настройки, очистка ключей/URL от скрытых символов
├── providers/         # OpenAI-compatible, Anthropic, Gemini
└── cli.py             # опциональный консольный режим neurohub-cli
```
