import os
import json
import re
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import keyring
from keyring.errors import KeyringError
from supervisor.models.task import RECURRING, occurrence_on_or_after
from supervisor.repositories import settings_repository

load_dotenv()

# Modelos oficiales soportados por Google AI Studio (ordenados por disponibilidad y cuota)
CANDIDATE_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)
KEYRING_SERVICE = "seeU"
KEYRING_ACCOUNT = "Gemini API"


def _save_key(key: str):
    keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, key)
    settings_repository.delete_setting("gemini_api_key")


class AIService:
    def __init__(self):
        legacy_key = settings_repository.get_setting("gemini_api_key")
        try:
            saved_key = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
            if legacy_key:
                if saved_key:
                    settings_repository.delete_setting("gemini_api_key")
                else:
                    _save_key(legacy_key)
                    saved_key = legacy_key
        except (KeyringError, OSError):
            saved_key = legacy_key
        self.api_key = saved_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self.active_model = CANDIDATE_MODELS[0]
        self.connection_status = "configured" if self.api_key else "offline"
        self.history: List[Dict[str, str]] = []

    @staticmethod
    def _new_client(key):
        from google import genai
        from google.genai.types import HttpOptions, HttpRetryOptions

        return genai.Client(
            api_key=key, vertexai=False,
            http_options=HttpOptions(timeout=8000, retry_options=HttpRetryOptions(attempts=1)),
        )

    def set_api_key(self, key: str) -> Dict[str, Any]:
        key = key.strip()
        if not key or any(char.isspace() for char in key):
            return {"status": "error", "message": "Pega la clave de Gemini completa, sin espacios ni saltos de línea."}
        try:
            client = self._new_client(key)
        except (ImportError, ValueError):
            return {"status": "error", "message": "No se pudo iniciar el componente de Gemini. Reinstala seeU."}
        result = self._probe(client)
        if result["status"] != "ok":
            client.close()
            if not self.api_key:
                self.connection_status = "error"
            return result
        if self.client:
            self.client.close()
        self.api_key, self.client = key, client
        self.active_model = result["model"]
        self.connection_status = "ok"
        try:
            _save_key(key)
        except (KeyringError, OSError):
            result["message"] += " El almacén de credenciales no está disponible. La clave dura solo esta sesión."
        return result

    def get_api_key_masked(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "••••••••"
        return self.api_key[:4] + "••••••••" + self.api_key[-4:]

    def get_connection_status(self) -> Dict[str, Any]:
        """Comprobación ultra-rápida y no bloqueante para el inicio de la app."""
        return {"status": self.connection_status}

    def test_connection(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "offline",
                "message": "Sin clave configurada. Operando en modo local autónomo."
            }

        try:
            if not self.client:
                self.client = self._new_client(self.api_key)
        except (ImportError, ValueError):
            self.connection_status = "error"
            return {
                "status": "error",
                "message": "No se pudo iniciar el componente de Gemini. Reinstala seeU."
            }
        result = self._probe(self.client)
        self.connection_status = result["status"]
        if result["status"] == "ok":
            self.active_model = result["model"]
        return result

    def _generate(self, client, prompt, **options):
        from google.genai.errors import APIError

        retryable = None
        models = (self.active_model, *(model for model in CANDIDATE_MODELS if model != self.active_model))
        for model in models:
            try:
                response = client.models.generate_content(model=model, contents=prompt, **options)
                if response.text:
                    return response.text.strip(), model
            except APIError as error:
                if error.code not in (404, 429, 500, 502, 503, 504):
                    raise
                if retryable is None or error.code == 429 or (retryable.code == 404 and error.code != 404):
                    retryable = error
        if retryable:
            raise retryable
        raise ValueError("Respuesta vacía de Gemini")

    def _probe(self, client):
        from google.genai.errors import APIError
        from httpx import TimeoutException, TransportError

        try:
            _, model = self._generate(client, "Responde solo la palabra OK")
            return {
                "status": "ok", "model": model,
                "message": f"Conectado a Google Gemini ({model})."
            }
        except APIError as error:
            code = error.code
            if code == 401 or "API_KEY_INVALID" in str(error.details) or "API_KEY_EXPIRED" in str(error.details):
                message = "Google rechazó la clave. Verifica que siga activa en Google AI Studio."
            elif code == 403:
                message = "Google denegó el acceso (403). Revisa las restricciones de la clave y los permisos del proyecto en AI Studio."
            elif code == 402 or error.status == "FAILED_PRECONDITION":
                message = f"El proyecto no cumple los requisitos de Gemini ({code}). Revisa la región y la facturación en AI Studio."
            elif code == 429:
                message = "Gemini alcanzó un límite de solicitudes o de cuota (429). Revisa el uso del proyecto o vuelve a intentar más tarde."
            elif code == 404:
                message = "El proyecto no tiene acceso a los modelos compatibles (404). Revisa su disponibilidad en Google AI Studio."
            else:
                message = f"Gemini devolvió un error ({code}). Vuelve a intentar más tarde."
        except (TimeoutException, TimeoutError):
            message = "Se agotó el tiempo de espera. Revisa la conexión o el proxy y vuelve a probar."
        except (TransportError, OSError):
            message = "No se pudo llegar a Google. Revisa tu conexión, proxy, firewall o certificados."
        except ValueError:
            message = "Gemini respondió sin texto. Vuelve a intentar más tarde."
        return {"status": "error", "message": message}

    def clear_history(self):
        """Reinicia el contexto de la conversación con el agente."""
        self.history = []

    def process_input(self, user_text: str) -> Dict[str, Any]:
        """
        Punto de entrada conversacional multi-turno.
        Mantiene el contexto acumulado de la sesión para que el agente dialogue de verdad.
        """
        text = user_text.strip()
        if not text:
            return {"action": "none"}

        # Registrar entrada del usuario en el historial
        self.history.append({"role": "user", "text": text})

        # Mantener solo los últimos 10 turnos para agilidad mental
        if len(self.history) > 10:
            self.history = self.history[-10:]

        if self.api_key and self.connection_status != "error":
            try:
                if not self.client:
                    self.client = self._new_client(self.api_key)
                result = self._call_gemini_conversational()
                self.connection_status = "ok"
                assistant_msg = result.get("message") or result.get("question") or ""
                if assistant_msg:
                    self.history.append({"role": "assistant", "text": assistant_msg})
                return result
            except Exception:
                self.connection_status = "error"

        # Motor Local Autónomo adaptativo
        result = self._local_conversational_agent(text)
        assistant_msg = result.get("message") or result.get("question") or ""
        if assistant_msg:
            self.history.append({"role": "assistant", "text": assistant_msg})
        return result

    def _call_gemini_conversational(self) -> Dict[str, Any]:
        now = datetime.now()
        fecha_actual = now.strftime("%Y-%m-%d (%A)")

        # Historial de conversación
        history_str = "\n".join([f"{msg['role'].upper()}: {msg['text']}" for msg in self.history])

        prompt = f"""
Eres seeU, un supervisor personal empático, inteligente y sobrio. Tu misión es ayudar a una persona que siente sobrecarga cognitiva y agobio mental a definir, negociar y clasificar sus actividades de forma tranquila y sin parálisis.

Fecha y hora de referencia: {fecha_actual}, {now.strftime("%H:%M")}.

HISTORIAL DE LA CONVERSACIÓN RECIENTE:
{history_str}

REGLAS DE CLASIFICACIÓN INTELIGENTE (El usuario puede escribir desde cualquier sección sin tener que especificar a dónde va):

1. DESTINO METAS (action: "create_goal" o "propose_tasks" con is_goal: true):
   - Aplica si el texto expresa un objetivo a mediano/largo plazo, aspiración, proyecto, aprendizaje de una habilidad, reto o hábito mayor ("aprender python", "aprender inglés", "leer 12 libros este año", "ahorrar 1 millón de pesos", "bajar 5 kilos", "preparar una maratón", "lanzar mi startup", "meta: terminar tesis", "mi objetivo es...", "comprar un auto").
   - Devuelve action: "create_goal", goal_title: "...", category: "estudio" | "salud" | "finanzas" | "trabajo" | "personal", y en tasks incluye 3 pasos iniciales concretos de baja fricción para comenzar.
   - O si el usuario pide ayuda para desglosar algo o necesita estructuración, usa action: "propose_tasks" con is_goal: true y los micro-pasos.

2. DESTINO AGENDA (action: "scheduled_task" o "question", destination: "agenda"):
   - Aplica para citas médicas (dentista, doctor), reuniones, compromisos con hora o fecha específica, fechas importantes, celebraciones o recordatorios periódicos ("el 19 de cada mes por mi cumplemes", "dentista martes a las 8 am", "mañana doctor", "reunión viernes 15:00", "cumpleaños").
   - IMPORTANTE: Las citas, recordatorios y celebraciones pertenecen EXCLUSIVAMENTE a la Agenda. NO son tareas de Foco diario para hacer ticks.
   - Si es un recordatorio recurrente mensual (ej: "de cada mes", "todos los 19", "mensualmente"), asigna recurrence: "monthly".
   - Devuelve action: "scheduled_task", destination: "agenda", scheduled_date en formato YYYY-MM-DD, scheduled_time en formato HH:MM (o null), task_type: "appointment", recurrence: "monthly" | "weekly" | "none", tag con la fecha/hora legible.
   - Si es una cita médica o reunión donde la hora exacta es fundamental pero no se dio, devuelve action: "question" con destination: "agenda" preguntando a qué hora está programada.

3. DESTINO FOCO (action: "quick_task", destination: "focus"):
   - Aplica para actividades rápidas del día a día, to-dos de hoy o hábitos cotidianos de tick diario ("comprar pan", "llamar a Carlos", "terminar el informe hoy", "hacer ejercicio todos los días").
   - IMPORTANTE: Viven EXCLUSIVAMENTE en Foco de Hoy. NO aparecen en Agenda.
   - Si es un hábito repetitivo diario ("todos los días"), asigna task_type: "daily" y recurrence: "daily".
   - Devuelve action: "quick_task", destination: "focus", scheduled_date: null o fecha de hoy, tag: "Hoy" (o "Diaria").

4. RESPUESTA A RECHAZOS O DUDAS:
   - Si el usuario dice que no quiere algo o pide otra alternativa, usa action: "question" para reconducir con serenidad.

RESPONDE ÚNICAMENTE UN JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
  "action": "create_goal" | "scheduled_task" | "quick_task" | "question" | "propose_tasks",
  "destination": "goals" | "agenda" | "focus",
  "message": "Tu respuesta serena al usuario indicando claramente dónde se guardó (Metas, Agenda o Foco)",
  "question": "Pregunta si aplica",
  "options": ["Opcion 1", "Opcion 2", "Opcion 3"],
  "allow_custom": true,
  "custom_placeholder": "Placeholder para responder",
  "is_goal": true | false,
  "goal_title": "Título si es meta",
  "category": "estudio" | "salud" | "finanzas" | "trabajo" | "personal",
  "tasks": [
    {{"title": "Actividad o paso muy concreto", "tag": "Hoy", "scheduled_time": null, "scheduled_date": null, "task_type": "quick" | "daily" | "micro_step" | "appointment", "recurrence": "none" | "daily" | "weekly" | "monthly"}}
  ]
}}
"""
        text, model = self._generate(self.client, prompt, config={"response_mime_type": "application/json"})
        parsed = json.loads(text)
        act = parsed.get("action")
        if act == "create_goal" or parsed.get("is_goal"):
            parsed.setdefault("destination", "goals")
        elif act == "scheduled_task":
            parsed.setdefault("destination", "agenda")
        elif act == "quick_task":
            parsed.setdefault("destination", "focus")
        self.active_model = model
        return parsed

    def _local_conversational_agent(self, current_text: str) -> Dict[str, Any]:
        """
        Motor Local Autónomo con máquina de estados, memoria de contexto y clasificación tripartita
        (Metas vs Agenda vs Foco).
        Permite ingresar cualquier actividad desde la barra global sin especificar prefijos.
        """
        lower = current_text.lower().strip()
        now = datetime.now()

        prev_user_msgs = [m["text"] for m in self.history[:-1] if m["role"] == "user"]
        prev_assistant_msgs = [m["text"] for m in self.history if m["role"] == "assistant"]
        last_assistant_msg = prev_assistant_msgs[-1].lower() if prev_assistant_msgs else ""
        last_user_msg = prev_user_msgs[-1].lower() if prev_user_msgs else ""

        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", lower)
        am_pm_match = re.search(r"(?:a las\s+)?(\d{1,2})\s*(am|pm)\b", lower)
        hour_match = re.search(r"\ba las\s+(\d{1,2})\b", lower)
        if time_match:
            detected_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        elif am_pm_match:
            h = int(am_pm_match.group(1))
            if am_pm_match.group(2) == "pm" and h < 12:
                h += 12
            elif am_pm_match.group(2) == "am" and h == 12:
                h = 0
            detected_time = f"{h:02d}:00"
        elif hour_match:
            detected_time = f"{int(hour_match.group(1)):02d}:00"
        else:
            detected_time = None

        # 0. RESOLUCIÓN DE HORA TRAS PREGUNTA DE CITA PREVIA
        if detected_time and ("a qué hora" in last_assistant_msg or "agendemos" in last_assistant_msg):
            palabras_cita = ["cita", "médico", "medico", "dentista", "doctor", "doctora", "reunión", "reunion"]
            appt_title = next((m for m in reversed(prev_user_msgs) if any(w in m.lower() for w in palabras_cita)), "Cita médica")
            return {
                "action": "scheduled_task",
                "destination": "agenda",
                "message": f"He agendado '{appt_title}' para las {detected_time} en tu Agenda.",
                "tasks": [
                    {
                        "title": appt_title,
                        "tag": f"Cita {detected_time}",
                        "scheduled_time": detected_time,
                        "scheduled_date": (now + timedelta(days=1)).strftime("%Y-%m-%d") if "mañana" in appt_title.lower() else now.strftime("%Y-%m-%d"),
                        "task_type": "appointment"
                    }
                ]
            }

        # 1. DETECCIÓN DE RECHAZO O CAMBIO DE RUMBO
        if any(w in lower for w in ["no quiero", "otra actividad", "otras actividades", "otra cosa", "cambiar", "no me gusta", "algo distinto", "mejor no"]):
            return {
                "action": "question",
                "destination": "focus",
                "message": "Entendido, cambiamos de enfoque por completo. Para evitar agobio, ¿qué tipo de actividad prefieres ahora y de cuánto tiempo dispones?",
                "options": [
                    "Tareas prácticas cortas",
                    "Ordenar apuntes y notas",
                    "Pausa activa o descanso",
                    "Avanzar en un proyecto pendiente"
                ],
                "allow_custom": True,
                "custom_placeholder": "Ej: Tengo 45 minutos y prefiero ordenar mi escritorio..."
            }

        # 2. HÁBITOS RECURRENTES (ej: "hacer ejercicio todos los días", "tomar agua todos los días")
        if any(w in lower for w in ["todos los días", "todos los dias", "cada día", "cada dia", "diariamente", "diario", "hábito diario"]):
            clean_title = re.sub(r"\b(todos los d[ií]as|cada d[ií]a|diariamente|diario|h[aá]bito diario)\b", "", current_text, flags=re.IGNORECASE).strip()
            clean_title = clean_title.capitalize() if clean_title else current_text
            return {
                "action": "quick_task",
                "destination": "focus",
                "message": f"He configurado '{clean_title}' como hábito general para todos los días.",
                "tasks": [
                    {
                        "title": clean_title,
                        "tag": "Diaria",
                        "scheduled_time": detected_time,
                        "scheduled_date": None,
                        "task_type": "daily",
                        "recurrence": "daily"
                    }
                ]
            }

        # 3. DETECCIÓN DE TIEMPO DISPONIBLE EN EL MOMENTO
        time_avail_match = re.search(r"(\d+)\s*(?:minutos|min|m\b)", lower)
        hour_avail_match = re.search(r"(\d+)\s*(?:horas|hora|h\b)", lower)
        is_half_hour = "media hora" in lower

        minutes_available = None
        if time_avail_match:
            minutes_available = int(time_avail_match.group(1))
        elif hour_avail_match:
            minutes_available = int(hour_avail_match.group(1)) * 60
        elif is_half_hour:
            minutes_available = 30

        # Solo activar desglose por tiempo si el usuario explícitamente habla de su tiempo disponible o sesión
        is_time_avail_prompt = minutes_available and (
            any(w in lower for w in ["tengo", "dispongo", "bloque", "sesion", "sesión", "tiempo"]) or
            re.match(r"^\d+\s*(?:minutos|min|horas?|h)\b", lower)
        )

        if is_time_avail_prompt:
            if minutes_available <= 25:
                tasks = [
                    {"title": f"Foco único de alta prioridad ({minutes_available - 5} min)", "tag": f"{minutes_available - 5} min", "task_type": "micro_step"},
                    {"title": "Cierre y pausa de descanso (5 min)", "tag": "5 min", "task_type": "micro_step"}
                ]
            elif minutes_available <= 50:
                p1 = int(minutes_available * 0.5)
                p2 = minutes_available - p1 - 5
                tasks = [
                    {"title": f"Avance principal enfocado ({p1} min)", "tag": f"{p1} min", "task_type": "micro_step"},
                    {"title": "Pausa breve de respiración o agua (5 min)", "tag": "5 min", "task_type": "micro_step"},
                    {"title": f"Revisión y cierre de pendientes ({p2} min)", "tag": f"{p2} min", "task_type": "micro_step"}
                ]
            else:
                tasks = [
                    {"title": "Bloque 1 de desarrollo o lectura (25 min)", "tag": "25 min", "task_type": "micro_step"},
                    {"title": "Pausa activa (5 min)", "tag": "5 min", "task_type": "micro_step"},
                    {"title": "Bloque 2 de práctica o síntesis (25 min)", "tag": "25 min", "task_type": "micro_step"}
                ]

            return {
                "action": "propose_tasks",
                "destination": "focus",
                "message": f"Perfecto. Con {minutes_available} minutos disponibles, he distribuido tu tiempo en bloques de baja fricción para que no sientas sobrecarga:",
                "is_goal": True,
                "goal_title": f"Sesión de {minutes_available} min",
                "tasks": tasks
            }

        # 4. CLASIFICACIÓN: DESTINO METAS (Objetivos de mediano/largo plazo, aspiraciones, proyectos, habilidades)
        is_explicit_goal = bool(re.search(r"^(?:meta|objetivo|reto|proyecto):\s*", lower) or 
                               re.search(r"^mi\s+(?:meta|objetivo|reto|proyecto)\s+(?:es\s+)?", lower))
        is_learn_goal = bool(re.search(r"\b(aprender\s+[\wáéíóúñ]+|estudiar\s+(?:un\s+nuevo\s+)?(?:idioma|curso|carrera|maestr[ií]a|diplomado)|terminar\s+(?:mi\s+)?tesis|escribir\s+(?:mi\s+)?tesis|leer\s+(?:\d+|varios)?\s*libros)\b", lower))
        is_finance_goal = bool(re.search(r"\b(ahorrar(?:\s+(?:dinero|plata|lucas|\$|\d+|para))?|invertir\s+en|comprar\s+(?:un\s+)?(?:auto|casa|departamento|depto)|pagar\s+(?:mis\s+)?deudas)\b", lower))
        is_health_goal = bool(re.search(r"\b(bajar\s+(?:de\s+)?peso|bajar\s+\d+\s*kilos|perder\s+peso|ponerme\s+en\s+forma|ganar\s+masa\s+muscular|entrenar\s+para\s+(?:una\s+)?marat[oó]n|correr\s+\d+k|ir\s+al\s+gym\s+este\s+a[ñn]o)\b", lower))
        is_project_goal = bool(re.search(r"\b(lanzar\s+(?:mi\s+)?(?:startup|app|aplicaci[oó]n|web|negocio|canal|podcast)|crear\s+(?:mi\s+)?(?:empresa|startup|negocio)|escribir\s+un\s+libro|cambiar\s+de\s+trabajo)\b", lower))
        is_timeframe_goal = bool(re.search(r"\b(este\s+a[ñn]o|en\s+este\s+a[ñn]o|para\s+este\s+a[ñn]o|a\s+fin\s+de\s+a[ñn]o|en\s+\d+\s+meses)\b", lower) and not re.search(r"\b(cita|dentista|m[eé]dico|doctor|reuni[oó]n|hora|hoy|ma[ñn]ana)\b", lower))

        if is_explicit_goal or is_learn_goal or is_finance_goal or is_health_goal or is_project_goal or is_timeframe_goal:
            # Limpiar el título de la meta
            clean_title = re.sub(r"^(?:meta|objetivo|reto|proyecto):\s*", "", current_text, flags=re.IGNORECASE)
            clean_title = re.sub(r"^mi\s+(?:meta|objetivo|reto|proyecto)\s+(?:es\s+)?", "", clean_title, flags=re.IGNORECASE).strip()
            clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else "Nueva Meta"

            # Determinar categoría y micro-pasos iniciales
            if is_finance_goal or any(w in lower for w in ["ahorr", "dinero", "plata", "invertir", "comprar auto", "comprar casa", "deuda", "lucas"]):
                category = "finanzas"
                steps = [
                    {"title": f"{clean_title}: Revisar gastos fijos y fijar monto mensual de ahorro", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Configurar apartado o cuenta separada para el fondo", "tag": "15 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Monitorear balance y ahorro al cierre del primer mes", "tag": "15 min", "task_type": "micro_step"}
                ]
            elif is_health_goal or any(w in lower for w in ["peso", "kilo", "gym", "marat", "correr", "muscular", "salud", "forma"]):
                category = "salud"
                steps = [
                    {"title": f"{clean_title}: Definir rutina de inicio suave de 15 minutos", "tag": "15 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Planificar compras o comidas saludables para la semana", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Registrar avances y sensaciones sin autoexigencia", "tag": "10 min", "task_type": "micro_step"}
                ]
            elif is_project_goal or any(w in lower for w in ["startup", "app", "empresa", "negocio", "trabajo", "proyecto", "canal", "podcast", "web"]):
                category = "trabajo"
                steps = [
                    {"title": f"{clean_title}: Escribir alcance mínimo del proyecto en 1 página", "tag": "25 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Configurar herramientas y lista inicial de requisitos", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Desarrollar o probar la primera funcionalidad básica", "tag": "30 min", "task_type": "micro_step"}
                ]
            elif is_learn_goal or any(w in lower for w in ["aprend", "estudi", "curso", "tesis", "libro", "leer", "idioma", "python", "program", "código", "codigo"]):
                category = "estudio"
                steps = [
                    {"title": f"{clean_title}: Seleccionar recurso inicial o temario de estudio", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Completar la primera sesión práctica o lectura corta", "tag": "25 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Anotar dudas y definir horario semanal de avance", "tag": "15 min", "task_type": "micro_step"}
                ]
            else:
                category = "personal"
                steps = [
                    {"title": f"{clean_title}: Definir el primer micro-paso de baja fricción", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Dedicar una primera sesión enfocada", "tag": "25 min", "task_type": "micro_step"},
                    {"title": f"{clean_title}: Evaluar avances y programar el siguiente bloque", "tag": "15 min", "task_type": "micro_step"}
                ]

            return {
                "action": "create_goal",
                "destination": "goals",
                "is_goal": True,
                "goal_title": clean_title,
                "category": category,
                "message": f"He creado tu meta '{clean_title}' en la sección de Metas con sus 3 primeros pasos para comenzar sin sobrecarga.",
                "tasks": steps
            }

        # 5. CLASIFICACIÓN: DESTINO AGENDA (Citas, compromisos con fecha u hora, fechas importantes, celebraciones)
        palabras_cita = ["cita", "médico", "medico", "dentista", "doctor", "doctora", "reunión", "reunion", "compromiso", "consulta", "entrevista", "turno"]
        palabras_celebra = ["cumplemes", "cumpleaños", "cumple", "aniversario", "festejo", "celebración", "celebracion"]
        dias_map = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
        meses_map = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
        
        detected_date = None
        detected_day_name = None

        # 5.A Recordatorios recurrentes mensuales (ej: "el 19 de cada mes", "cumplemes todos los 19", "fecha 19 de cada mes")
        is_monthly = bool(re.search(r"\b(de\s+cada\s+mes|todos\s+los\s+meses|cada\s+mes|mensual(?:mente)?)\b", lower))
        month_day_match = re.search(r"\b(?:el\s+|fecha\s+|los\s+|d[ií]a\s+)?(\d{1,2})\b", lower)
        if is_monthly and month_day_match and 1 <= int(month_day_match.group(1)) <= 31:
            day_num = int(month_day_match.group(1))
            # Enero conserva el día elegido incluso si el primer mes actual es más corto.
            anchor = date(now.year - 1, 1, day_num)
            detected_date = occurrence_on_or_after("monthly", anchor.isoformat(), now.date()).isoformat()
            if int(detected_date[-2:]) != day_num:
                # Guardar una fecha válida con el día original para los meses siguientes.
                next_month = date.fromisoformat(detected_date) + timedelta(days=1)
                detected_date = occurrence_on_or_after("monthly", anchor.isoformat(), next_month).isoformat()

            if any(w in lower for w in ["cumplemes", "cumple mes", "novia", "aniversario"]):
                clean_title = "Cumplemes con mi novia" if ("novia" in lower or "pareja" in lower) else "Cumplemes"
            else:
                clean_title = re.sub(r"^(?:mira,?\s*)?(?:guarda|anota|recuerda|recordatorio\s+de)?\s*", "", current_text, flags=re.IGNORECASE).strip()
                clean_title = clean_title.capitalize() if clean_title else f"Recordatorio día {day_num}"

            return {
                "action": "scheduled_task",
                "destination": "agenda",
                "message": f"¡Anotado! He guardado '{clean_title}' para el día {day_num} de cada mes como recordatorio mensual en tu Agenda (sin mezclarse con tu Foco diario).",
                "tasks": [
                    {
                        "title": clean_title,
                        "tag": f"Mensual (día {day_num})",
                        "scheduled_time": detected_time,
                        "scheduled_date": detected_date,
                        "task_type": "appointment",
                        "recurrence": "monthly",
                        "is_priority": 1
                    }
                ]
            }

        if "mañana" in lower or "manana" in lower:
            tomorrow = now + timedelta(days=1)
            detected_date = tomorrow.strftime("%Y-%m-%d")
            detected_day_name = "Mañana"
        elif "hoy" in lower:
            detected_date = now.strftime("%Y-%m-%d")
            detected_day_name = "Hoy"
        else:
            # 5.A Detección por día de la semana (ej: "martes 8", "un martes", "el próximo viernes")
            weekday_match = re.search(r"\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)(?:\s+(\d{1,2}))?\b", lower)
            if weekday_match:
                dia_str = weekday_match.group(1).replace("é", "e").replace("á", "a")
                target_weekday = dias_map[dia_str]
                day_num = int(weekday_match.group(2)) if weekday_match.group(2) else None
                days_ahead = (target_weekday - now.weekday() + 7) % 7
                if days_ahead == 0 and (detected_time is None or target_weekday != now.weekday()):
                    days_ahead = 7
                target_dt = now + timedelta(days=days_ahead)
                if day_num:
                    try:
                        m_target = now.month if day_num >= now.day else (now.month % 12 + 1)
                        y_target = now.year if day_num >= now.day or now.month < 12 else now.year + 1
                        target_dt = datetime(y_target, m_target, day_num)
                    except Exception:
                        pass
                detected_date = target_dt.strftime("%Y-%m-%d")
                detected_day_name = f"{weekday_match.group(1).capitalize()} {target_dt.day}"
            else:
                # 5.B Detección por día del mes (ej: "el 19", "el 19 de noviembre")
                dm_match = re.search(r"\bel\s+(\d{1,2})(?:\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+))?\b", lower)
                if dm_match:
                    day_num = int(dm_match.group(1))
                    month_name = dm_match.group(2).lower() if dm_match.group(2) else None
                    month_num = meses_map.get(month_name, now.month)
                    year = now.year
                    if not month_name and day_num < now.day:
                        month_num = now.month % 12 + 1
                        if month_num == 1:
                            year += 1
                    try:
                        dt = datetime(year, month_num, day_num)
                        detected_date = dt.strftime("%Y-%m-%d")
                        dia_sem = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dt.weekday()]
                        detected_day_name = f"{dia_sem} {day_num}"
                    except Exception:
                        pass

        is_cita = any(w in lower for w in palabras_cita)
        is_celebra = any(w in lower for w in palabras_celebra)

        if is_celebra and (detected_date or detected_day_name):
            clean_title = current_text.strip()
            clean_title = clean_title[0].upper() + clean_title[1:]
            return {
                "action": "scheduled_task",
                "destination": "agenda",
                "message": f"¡Anotado con cariño! He agendado '{clean_title}' para {detected_day_name or 'esa fecha'} en tu Agenda.",
                "tasks": [
                    {
                        "title": clean_title,
                        "tag": f"Especial {detected_day_name or ''}".strip(),
                        "scheduled_time": detected_time,
                        "scheduled_date": detected_date or now.strftime("%Y-%m-%d"),
                        "task_type": "appointment",
                        "is_priority": 1
                    }
                ]
            }

        if is_cita or (detected_date and detected_date != now.strftime("%Y-%m-%d")) or (detected_time and not minutes_available):
            if not detected_time and not is_celebra:
                return {
                    "action": "question",
                    "destination": "agenda",
                    "message": f"Entendido, agendemos {current_text}. ¿A qué hora está programada?",
                    "options": ["08:00", "09:30", "11:00", "15:00", "17:30", "Sin hora fija"],
                    "allow_custom": True,
                    "custom_placeholder": "Ej: 14:15 o a las 4 de la tarde...",
                    "target_date": detected_date or now.strftime("%Y-%m-%d")
                }
            else:
                tag_label = f"{detected_day_name or 'Agenda'} {detected_time or ''}".strip()
                clean_title = current_text.strip()
                clean_title = clean_title[0].upper() + clean_title[1:]
                return {
                    "action": "scheduled_task",
                    "destination": "agenda",
                    "message": f"Compromiso agendado con éxito para {detected_day_name or 'Hoy'}{(' a las ' + detected_time) if detected_time else ''}.",
                    "tasks": [
                        {
                            "title": clean_title,
                            "tag": tag_label,
                            "scheduled_time": detected_time,
                            "scheduled_date": detected_date or now.strftime("%Y-%m-%d"),
                            "task_type": "appointment",
                            "is_priority": 1
                        }
                    ]
                }

        # 6. CLASIFICACIÓN: DESTINO FOCO (Tareas cotidianas, inmediatas o pendientes de hoy)
        clean_title = current_text.strip()
        clean_title = clean_title[0].upper() + clean_title[1:] if clean_title else "Tarea"
        return {
            "action": "quick_task",
            "destination": "focus",
            "message": f"He anotado '{clean_title}' directamente en tu Foco de Hoy.",
            "tasks": [
                {"title": clean_title, "tag": "Hoy", "scheduled_time": None, "scheduled_date": None, "task_type": "quick", "recurrence": "none"}
            ]
        }

    def triage_focus(self, pending_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not pending_tasks:
            return {
                "message": "No tienes tareas pendientes ahora mismo. Tienes el foco totalmente despejado.",
                "keep_ids": [],
                "postpone_ids": []
            }

        if len(pending_tasks) <= 2:
            return {
                "message": "Tu lista actual ya es muy concisa (2 o menos tareas). Puedes completarlas a tu propio ritmo con tranquilidad.",
                "keep_ids": [t["id"] for t in pending_tasks],
                "postpone_ids": []
            }

        if self.client and self.connection_status == "ok":
            try:
                task_summaries = [f"ID {t['id']}: {t['title']} ({t.get('tag', 'Hoy')})" for t in pending_tasks]
                prompt = f"""
Eres seeU. El usuario tiene sobrecarga mental y ansiedad frente a esta lista de tareas:
{chr(10).join(task_summaries)}

Selecciona únicamente 2 tareas esenciales para completar hoy y devolverle la sensación de control.
Responde ÚNICAMENTE un JSON válido:
{{
  "message": "Explicación breve y reconfortante de por qué estas 2 tareas te devolverán el control hoy.",
  "keep_ids": [id1, id2],
  "postpone_ids": [id3, id4]
}}
"""
                text, _ = self._generate(self.client, prompt, config={"response_mime_type": "application/json"})
                return json.loads(text)
            except Exception:
                pass

        # Fallback local
        keep = [t["id"] for t in pending_tasks[:2]]
        postpone = [t["id"] for t in pending_tasks[2:]]
        return {
            "message": "Para aliviar la sobrecarga, nos enfocaremos únicamente en las dos primeras tareas. El resto queda en pausa para después.",
            "keep_ids": keep,
            "postpone_ids": postpone
        }

    def get_smart_reminders(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analiza las tareas y detecta citas, fechas importantes, cumplemeses,
        aniversarios y compromisos próximos para generar recordatorios inteligentes.
        """
        now = datetime.now()
        today = now.date()
        reminders = []

        keywords_special = ["cumplemes", "cumpleaños", "cumple", "aniversario", "dentista", "doctor", "doctora", "médico", "medico", "cita", "examen", "prueba", "pago", "tesis"]

        for task in tasks:
            if task.get("status") in ("completada", "no_lograda"):
                continue

            title = task.get("title", "").strip()
            if not title:
                continue

            title_lower = title.lower()
            sched_date = task.get("scheduled_date")
            sched_time = task.get("scheduled_time")
            is_prio = bool(task.get("is_priority"))

            target_date = None
            if sched_date:
                recurrence = task.get("recurrence")
                if recurrence in RECURRING:
                    target_date = occurrence_on_or_after(recurrence, sched_date, today)
                else:
                    try:
                        target_date = datetime.strptime(sched_date, "%Y-%m-%d").date()
                    except ValueError:
                        pass

            # Si no tiene fecha asignada pero el texto dice "el 19", etc.
            if not target_date:
                m_day = re.search(r"\bel\s+(\d{1,2})\b", title_lower)
                if m_day:
                    day_val = int(m_day.group(1))
                    try:
                        m_val = now.month if day_val >= now.day else (now.month % 12 + 1)
                        y_val = now.year if day_val >= now.day or now.month < 12 else now.year + 1
                        target_date = datetime(y_val, m_val, day_val).date()
                    except Exception:
                        pass

            is_special = any(k in title_lower for k in keywords_special) or task.get("task_type") == "appointment"

            if not target_date and not is_special and not is_prio:
                continue

            days_left = (target_date - today).days if target_date else 0

            # Solo recordar si es hoy, o en los próximos 14 días
            if target_date and (days_left < 0 or days_left > 14):
                continue

            if target_date:
                if days_left == 0:
                    date_prefix = "Hoy"
                elif days_left == 1:
                    date_prefix = "Mañana"
                else:
                    dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                    date_prefix = f"{dias_es[target_date.weekday()]} {target_date.day}"
            else:
                date_prefix = "Compromiso importante"

            time_suffix = f" a las {sched_time}" if sched_time else ""

            if any(k in title_lower for k in ["cumplemes", "cumpleaños", "aniversario"]):
                msg = f"{date_prefix}: {title}. ¡Acuérdate de celebrarlo! ❤️"
                icon = "heart"
            elif any(k in title_lower for k in ["dentista", "doctor", "médico", "medico", "cita"]):
                msg = f"{date_prefix}{time_suffix}: {title}. ¡Acuérdate de asistir! 🦷"
                icon = "calendar"
            elif any(k in title_lower for k in ["examen", "prueba", "tesis"]):
                msg = f"{date_prefix}{time_suffix}: {title}. ¡Mucho éxito en tu preparación! 📚"
                icon = "star"
            elif "pago" in title_lower:
                msg = f"{date_prefix}: Recordatorio de pago: {title}. 💳"
                icon = "bell"
            else:
                msg = f"{date_prefix}{time_suffix}: {title}. ¡Acuérdate!"
                icon = "bell"

            reminders.append({
                "id": task.get("id"),
                "title": title,
                "message": msg,
                "date_label": date_prefix,
                "days_left": days_left,
                "time": sched_time,
                "icon": icon
            })

        reminders.sort(key=lambda r: (r["days_left"], r.get("time") or "99:99"))
        return reminders
