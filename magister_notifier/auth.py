import base64
import hashlib
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests


class BrowserLoginError(RuntimeError):
    pass


class SecureTokenStore:
    """Encrypts OAuth tokens with Windows DPAPI for the current Windows user."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "oauth_tokens.bin"

    def save(self, token_data: dict) -> None:
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(token_data).encode("utf-8")
        self.path.write_bytes(self._protect(plaintext))

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            plaintext = self._unprotect(self.path.read_bytes())
            data = json.loads(plaintext.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, RuntimeError):
            return {}

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    @staticmethod
    def _protect(data: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        buffer = ctypes.create_string_buffer(data)
        blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        protected = DATA_BLOB()
        crypt32 = ctypes.windll.CryptProtectData
        crypt32.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.restype = wintypes.BOOL
        if not crypt32(ctypes.byref(blob), None, None, None, None, 0, ctypes.byref(protected)):
            raise RuntimeError("Windows kon de inlogsessie niet versleutelen.")
        result = ctypes.string_at(protected.pbData, protected.cbData)
        ctypes.windll.Kernel32.LocalFree(protected.pbData)
        return result

    @staticmethod
    def _unprotect(data: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        buffer = ctypes.create_string_buffer(data)
        blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        plaintext = DATA_BLOB()
        crypt32 = ctypes.windll.CryptUnprotectData
        crypt32.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.restype = wintypes.BOOL
        if not crypt32(ctypes.byref(blob), None, None, None, None, 0, ctypes.byref(plaintext)):
            raise RuntimeError("Windows kon de inlogsessie niet ontgrendelen.")
        result = ctypes.string_at(plaintext.pbData, plaintext.cbData)
        ctypes.windll.Kernel32.LocalFree(plaintext.pbData)
        return result


class MagisterBrowserAuth:
    def __init__(self, school_url: str, token_store: SecureTokenStore) -> None:
        self.school_url = self.normalize_school_url(school_url)
        self.token_store = token_store

    @staticmethod
    def normalize_school_url(value: str) -> str:
        value = value.strip()
        if not value:
            raise BrowserLoginError("Voer de Magister-school-URL in.")
        if "://" not in value:
            value = "https://" + value
        parsed = urlparse(value)
        host = parsed.netloc or parsed.path
        host = host.lower().rstrip("/")
        if "." not in host:
            raise BrowserLoginError("Gebruik een Magister-school-URL, bijvoorbeeld schaersvoorde.magister.net.")
        return f"https://{host}"

    def discover(self) -> dict:
        candidates = [
            f"{self.school_url}/.well-known/openid-configuration",
            "https://accounts.magister.net/.well-known/openid-configuration",
        ]
        oidc_config_url = f"{self.school_url}/oidc_config.js"
        try:
            config_response = requests.get(oidc_config_url, timeout=10)
            if config_response.ok:
                text = config_response.text
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    school_config = json.loads(text[start:end + 1])
                    candidates.insert(0, school_config.get("authority"))
        except (requests.RequestException, json.JSONDecodeError):
            pass

        for candidate in candidates:
            if not candidate:
                continue
            url = candidate if candidate.startswith("http") else f"{candidate}/.well-known/openid-configuration"
            try:
                response = requests.get(url, timeout=10)
                if response.ok:
                    data = response.json()
                    if data.get("authorization_endpoint") and data.get("token_endpoint"):
                        return data
            except requests.RequestException:
                continue
        raise BrowserLoginError("Magister-OpenID-informatie kon niet worden opgehaald.")

    def login(self, timeout_seconds: int = 300) -> dict:
        discovery = self.discover()
        authorization_endpoint = discovery["authorization_endpoint"]
        token_endpoint = discovery["token_endpoint"]

        result: dict = {}
        server_ready = threading.Event()

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(handler_self) -> None:
                query = parse_qs(urlparse(handler_self.path).query)
                if "error" in query:
                    result["error"] = query.get("error_description", query["error"])[0]
                else:
                    result["code"] = query.get("code", [""])[0]
                    result["state"] = query.get("state", [""])[0]
                handler_self.send_response(200)
                handler_self.send_header("Content-Type", "text/html; charset=utf-8")
                handler_self.end_headers()
                handler_self.wfile.write(
                    "<html><body><h2>Inloggen geslaagd</h2><p>Je kunt dit venster sluiten.</p></body></html>".encode("utf-8")
                )
                server_ready.set()

            def log_message(self, format, *args) -> None:
                return

        callback_server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
        port = callback_server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(24)

        subdomain = urlparse(self.school_url).hostname.split(".")[0]
        client_id = f"M6-{subdomain}.magister.net"
        parameters = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile calendar.user grades.read",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "acr_values": f"tenant:{subdomain}.magister.net",
        }
        authorization_url = authorization_endpoint + ("&" if "?" in authorization_endpoint else "?") + urlencode(parameters)
        webbrowser.open(authorization_url)

        thread = threading.Thread(target=callback_server.handle_request, daemon=True)
        thread.start()
        if not server_ready.wait(timeout_seconds):
            callback_server.server_close()
            raise BrowserLoginError("Het browservenster kreeg binnen 5 minuten geen loginantwoord.")

        callback_server.server_close()
        if result.get("error"):
            raise BrowserLoginError(result["error"])
        if result.get("state") != state:
            raise BrowserLoginError("De beveiligingsstatus van de login kwam niet overeen.")
        if not result.get("code"):
            raise BrowserLoginError("Magister heeft geen autorisatiecode teruggegeven.")

        exchange = requests.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": result["code"],
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
            timeout=20,
        )
        if not exchange.ok:
            raise BrowserLoginError(
                "De browserlogin is gestart, maar Magister heeft de desktop-redirect niet geaccepteerd. "
                f"Details: {exchange.text[:180]}"
            )
        tokens = exchange.json()
        tokens["school_url"] = self.school_url
        tokens["client_id"] = client_id
        tokens["token_endpoint"] = token_endpoint
        self.token_store.save(tokens)
        return tokens

    def refresh(self) -> dict:
        tokens = self.token_store.load()
        refresh_token = tokens.get("refresh_token")
        token_endpoint = tokens.get("token_endpoint")
        client_id = tokens.get("client_id")
        if not refresh_token or not token_endpoint or not client_id:
            raise BrowserLoginError("Er is geen vernieuwingstoken opgeslagen. Log opnieuw in.")
        response = requests.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
                "scope": "openid profile calendar.user grades.read",
            },
            timeout=20,
        )
        if not response.ok:
            raise BrowserLoginError("Het inlogtoken kon niet worden vernieuwd.")
        new_tokens = response.json()
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = refresh_token
        new_tokens["school_url"] = tokens.get("school_url", self.school_url)
        new_tokens["client_id"] = client_id
        new_tokens["token_endpoint"] = token_endpoint
        self.token_store.save(new_tokens)
        return new_tokens
