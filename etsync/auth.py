import secrets
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tomli_w

from etsync.config import _root, settings

_CALLBACK_HOST = "localhost"
_CALLBACK_PORT = 8888
_CALLBACK_PATH = "/callback"


def _secrets_path() -> Path:
    return _root / ".secrets.toml"


def _save_tokens(access_token: str, refresh_token: str, expires_at: float) -> None:
    """Save tokens to .secrets.toml, preserving existing content."""
    path = _secrets_path()
    data: dict = {}
    if path.exists():
        import tomllib

        data = tomllib.loads(path.read_text())

    # Find the existing section (case-insensitive) or use the current env name
    target_env = settings.current_env
    for key in data:
        if key.lower() == target_env.lower():
            target_env = key
            break
    if target_env not in data:
        data[target_env] = {}
    data[target_env]["access_token"] = access_token
    data[target_env]["refresh_token"] = refresh_token
    data[target_env]["expires_at"] = expires_at

    path.write_bytes(tomli_w.dumps(data).encode())


def refresh_save(token: str, refresh_token: str, expiry: datetime) -> None:
    """Callback for etsyv3.EtsyAPI to persist refreshed tokens."""
    _save_tokens(token, refresh_token, expiry.timestamp())


def _wait_for_callback() -> tuple[str, str]:
    """Start a temporary HTTP server and wait for the OAuth callback.

    Returns (code, state) from the callback query params.
    """
    result: dict[str, str] = {}
    error: list[str] = []

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != _CALLBACK_PATH:
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            if "error" in params:
                error.append(params["error"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization failed.</h1><p>You can close this tab.</p>")
            elif "code" in params and "state" in params:
                result["code"] = params["code"][0]
                result["state"] = params["state"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
            else:
                self.send_response(400)
                self.end_headers()

            # Shut down the server after handling the callback
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # suppress request logs

    import socket

    class DualStackHTTPServer(HTTPServer):
        address_family = socket.AF_INET6

        def server_bind(self) -> None:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    server = DualStackHTTPServer(("::", _CALLBACK_PORT), CallbackHandler)
    server.serve_forever()

    if error:
        raise SystemExit(f"OAuth error: {error[0]}")
    if "code" not in result:
        raise SystemExit("No authorization code received.")

    return result["code"], result["state"]


def login() -> None:
    """Run OAuth 2.0 consent flow and persist tokens."""
    from etsyv3.util.auth import AuthHelper

    keystring = settings.api_keystring
    redirect_uri = settings.get("redirect_uri", f"http://{_CALLBACK_HOST}:{_CALLBACK_PORT}{_CALLBACK_PATH}")
    scopes = settings.get("scopes", ["listings_r"])

    code_verifier = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(16)

    helper = AuthHelper(
        keystring=keystring,
        redirect_uri=redirect_uri,
        scopes=scopes,
        code_verifier=code_verifier,
        state=state,
    )

    auth_url, auth_state = helper.get_auth_code()
    print(f"Opening browser for Etsy authorization...\n{auth_url}")
    print(f"Waiting for callback on {redirect_uri} ...")
    print(f"\nOpen this URL in your browser:\n{auth_url}\n")

    code, callback_state = _wait_for_callback()
    helper.set_authorisation_code(code, callback_state)

    # get_access_token() is typed as Optional[str] but returns a dict at runtime
    raw_response = helper.get_access_token()
    if raw_response is None:
        print("Error: failed to obtain access token.")
        raise SystemExit(1)

    token_response: dict = raw_response  # type: ignore[assignment]
    access_token = token_response["access_token"]
    new_refresh_token = token_response["refresh_token"]
    expires_in = token_response["expires_in"]
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp()

    _save_tokens(access_token, new_refresh_token, expires_at)
    print("Login successful. Tokens saved.")
