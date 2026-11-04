"""
Servicio de verificación de actualizaciones de seeU.
Consulta GitHub Releases para detectar nuevas versiones y permite al usuario
actualizar o posponer las notificaciones.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from supervisor.repositories import settings_repository

CURRENT_VERSION = "1.0.4"
GITHUB_REPO = "Seavuelo/supervisor-personal"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def parse_version(tag: str):
    """Convierte una etiqueta como 'v1.0.3' o '1.0.3' en una tupla de enteros (1, 0, 3)."""
    clean = re.sub(r"^[^\d]*", "", str(tag).strip())
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)

def is_newer_version(latest_tag: str, current_ver: str = CURRENT_VERSION) -> bool:
    """Retorna True si latest_tag es estrictamente mayor que current_ver."""
    v_latest = parse_version(latest_tag)
    v_current = parse_version(current_ver)
    if not v_latest:
        return False
    return v_latest > v_current

class UpdateService:
    def __init__(self, current_version: str = CURRENT_VERSION):
        self.current_version = current_version

    def check_for_updates(self, manual: bool = False) -> dict:
        """
        Consulta la API de GitHub Releases para comprobar si existe una versión superior.
        Respeta las opciones de 'ignorar versión' y 'recordar más tarde' a menos que sea manual=True.
        """
        now = time.time()

        # Si no es manual, verificar si el usuario pidió recordar más tarde
        if not manual:
            remind_until = settings_repository.get_setting("update_remind_later_until")
            if remind_until:
                try:
                    if now < float(remind_until):
                        return {
                            "update_available": False,
                            "reason": "postponed",
                            "current_version": self.current_version
                        }
                except ValueError:
                    pass

        try:
            req = urllib.request.Request(
                API_URL,
                headers={
                    "User-Agent": "seeU-Desktop-Supervisor",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status != 200:
                    return {
                        "update_available": False,
                        "error": f"HTTP {resp.status}",
                        "current_version": self.current_version
                    }
                data = json.loads(resp.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").strip()
            release_name = data.get("name") or latest_tag
            release_notes = data.get("body") or "Mejoras generales de rendimiento, interfaz y estabilidad."
            release_html_url = data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"

            # Buscar asset de Windows Setup .exe
            download_url = release_html_url
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and "setup" in name:
                    download_url = asset.get("browser_download_url") or download_url
                    break

            if is_newer_version(latest_tag, self.current_version):
                # Verificar si el usuario ignoró específicamente esta versión
                ignored_ver = settings_repository.get_setting("update_ignored_version")
                if not manual and ignored_ver == latest_tag:
                    return {
                        "update_available": False,
                        "reason": "ignored",
                        "current_version": self.current_version,
                        "latest_version": latest_tag
                    }

                return {
                    "update_available": True,
                    "current_version": self.current_version,
                    "latest_version": latest_tag,
                    "release_name": release_name,
                    "release_notes": release_notes,
                    "download_url": download_url,
                    "release_url": release_html_url
                }
            else:
                return {
                    "update_available": False,
                    "reason": "up_to_date",
                    "current_version": self.current_version,
                    "latest_version": latest_tag
                }

        except Exception as e:
            return {
                "update_available": False,
                "error": str(e),
                "current_version": self.current_version
            }

    def set_update_preference(self, action: str, version: str) -> bool:
        """
        Guarda la decisión del usuario:
        - 'ignore': No volver a notificar sobre esta versión específica.
        - 'remind_later': Posponer el aviso por 24 horas.
        """
        if action == "ignore":
            settings_repository.set_setting("update_ignored_version", version)
            return True
        elif action == "remind_later":
            remind_time = time.time() + 86400  # 24 horas
            settings_repository.set_setting("update_remind_later_until", str(remind_time))
            return True
        return False
