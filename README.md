# NeuroHub

**Единый клиент для общения с нейросетями** — OpenAI, Anthropic, Gemini, OpenRouter, DeepSeek, Groq.

## Быстрый старт

```bash
cd neurohub
pip install -e .
cp .env.example .env
# Добавь свой API ключ в .env
neurohub
```

## CLI

```bash
# Интерактивный чат
neurohub

# С выбором провайдера и модели
neurohub -p anthropic -m claude-3-5-sonnet-20241022

# One-shot запрос
neurohub "Объясни async/await в Python"

# Команды в чате
/help       — список команд
/switch     — сменить провайдера
/model      — сменить модель
/clear      — очистить историю
/tokens     — статистика токенов
/export     — сохранить чат в JSON
```

## Python API

```python
import asyncio
from neurohub import NeuroClient, Conversation

async def main():
    client = NeuroClient.from_env("openai")
    
    # Простой вопрос
    answer = await client.ask("Привет!")
    
    # Стриминг
    async for chunk in client.stream("Расскажи историю"):
        print(chunk.content, end="")
    
    # Диалог с историей
    conv = Conversation(system_prompt="Ты — эксперт Python")
    await conv.send("Что такое GIL?")
    await conv.send("А как обойти?")

asyncio.run(main())
```

## Провайдеры

| Провайдер   | Env переменная       | Модели по умолчанию          |
|-------------|----------------------|------------------------------|
| OpenAI      | `OPENAI_API_KEY`     | gpt-4o-mini                  |
| Anthropic   | `ANTHROPIC_API_KEY`  | claude-3-5-sonnet            |
| Gemini      | `GEMINI_API_KEY`     | gemini-2.0-flash             |
| OpenRouter  | `OPENROUTER_API_KEY` | openai/gpt-4o-mini           |
| DeepSeek    | `DEEPSEEK_API_KEY`   | deepseek-chat                |
| Groq        | `GROQ_API_KEY`       | llama-3.3-70b-versatile      |

## Архитектура

```
neurohub/
├── client.py          # NeuroClient — единая точка входа
├── conversation.py    # Многоходовые сессии + экспорт
├── config.py          # Настройки и API ключи из .env
├── providers/
│   ├── base.py        # Абстрактный провайдер + retry
│   ├── openai_compat.py  # OpenAI-совместимые API
│   ├── anthropic.py   # Claude
│   └── gemini.py      # Google Gemini
└── cli.py             # Красивый терминальный чат
```
