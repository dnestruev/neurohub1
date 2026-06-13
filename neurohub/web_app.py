"""Local browser UI for NeuroHub."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

import httpx

from .config import API_KEY_ENV, DEFAULT_BASE_URLS, DEFAULT_MODELS, ConfigError, ProviderConfig, clean_env_value, validate_url
from .models import ChatMessage
from .providers import create_provider

STATIC_PACKAGE = "neurohub.static"


class ApiError(Exception):
    """HTTP error returned to the browser as JSON."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def run_server(host: str = "127.0.0.1", port: int = 8765, *, open_browser: bool = True) -> None:
    """Start the local NeuroHub web application."""

    server = ThreadingHTTPServer((host, port), NeuroHubRequestHandler)
    url = f"http://{host}:{server.server_port}"
    print(f"NeuroHub web app: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NeuroHub...")
    finally:
        server.server_close()


class NeuroHubRequestHandler(BaseHTTPRequestHandler):
    """Small JSON/static HTTP handler with no external web framework dependency."""

    server_version = "NeuroHub/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/api/providers":
            self._send_json(
                {
                    "providers": [
                        {
                            "id": provider,
                            "apiKeyEnv": API_KEY_ENV[provider],
                            "defaultModel": DEFAULT_MODELS[provider],
                            "defaultBaseUrl": DEFAULT_BASE_URLS.get(provider, ""),
                        }
                        for provider in sorted(API_KEY_ENV)
                    ]
                }
            )
            return

        path = "index.html" if self.path in {"/", ""} else self.path.lstrip("/")
        if ".." in Path(path).parts:
            self.send_error(404)
            return
        self._send_static(path)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/api/chat":
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            result = asyncio.run(handle_chat(payload))
            self._send_json(result)
        except ApiError as exc:
            self._send_json({"error": exc.message}, status=exc.status)
        except Exception as exc:  # Keep the desktop app alive and show a useful UI error.
            self._send_json({"error": f"Unexpected NeuroHub error: {exc}"}, status=500)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            raise ApiError(400, "Empty request body")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(400, "Request body must be valid JSON") from exc

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: str) -> None:
        try:
            resource = resources.files(STATIC_PACKAGE).joinpath(path)
            if not resource.is_file():
                self.send_error(404)
                return
            body = resource.read_bytes()
        except (FileNotFoundError, ModuleNotFoundError):
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-cache")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


async def handle_chat(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate browser payload, call the selected provider and return a JSON response."""

    provider = clean_env_value(str(payload.get("provider") or "openai")).lower()
    if provider not in API_KEY_ENV:
        raise ApiError(400, f"Unknown provider: {provider}")

    api_key = clean_env_value(str(payload.get("apiKey") or ""))
    if not api_key or api_key in {"sk-...", "sk-ant-...", "sk-or-...", "gsk_..."}:
        raise ApiError(400, "Добавь настоящий API ключ в настройках слева.")

    model = clean_env_value(str(payload.get("model") or DEFAULT_MODELS[provider]))
    base_url = _resolve_base_url(provider, payload.get("baseUrl"))
    messages = _parse_messages(payload.get("messages"))

    config = ProviderConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)
    try:
        response = await create_provider(config).ask(messages)
    except httpx.HTTPStatusError as exc:
        raise ApiError(exc.response.status_code, _friendly_http_error(exc)) from exc
    except httpx.RequestError as exc:
        raise ApiError(502, f"Не удалось подключиться к API: {exc}") from exc
    except ConfigError as exc:
        raise ApiError(400, str(exc)) from exc

    return {
        "content": response.content,
        "provider": response.provider,
        "model": response.model,
        "usage": {"input": response.input_tokens, "output": response.output_tokens},
    }


def _resolve_base_url(provider: str, raw_base_url: object) -> str | None:
    raw = clean_env_value(str(raw_base_url or ""))
    if raw:
        return validate_url(raw, name="Base URL")
    default = DEFAULT_BASE_URLS.get(provider)
    return validate_url(default, name="Base URL") if default else None


def _parse_messages(raw_messages: object) -> list[ChatMessage]:
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ApiError(400, "Напиши сообщение перед отправкой.")

    messages: list[ChatMessage] = []
    for item in raw_messages[-30:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = clean_env_value(str(item.get("content") or ""))
        if role in {"system", "user", "assistant"} and content:
            messages.append(ChatMessage(role, content))  # type: ignore[arg-type]
    if not messages or messages[-1].role != "user":
        raise ApiError(400, "Последнее сообщение должно быть от пользователя.")
    return messages


def _friendly_http_error(exc: httpx.HTTPStatusError) -> str:
    status = exc.response.status_code
    details = _extract_error_detail(exc.response)
    if status == 401:
        return "API вернул 401 Unauthorized: проверь, что ключ настоящий и выбран правильный провайдер."
    if status == 403:
        return "API вернул 403 Forbidden: у ключа нет доступа к этой модели или провайдеру."
    if status == 404:
        return "API вернул 404: проверь модель и Base URL."
    if status == 429:
        return "API вернул 429: лимит запросов/баланса. Попробуй позже или проверь аккаунт."
    return f"API вернул HTTP {status}. {details}".strip()


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300]
    if error:
        return str(error)[:300]
    return str(data)[:300]


def _find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the NeuroHub local web app")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    port = _find_free_port(args.port) if args.host in {"127.0.0.1", "localhost"} else args.port
    run_server(args.host, port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
