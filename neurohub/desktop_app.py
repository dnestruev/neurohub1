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
    ("openai", "GPT-4o mini", "gpt-4o-mini", "⚡"),
    ("openai", "GPT-4.1", "gpt-4.1", "✦"),
    ("anthropic", "Claude Sonnet", "claude-3-5-sonnet-20241022", "✹"),
    ("deepseek", "DeepSeek", "deepseek-chat", "◆"),
    ("groq", "Groq Llama", "llama-3.3-70b-versatile", "●"),
    ("gemini", "Gemini Flash", "gemini-2.0-flash", "✧"),
]

SUGGESTIONS = [
    "Сделай план проекта",
    "Объясни ошибку в коде",
    "Напиши красивый README",
    "Сравни модели для задачи",
]

COLORS = {
    "app": "#f6f7fb",
    "surface": "#ffffff",
    "surface_2": "#f1f4f8",
    "sidebar": "#101827",
    "sidebar_2": "#172033",
    "text": "#111827",
    "text_inverse": "#f9fafb",
    "muted": "#667085",
    "muted_inverse": "#a7b0c0",
    "border": "#e6e8ef",
    "accent": "#10a37f",
    "accent_2": "#0ea5e9",
    "accent_soft": "#e8f8f2",
    "danger": "#dc2626",
    "danger_soft": "#fff1f2",
    "user": "#eef4ff",
    "assistant": "#ffffff",
    "code": "#0f172a",
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


class ScrollFrame(tk.Frame):
    """Scrollable frame for chat messages."""

    def __init__(self, parent: tk.Widget, *, bg: str) -> None:
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _event: tk.Event[Any]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[Any]) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event[Any]) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_to_bottom(self) -> None:
        self.update_idletasks()
        self.canvas.yview_moveto(1.0)


class NeuroHubDesktop(tk.Tk):
    """Native desktop chat application with a modern app shell."""

    def __init__(self) -> None:
        super().__init__()
        self.title("NeuroHub — Desktop AI Workspace")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg=COLORS["app"])

        self.settings = load_desktop_settings()
        self.messages: list[ChatMessage] = []
        self.result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_busy = False
        self.chat_title_var = tk.StringVar(value="Новый чат")

        self._setup_style()
        self._build_layout()
        self._render_welcome()
        self.after(120, self._poll_result_queue)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar", background=COLORS["surface_2"], troughcolor=COLORS["app"])
        style.configure("TCombobox", padding=8)

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self, bg=COLORS["sidebar"], width=252)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        brand = tk.Frame(sidebar, bg=COLORS["sidebar"], padx=20, pady=22)
        brand.pack(fill="x")
        tk.Label(
            brand,
            text="✣",
            width=2,
            bg=COLORS["accent"],
            fg="#ffffff",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")
        title = tk.Frame(brand, bg=COLORS["sidebar"])
        title.pack(side="left", padx=12)
        tk.Label(title, text="NeuroHub", bg=COLORS["sidebar"], fg=COLORS["text_inverse"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title, text="AI workspace", bg=COLORS["sidebar"], fg=COLORS["muted_inverse"], font=("Segoe UI", 9)).pack(anchor="w")

        tk.Button(
            sidebar,
            text="＋  New chat",
            command=self._new_chat,
            relief="flat",
            bg=COLORS["accent"],
            fg="#ffffff",
            activebackground="#0e8f70",
            padx=18,
            pady=11,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(8, 18))

        tk.Label(sidebar, text="MODELS", bg=COLORS["sidebar"], fg=COLORS["muted_inverse"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20)
        self.model_list = tk.Frame(sidebar, bg=COLORS["sidebar"], padx=14, pady=8)
        self.model_list.pack(fill="x")
        self._rebuild_model_list()

        bottom = tk.Frame(sidebar, bg=COLORS["sidebar"], padx=18, pady=18)
        bottom.pack(side="bottom", fill="x")
        tk.Button(bottom, text="⚙  API keys", command=self._open_settings_dialog, relief="flat", bg=COLORS["sidebar_2"], fg=COLORS["text_inverse"], padx=14, pady=10, anchor="w").pack(fill="x", pady=(0, 8))
        tk.Button(bottom, text="↧  Export JSON", command=self._export_chat, relief="flat", bg=COLORS["sidebar_2"], fg=COLORS["text_inverse"], padx=14, pady=10, anchor="w").pack(fill="x")

    def _build_main(self) -> None:
        main = tk.Frame(self, bg=COLORS["app"])
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        topbar = tk.Frame(main, bg=COLORS["app"], padx=28, pady=18)
        topbar.grid(row=0, column=0, sticky="ew")
        tk.Entry(
            topbar,
            textvariable=self.chat_title_var,
            relief="flat",
            bg=COLORS["app"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
            width=28,
        ).pack(side="left")
        self.status_pill = tk.Label(
            topbar,
            text=self._status_text(),
            bg=COLORS["accent_soft"],
            fg=COLORS["accent"],
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        )
        self.status_pill.pack(side="right")

        self.messages_frame = ScrollFrame(main, bg=COLORS["app"])
        self.messages_frame.grid(row=1, column=0, sticky="nsew", padx=28)

        self._build_composer(main)

    def _build_composer(self, parent: tk.Widget) -> None:
        composer_outer = tk.Frame(parent, bg=COLORS["app"], padx=28, pady=(14, 24))
        composer_outer.grid(row=2, column=0, sticky="ew")
        composer_outer.columnconfigure(0, weight=1)

        composer = tk.Frame(
            composer_outer,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        composer.grid(row=0, column=0, sticky="ew")
        composer.columnconfigure(0, weight=1)

        tools = tk.Frame(composer, bg=COLORS["surface"])
        tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._tool_button(tools, "📎 Attach").pack(side="left", padx=(0, 8))
        self._tool_button(tools, "🔭 Deep research").pack(side="left", padx=(0, 8))
        self._tool_button(tools, "🎨 Create image").pack(side="left")
        tk.Label(tools, text="Ctrl+Enter to send", bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(side="right")

        self.prompt = tk.Text(
            composer,
            height=4,
            wrap="word",
            relief="flat",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            padx=4,
            pady=4,
            font=("Segoe UI", 12),
        )
        self.prompt.grid(row=1, column=0, sticky="ew", padx=(0, 12))
        self.prompt.bind("<Control-Return>", lambda _event: self._send_message())
        self.prompt.bind("<Command-Return>", lambda _event: self._send_message())

        self.send_button = tk.Button(
            composer,
            text="➤",
            command=self._send_message,
            relief="flat",
            bg=COLORS["text"],
            fg="#ffffff",
            activebackground="#000000",
            width=4,
            height=2,
            font=("Segoe UI", 13, "bold"),
        )
        self.send_button.grid(row=1, column=1, sticky="se")

    def _tool_button(self, parent: tk.Widget, text: str) -> tk.Button:
        return tk.Button(parent, text=text, relief="flat", bg=COLORS["surface_2"], fg=COLORS["muted"], padx=10, pady=6)

    def _rebuild_model_list(self) -> None:
        for child in self.model_list.winfo_children():
            child.destroy()
        for provider, label, model, icon in MODEL_PRESETS:
            selected = self.settings.provider == provider and self.settings.model == model
            tk.Button(
                self.model_list,
                text=f"{icon}  {label}",
                command=lambda next_provider=provider, next_model=model: self._select_model(next_provider, next_model),
                relief="flat",
                bg=COLORS["accent_soft"] if selected else COLORS["sidebar"],
                fg=COLORS["accent"] if selected else COLORS["muted_inverse"],
                activebackground=COLORS["sidebar_2"],
                padx=12,
                pady=9,
                anchor="w",
                font=("Segoe UI", 10, "bold" if selected else "normal"),
            ).pack(fill="x", pady=3)

    def _render_welcome(self) -> None:
        self._clear_messages_ui()
        hero = tk.Frame(self.messages_frame.inner, bg=COLORS["app"])
        hero.pack(fill="both", expand=True, pady=(70, 20))
        tk.Label(hero, text="✣", bg=COLORS["app"], fg=COLORS["text"], font=("Segoe UI", 42, "bold")).pack()
        tk.Label(hero, text="How can I help you today?", bg=COLORS["app"], fg=COLORS["text"], font=("Segoe UI", 24, "bold")).pack(pady=(8, 8))
        tk.Label(hero, text="Выбери модель слева, добавь ключ в API keys и начни диалог.", bg=COLORS["app"], fg=COLORS["muted"], font=("Segoe UI", 11)).pack()
        chips = tk.Frame(hero, bg=COLORS["app"])
        chips.pack(pady=24)
        for suggestion in SUGGESTIONS:
            tk.Button(
                chips,
                text=suggestion,
                command=lambda value=suggestion: self._use_suggestion(value),
                relief="flat",
                bg=COLORS["surface"],
                fg=COLORS["text"],
                padx=14,
                pady=9,
                highlightbackground=COLORS["border"],
                highlightthickness=1,
            ).pack(side="left", padx=6)

    def _use_suggestion(self, text: str) -> None:
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", text)
        self.prompt.focus_set()

    def _clear_messages_ui(self) -> None:
        for child in self.messages_frame.inner.winfo_children():
            child.destroy()

    def _select_model(self, provider: str, model: str) -> None:
        self.settings.provider = provider
        self.settings.model = model
        self.settings.base_url = DEFAULT_BASE_URLS.get(provider, "")
        self._refresh_status()
        save_desktop_settings(self.settings)
        self._rebuild_model_list()

    def _open_settings_dialog(self) -> None:
        SettingsDialog(self, self.settings, self._apply_settings)

    def _apply_settings(self, settings: DesktopSettings) -> None:
        self.settings = settings
        save_desktop_settings(settings)
        self._refresh_status()
        self._rebuild_model_list()

    def _new_chat(self) -> None:
        self.messages.clear()
        self.chat_title_var.set("Новый чат")
        self._render_welcome()
        self._refresh_status("Новый чат готов")

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
        self._refresh_status(f"Чат сохранён: {path}")

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

        if not self.messages:
            self._clear_messages_ui()
            self.chat_title_var.set(text[:48] + ("…" if len(text) > 48 else ""))
        self.prompt.delete("1.0", "end")
        user_message = ChatMessage("user", text)
        self.messages.append(user_message)
        self._append_message("Ты", text, is_user=True)
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
            self._append_message("NeuroHub", str(payload), is_user=False, markdown=True)
            self._set_busy(False, self._status_text())
        else:
            self._append_message("Ошибка", str(payload), is_user=False, error=True)
            self._set_busy(False, "Исправь настройки и попробуй снова")
        self.after(120, self._poll_result_queue)

    def _append_message(
        self,
        role: str,
        content: str,
        *,
        is_user: bool,
        markdown: bool = False,
        error: bool = False,
    ) -> None:
        row = tk.Frame(self.messages_frame.inner, bg=COLORS["app"])
        row.pack(fill="x", pady=9, padx=18)

        bubble = tk.Frame(
            row,
            bg=COLORS["danger_soft"] if error else COLORS["user"] if is_user else COLORS["assistant"],
            highlightbackground="#fecdd3" if error else COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        bubble.pack(side="right" if is_user else "left", anchor="e" if is_user else "w", padx=(180, 0) if is_user else (0, 180))
        tk.Label(bubble, text=role, bg=bubble["bg"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        if markdown:
            self._insert_markdown_widgets(bubble, content)
        else:
            tk.Label(
                bubble,
                text=content,
                bg=bubble["bg"],
                fg=COLORS["danger"] if error else COLORS["text"],
                justify="left",
                wraplength=660,
                font=("Segoe UI", 11),
            ).pack(anchor="w", pady=(4, 0))
        self.messages_frame.scroll_to_bottom()

    def _insert_markdown_widgets(self, parent: tk.Frame, content: str) -> None:
        in_code = False
        code_lines: list[str] = []
        for raw_line in content.splitlines() or [content]:
            line = raw_line.rstrip()
            if line.startswith("```"):
                if in_code:
                    self._markdown_label(parent, "\n".join(code_lines), code=True)
                    code_lines.clear()
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(line)
                continue
            if line.startswith("# "):
                self._markdown_label(parent, line[2:], heading=True)
            elif line.startswith("## "):
                self._markdown_label(parent, line[3:], heading=True)
            elif line.startswith(("- ", "* ")):
                self._markdown_label(parent, "• " + line[2:])
            elif line:
                self._markdown_label(parent, line)
        if code_lines:
            self._markdown_label(parent, "\n".join(code_lines), code=True)

    def _markdown_label(self, parent: tk.Frame, text: str, *, heading: bool = False, code: bool = False) -> None:
        bg = COLORS["code"] if code else parent["bg"]
        fg = "#e5e7eb" if code else COLORS["text"]
        font = ("Consolas", 10) if code else ("Segoe UI", 13, "bold") if heading else ("Segoe UI", 11)
        tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            justify="left",
            wraplength=660,
            font=font,
            padx=10 if code else 0,
            pady=8 if code else 2,
        ).pack(anchor="w", fill="x" if code else "none", pady=(5 if heading or code else 1, 0))

    def _set_busy(self, busy: bool, status: str) -> None:
        self.is_busy = busy
        self.send_button.configure(text="…" if busy else "➤", state="disabled" if busy else "normal")
        self._refresh_status(status)

    def _refresh_status(self, text: str | None = None) -> None:
        self.status_pill.configure(text=text or self._status_text())

    def _status_text(self) -> str:
        return f"{self.settings.provider} · {self.settings.model}"


class SettingsDialog(tk.Toplevel):
    """API key and provider settings dialog."""

    def __init__(self, parent: NeuroHubDesktop, settings: DesktopSettings, on_save: Any) -> None:
        super().__init__(parent)
        self.title("NeuroHub settings")
        self.configure(bg=COLORS["app"])
        self.geometry("520x390")
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
        card = tk.Frame(self, bg=COLORS["surface"], padx=24, pady=22, highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(card, text="API keys & provider", bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        self._label(card, "Провайдер", 1)
        provider_box = ttk.Combobox(card, textvariable=self.provider_var, values=sorted(API_KEY_ENV), state="readonly")
        provider_box.grid(row=1, column=1, sticky="ew", pady=7)

        self._label(card, "API ключ", 2)
        tk.Entry(card, textvariable=self.api_key_var, show="•", width=44, relief="flat", bg=COLORS["surface_2"], fg=COLORS["text"]).grid(row=2, column=1, sticky="ew", pady=7, ipady=8)

        tk.Checkbutton(card, text="Сохранить ключ локально на этом ПК", variable=self.remember_var, bg=COLORS["surface"], fg=COLORS["muted"], activebackground=COLORS["surface"]).grid(row=3, column=1, sticky="w", pady=(0, 8))

        self._label(card, "Модель", 4)
        tk.Entry(card, textvariable=self.model_var, width=44, relief="flat", bg=COLORS["surface_2"], fg=COLORS["text"]).grid(row=4, column=1, sticky="ew", pady=7, ipady=8)

        self._label(card, "Base URL", 5)
        tk.Entry(card, textvariable=self.base_url_var, width=44, relief="flat", bg=COLORS["surface_2"], fg=COLORS["text"]).grid(row=5, column=1, sticky="ew", pady=7, ipady=8)

        buttons = tk.Frame(card, bg=COLORS["surface"])
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(18, 0))
        tk.Button(buttons, text="Cancel", command=self.destroy, relief="flat", bg=COLORS["surface_2"], padx=16, pady=9).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="Save", command=self._save, relief="flat", bg=COLORS["accent"], fg="#ffffff", padx=20, pady=9).pack(side="left")
        card.columnconfigure(1, weight=1)

    @staticmethod
    def _label(parent: tk.Widget, text: str, row: int) -> None:
        tk.Label(parent, text=text, bg=COLORS["surface"], fg=COLORS["muted"]).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=7)

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
