"""Native desktop application for NeuroHub."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import httpx

from .config import API_KEY_ENV, DEFAULT_BASE_URLS, DEFAULT_MODELS, ProviderConfig, clean_env_value, validate_url
from .models import ChatMessage
from .providers import create_provider

APP_NAME = "NeuroHub"
SETTINGS_DIR = Path.home() / ".neurohub"
SETTINGS_FILE = SETTINGS_DIR / "desktop-settings.json"

MODEL_PRESETS = [
    ("openai", "GPT-4o mini", "gpt-4o-mini"),
    ("openai", "GPT-4.1", "gpt-4.1"),
    ("anthropic", "Claude Sonnet", "claude-3-5-sonnet-20241022"),
    ("deepseek", "DeepSeek Chat", "deepseek-chat"),
    ("groq", "Groq Llama", "llama-3.3-70b-versatile"),
    ("gemini", "Gemini Flash", "gemini-2.0-flash"),
]

COLORS = {
    "bg": "#f7f7f8",
    "panel": "#ffffff",
    "panel_soft": "#f2f4f7",
    "text": "#111827",
    "muted": "#6b7280",
    "border": "#e5e7eb",
    "accent": "#10a37f",
    "accent_soft": "#e7f8f2",
    "danger": "#dc2626",
    "user": "#eef2ff",
    "assistant": "#ffffff",
}


@dataclass(slots=True)
class DesktopSettings:
    """User settings saved by the native desktop app."""

    provider: str = "openai"
    model: str = DEFAULT_MODELS["openai"]
    base_url: str = DEFAULT_BASE_URLS["openai"]
    api_keys: dict[str, str] | None = None
    remember_keys: bool = False

    def key_for_provider(self) -> str:
        return (self.api_keys or {}).get(self.provider, "")

    def to_json(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_keys": self.api_keys if self.remember_keys else {},
            "remember_keys": self.remember_keys,
        }


class DesktopConfigError(ValueError):
    """Raised for desktop form validation errors."""


def load_desktop_settings() -> DesktopSettings:
    """Load settings from the user's home directory."""

    if not SETTINGS_FILE.exists():
        return DesktopSettings(api_keys={})
    data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    provider = clean_env_value(str(data.get("provider") or "openai")).lower()
    if provider not in API_KEY_ENV:
        provider = "openai"
    return DesktopSettings(
        provider=provider,
        model=clean_env_value(str(data.get("model") or DEFAULT_MODELS[provider])),
        base_url=clean_env_value(str(data.get("base_url") or DEFAULT_BASE_URLS.get(provider, ""))),
        api_keys={str(k): clean_env_value(str(v)) for k, v in data.get("api_keys", {}).items()},
        remember_keys=bool(data.get("remember_keys")),
    )


def save_desktop_settings(settings: DesktopSettings) -> None:
    """Persist settings locally in the user's profile."""

    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")


def build_provider_config(settings: DesktopSettings) -> ProviderConfig:
    """Validate UI settings and build a provider config."""

    provider = clean_env_value(settings.provider).lower()
    if provider not in API_KEY_ENV:
        raise DesktopConfigError(f"Неизвестный провайдер: {provider}")

    api_key = clean_env_value(settings.key_for_provider())
    if not api_key or api_key in {"sk-...", "sk-ant-...", "sk-or-...", "gsk_..."}:
        raise DesktopConfigError("Добавь настоящий API ключ: кнопка «API keys» справа сверху.")

    model = clean_env_value(settings.model or DEFAULT_MODELS[provider])
    raw_base_url = clean_env_value(settings.base_url or DEFAULT_BASE_URLS.get(provider, ""))
    base_url = validate_url(raw_base_url, name="Base URL") if raw_base_url else None
    return ProviderConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)


def friendly_http_error(exc: httpx.HTTPStatusError) -> str:
    """Convert provider HTTP failures into human-readable desktop messages."""

    status = exc.response.status_code
    if status == 401:
        return "401 Unauthorized — ключ неверный, пустой или выбран не тот провайдер."
    if status == 403:
        return "403 Forbidden — у ключа нет доступа к выбранной модели."
    if status == 404:
        return "404 Not Found — проверь модель и Base URL."
    if status == 429:
        return "429 Rate limit — лимит запросов или закончился баланс."
    return f"HTTP {status}: {_extract_error_detail(exc.response)}"


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return str(data["error"].get("message") or data["error"])[:300]
    return str(data)[:300]


class NeuroHubDesktop(tk.Tk):
    """Native Tkinter desktop chat application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("NeuroHub — Native AI Chat")
        self.geometry("1080x720")
        self.minsize(840, 560)
        self.configure(bg=COLORS["bg"])

        self.settings = load_desktop_settings()
        self.messages: list[ChatMessage] = []
        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_busy = False

        self._setup_style()
        self._build_layout()
        self._render_welcome()
        self.after(120, self._poll_result_queue)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"], relief="flat")
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
        style.configure("Accent.TButton", padding=(16, 9), background=COLORS["accent"])
        style.configure("Chip.TButton", padding=(12, 7), background=COLORS["panel"])

    def _build_layout(self) -> None:
        shell = tk.Frame(self, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True, padx=28, pady=24)

        header = tk.Frame(shell, bg=COLORS["bg"])
        header.pack(fill="x")
        tk.Label(header, text="✣", font=("Segoe UI", 38, "bold"), bg=COLORS["bg"]).pack()
        tk.Label(
            header,
            text="How can I help you today?",
            font=("Segoe UI", 22, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(0, 18))

        self.chip_row = tk.Frame(shell, bg=COLORS["bg"])
        self.chip_row.pack(fill="x", pady=(0, 16))
        for provider, label, model in MODEL_PRESETS:
            self._make_chip(self.chip_row, provider, label, model).pack(side="left", padx=(0, 8))
        tk.Button(
            self.chip_row,
            text="API keys",
            command=self._open_settings_dialog,
            relief="flat",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            padx=14,
            pady=8,
        ).pack(side="right")

        chat_card = tk.Frame(shell, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        chat_card.pack(fill="both", expand=True)

        self.chat = tk.Text(
            chat_card,
            wrap="word",
            relief="flat",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            padx=24,
            pady=20,
            state="disabled",
            font=("Segoe UI", 11),
        )
        self.chat.pack(fill="both", expand=True)
        self._configure_chat_tags()

        composer = tk.Frame(chat_card, bg=COLORS["panel"], padx=14, pady=14)
        composer.pack(fill="x")
        self.prompt = tk.Text(
            composer,
            height=3,
            wrap="word",
            relief="flat",
            bg=COLORS["panel_soft"],
            fg=COLORS["text"],
            padx=14,
            pady=12,
            font=("Segoe UI", 11),
        )
        self.prompt.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.prompt.bind("<Control-Return>", lambda _event: self._send_message())
        self.prompt.bind("<Command-Return>", lambda _event: self._send_message())

        actions = tk.Frame(composer, bg=COLORS["panel"])
        actions.pack(side="right", fill="y")
        tk.Button(actions, text="New", command=self._new_chat, relief="flat", padx=12, pady=7).pack(
            fill="x", pady=(0, 7)
        )
        tk.Button(actions, text="Export", command=self._export_chat, relief="flat", padx=12, pady=7).pack(
            fill="x", pady=(0, 7)
        )
        self.send_button = tk.Button(
            actions,
            text="Send ↵",
            command=self._send_message,
            relief="flat",
            bg=COLORS["text"],
            fg="#ffffff",
            padx=18,
            pady=11,
        )
        self.send_button.pack(fill="x")

        self.status = tk.Label(
            shell,
            text=self._status_text(),
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            anchor="w",
        )
        self.status.pack(fill="x", pady=(10, 0))

    def _make_chip(self, parent: tk.Widget, provider: str, label: str, model: str) -> tk.Button:
        selected = self.settings.provider == provider and self.settings.model == model
        return tk.Button(
            parent,
            text=label,
            command=lambda: self._select_model(provider, model),
            relief="flat",
            bg=COLORS["accent_soft"] if selected else COLORS["panel"],
            fg=COLORS["accent"] if selected else COLORS["muted"],
            activebackground=COLORS["accent_soft"],
            padx=13,
            pady=8,
        )

    def _configure_chat_tags(self) -> None:
        self.chat.tag_configure("center", justify="center", spacing3=10)
        self.chat.tag_configure("muted", foreground=COLORS["muted"])
        self.chat.tag_configure("user", lmargin1=180, lmargin2=180, rmargin=20, spacing3=12)
        self.chat.tag_configure("assistant", lmargin1=20, lmargin2=20, rmargin=180, spacing3=12)
        self.chat.tag_configure("role", foreground=COLORS["muted"], font=("Segoe UI", 9, "bold"))
        self.chat.tag_configure("heading", font=("Segoe UI", 15, "bold"), spacing1=10, spacing3=6)
        self.chat.tag_configure("code", font=("Consolas", 10), background="#f3f4f6", lmargin1=36)
        self.chat.tag_configure("error", foreground=COLORS["danger"])

    def _render_welcome(self) -> None:
        self._with_chat_editable(lambda: self._insert_welcome())

    def _insert_welcome(self) -> None:
        self.chat.delete("1.0", "end")
        self.chat.insert("end", "NeuroHub\n", ("center", "heading"))
        self.chat.insert(
            "end",
            "Выбери модель, добавь API ключ через кнопку API keys и напиши сообщение.\n\n",
            ("center", "muted"),
        )
        self.chat.insert("end", "Поддерживаются Markdown, кодовые блоки и экспорт истории в JSON.", "center")

    def _select_model(self, provider: str, model: str) -> None:
        self.settings.provider = provider
        self.settings.model = model
        self.settings.base_url = DEFAULT_BASE_URLS.get(provider, "")
        self.status.configure(text=self._status_text())
        save_desktop_settings(self.settings)
        self._rebuild_chips()

    def _rebuild_chips(self) -> None:
        for child in self.chip_row.winfo_children():
            child.destroy()
        for provider, label, model in MODEL_PRESETS:
            self._make_chip(self.chip_row, provider, label, model).pack(side="left", padx=(0, 8))
        tk.Button(
            self.chip_row,
            text="API keys",
            command=self._open_settings_dialog,
            relief="flat",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            padx=14,
            pady=8,
        ).pack(side="right")

    def _open_settings_dialog(self) -> None:
        SettingsDialog(self, self.settings, self._apply_settings)

    def _apply_settings(self, settings: DesktopSettings) -> None:
        self.settings = settings
        save_desktop_settings(settings)
        self.status.configure(text=self._status_text())
        self._rebuild_chips()

    def _new_chat(self) -> None:
        self.messages.clear()
        self._render_welcome()
        self.status.configure(text="Новый чат готов")


    def _export_chat(self) -> None:
        if not self.messages:
            messagebox.showinfo(APP_NAME, "История чата пустая.")
            return
        path = filedialog.asksaveasfilename(
            title="Export NeuroHub chat",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        payload = [message.as_dict() for message in self.messages]
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.configure(text=f"Чат сохранён: {path}")

    def _send_message(self) -> None:
        if self.is_busy:
            return
        text = self.prompt.get("1.0", "end").strip()
        if not text:
            return
        try:
            config = build_provider_config(self.settings)
        except (DesktopConfigError, ValueError) as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        self.prompt.delete("1.0", "end")
        user_message = ChatMessage("user", text)
        self.messages.append(user_message)
        self._append_message("Ты", text, "user")
        self._set_busy(True, "Думаю...")

        thread = threading.Thread(target=self._ask_in_background, args=(config, list(self.messages)), daemon=True)
        thread.start()

    def _ask_in_background(self, config: ProviderConfig, messages: list[ChatMessage]) -> None:
        try:
            response = asyncio.run(create_provider(config).ask(messages))
        except httpx.HTTPStatusError as exc:
            self.result_queue.put(("error", friendly_http_error(exc)))
        except httpx.RequestError as exc:
            self.result_queue.put(("error", f"Не удалось подключиться к API: {exc}"))
        except Exception as exc:
            self.result_queue.put(("error", f"Ошибка NeuroHub: {exc}"))
        else:
            self.result_queue.put(("answer", response.content))

    def _poll_result_queue(self) -> None:
        try:
            kind, payload = self.result_queue.get_nowait()
        except queue.Empty:
            self.after(120, self._poll_result_queue)
            return

        if kind == "answer":
            self.messages.append(ChatMessage("assistant", str(payload)))
            self._append_message("NeuroHub", str(payload), "assistant", markdown=True)
            self._set_busy(False, self._status_text())
        else:
            self._append_message("Ошибка", str(payload), "assistant", error=True)
            self._set_busy(False, "Исправь настройки и попробуй снова")
        self.after(120, self._poll_result_queue)

    def _append_message(
        self,
        role: str,
        content: str,
        tag: str,
        *,
        markdown: bool = False,
        error: bool = False,
    ) -> None:
        def insert() -> None:
            if len(self.messages) == 1 and role == "Ты":
                self.chat.delete("1.0", "end")
            self.chat.insert("end", f"{role}\n", (tag, "role"))
            if error:
                self.chat.insert("end", f"{content}\n\n", (tag, "error"))
            elif markdown:
                self._insert_markdown(content, tag)
            else:
                self.chat.insert("end", f"{content}\n\n", tag)
            self.chat.see("end")

        self._with_chat_editable(insert)

    def _insert_markdown(self, content: str, base_tag: str) -> None:
        in_code = False
        code_lines: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if line.startswith("```"):
                if in_code:
                    self.chat.insert("end", "\n".join(code_lines) + "\n", (base_tag, "code"))
                    code_lines.clear()
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(line)
                continue
            if line.startswith("# "):
                self.chat.insert("end", line[2:] + "\n", (base_tag, "heading"))
            elif line.startswith("## "):
                self.chat.insert("end", line[3:] + "\n", (base_tag, "heading"))
            elif line.startswith(("- ", "* ")):
                self.chat.insert("end", "• " + line[2:] + "\n", base_tag)
            else:
                self.chat.insert("end", line + "\n", base_tag)
        if code_lines:
            self.chat.insert("end", "\n".join(code_lines) + "\n", (base_tag, "code"))
        self.chat.insert("end", "\n", base_tag)

    def _with_chat_editable(self, callback: Any) -> None:
        self.chat.configure(state="normal")
        callback()
        self.chat.configure(state="disabled")

    def _set_busy(self, busy: bool, status: str) -> None:
        self.is_busy = busy
        self.send_button.configure(text="Thinking..." if busy else "Send ↵", state="disabled" if busy else "normal")
        self.status.configure(text=status)

    def _status_text(self) -> str:
        return f"{self.settings.provider} · {self.settings.model}"


class SettingsDialog(tk.Toplevel):
    """API key and provider settings dialog."""

    def __init__(self, parent: NeuroHubDesktop, settings: DesktopSettings, on_save: Any) -> None:
        super().__init__(parent)
        self.title("NeuroHub settings")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.on_save = on_save
        self.settings = DesktopSettings(
            provider=settings.provider,
            model=settings.model,
            base_url=settings.base_url,
            api_keys=dict(settings.api_keys or {}),
            remember_keys=settings.remember_keys,
        )

        self.provider_var = tk.StringVar(value=self.settings.provider)
        self.model_var = tk.StringVar(value=self.settings.model)
        self.base_url_var = tk.StringVar(value=self.settings.base_url)
        self.api_key_var = tk.StringVar(value=self.settings.key_for_provider())
        self.remember_var = tk.BooleanVar(value=self.settings.remember_keys)

        self._build()
        self.provider_var.trace_add("write", lambda *_: self._on_provider_change())
        self.wait_window(self)

    def _build(self) -> None:
        card = tk.Frame(self, bg=COLORS["panel"], padx=22, pady=20)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            card,
            text="API keys & provider",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self._label(card, "Провайдер", 1)
        provider_box = ttk.Combobox(card, textvariable=self.provider_var, values=sorted(API_KEY_ENV), state="readonly")
        provider_box.grid(row=1, column=1, sticky="ew", pady=6)

        self._label(card, "API ключ", 2)
        tk.Entry(card, textvariable=self.api_key_var, show="•", width=44).grid(
            row=2, column=1, sticky="ew", pady=6
        )

        tk.Checkbutton(
            card,
            text="Сохранить ключ локально на этом ПК",
            variable=self.remember_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            activebackground=COLORS["panel"],
        ).grid(row=3, column=1, sticky="w", pady=(0, 8))

        self._label(card, "Модель", 4)
        tk.Entry(card, textvariable=self.model_var, width=44).grid(row=4, column=1, sticky="ew", pady=6)

        self._label(card, "Base URL", 5)
        tk.Entry(card, textvariable=self.base_url_var, width=44).grid(row=5, column=1, sticky="ew", pady=6)

        buttons = tk.Frame(card, bg=COLORS["panel"])
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(16, 0))
        tk.Button(buttons, text="Cancel", command=self.destroy, relief="flat", padx=14, pady=8).pack(
            side="left", padx=(0, 8)
        )
        tk.Button(
            buttons,
            text="Save",
            command=self._save,
            relief="flat",
            bg=COLORS["accent"],
            fg="#ffffff",
            padx=18,
            pady=8,
        ).pack(side="left")
        card.columnconfigure(1, weight=1)

    @staticmethod
    def _label(parent: tk.Widget, text: str, row: int) -> None:
        tk.Label(parent, text=text, bg=COLORS["panel"], fg=COLORS["muted"]).grid(
            row=row, column=0, sticky="w", padx=(0, 16), pady=6
        )

    def _on_provider_change(self) -> None:
        provider = self.provider_var.get()
        self.model_var.set(DEFAULT_MODELS.get(provider, ""))
        self.base_url_var.set(DEFAULT_BASE_URLS.get(provider, ""))
        self.api_key_var.set((self.settings.api_keys or {}).get(provider, ""))

    def _save(self) -> None:
        provider = self.provider_var.get()
        api_keys = dict(self.settings.api_keys or {})
        api_keys[provider] = clean_env_value(self.api_key_var.get())
        next_settings = DesktopSettings(
            provider=provider,
            model=clean_env_value(self.model_var.get()),
            base_url=clean_env_value(self.base_url_var.get()),
            api_keys=api_keys,
            remember_keys=self.remember_var.get(),
        )
        try:
            # Validate everything except key presence, so a user can save a provider draft.
            if next_settings.base_url:
                validate_url(next_settings.base_url, name="Base URL")
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.on_save(next_settings)
        self.destroy()


def main() -> None:
    app = NeuroHubDesktop()
    app.mainloop()


if __name__ == "__main__":
    main()
