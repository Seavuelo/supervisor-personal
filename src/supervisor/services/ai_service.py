import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from supervisor.repositories import settings_repository

load_dotenv()

# Modelos oficiales soportados por Google AI Studio
CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]

class AIService:
    def __init__(self):
        db_key = settings_repository.get_setting("gemini_api_key")
        self.api_key = db_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
        self.active_model = "gemini-3.5-flash"
        self.history: List[Dict[str, str]] = []
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[seeU] Inicialización de cliente Gemini: {e}")
                self.client = None
        else:
            self.client = None

    def set_api_key(self, key: str) -> Dict[str, Any]:
        cleaned_key = key.strip()
        self.api_key = cleaned_key
        settings_repository.set_setting("gemini_api_key", cleaned_key)
        self._init_client()
        return self.test_connection()

    def get_api_key_masked(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "••••••••"
        return self.api_key[:4] + "••••••••" + self.api_key[-4:]

    def test_connection(self) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "offline",
                "message": "Sin clave configurada. Operando en modo local autónomo."
            }

        if not self.client:
            self._init_client()

        if not self.client:
            return {
                "status": "error",
                "message": "Librería google-genai no inicializada."
            }

        # Probar modelos candidatos para evitar 404 de modelos discontinuados o 503 de alta demanda
        last_error = ""
        for model_name in CANDIDATE_MODELS:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents="Responde solo la palabra OK",
                )
                if response and response.text:
                    self.active_model = model_name
                    return {
                        "status": "ok",
                        "model": model_name,
                        "message": f"Conectado a Google Gemini ({model_name}) con éxito."
                    }
            except Exception as e:
                last_error = str(e)
                print(f"[seeU] Modelo {model_name} no disponible: {e}")
                continue

        # Diagnóstico claro si todos fallan
        if "API_KEY_INVALID" in last_error or "400" in last_error or "expired" in last_error.lower():
            return {
                "status": "error",
                "message": "Clave de API inválida o expirada. Verifica en Google AI Studio."
            }
        elif "404" in last_error:
            return {
                "status": "error",
                "message": "El endpoint del modelo no está disponible. Probando alternativas..."
            }
        return {
            "status": "error",
            "message": f"Error de conexión: {last_error[:70]}"
        }

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

        if self.client:
            try:
                result = self._call_gemini_conversational()
                assistant_msg = result.get("message") or result.get("question") or ""
                if assistant_msg:
                    self.history.append({"role": "assistant", "text": assistant_msg})
                return result
            except Exception as e:
                print(f"[seeU] Error llamando a Gemini ({e}), probando fallback...")

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
Eres seeU, un supervisor personal empático, inteligente y sobrio. Tu misión es ayudar a una persona que siente sobrecarga cognitiva y agobio mental a definir, negociar y anotar sus actividades de forma tranquila y sin parálisis.

Fecha y hora de referencia: {fecha_actual}, {now.strftime("%H:%M")}.

HISTORIAL DE LA CONVERSACIÓN RECIENTE:
{history_str}

REGLAS DE COMPORTAMIENTO:
1. CERO emojis. Tono sereno, directo y reconfortante. Sin marketing ni frases vacías.
2. Si el usuario pide un hábito o tarea que se repite (ej: "hacer ejercicio todos los días", "tomar agua todos los días"):
   - Asignar recurrence: "daily", task_type: "daily", tag: "Diaria", scheduled_date: null.
3. Si el usuario rechaza algo (ej: "no quiero estudiar", "quiero otras actividades", "otra cosa"):
   - Cambia de rumbo con flexibilidad. Pregúntale qué tipo de actividades prefiere hoy (prácticas, organizar pendientes, descanso activo) y cuánto tiempo tiene.
4. Si el usuario da un plazo o tiempo disponible (ej: "tengo 40 minutos", "1 hora"):
   - Desglosa un plan realista y adaptable a ese tiempo exacto con pausas breves.
5. Si el usuario propone algo vago (ej: "quiero estudiar"):
   - Pregúntale de forma natural qué materia o proyecto tiene en mente, o qué le genera más resistencia para empezar.
6. Si es una cita o compromiso sin hora:
   - Pregúntale a qué hora está programada.
7. Si la propuesta ya está clara o el usuario la aprobó:
   - Devuelve la lista de tareas concretas listas para guardar en su Foco o Agenda.

RESPONDE ÚNICAMENTE UN JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
  "action": "question" | "propose_tasks" | "scheduled_task" | "quick_task",
  "message": "Tu respuesta conversacional articulada al usuario",
  "question": "Pregunta si aplica",
  "options": ["Opcion 1", "Opcion 2", "Opcion 3"],
  "allow_custom": true,
  "custom_placeholder": "Placeholder para responder",
  "is_goal": true | false,
  "goal_title": "Título si es meta",
  "tasks": [
    {{"title": "Paso 1 muy concreto", "tag": "Hoy", "scheduled_time": null, "scheduled_date": null, "task_type": "quick" | "daily" | "micro_step" | "appointment", "recurrence": "none" | "daily"}}
  ]
}}
"""
        # Ejecutar con modelo activo o probar candidatos
        last_err = None
        models_to_try = [self.active_model] + [m for m in CANDIDATE_MODELS if m != self.active_model]

        for m_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                )
                self.active_model = m_name
                raw_text = response.text.strip()
                clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text)
                clean_json = re.sub(r"\s*```$", "", clean_json)
                return json.loads(clean_json)
            except Exception as e:
                last_err = e
                print(f"[seeU] Reintento con siguiente modelo tras fallo en {m_name}: {e}")
                continue

        raise last_err or Exception("No se pudo obtener respuesta de ningún modelo Gemini.")

    def _local_conversational_agent(self, current_text: str) -> Dict[str, Any]:
        """
        Motor Local Autónomo con máquina de estados y memoria de contexto.
        Simula una conversación real cuando el usuario aún no ha configurado Gemini o está sin conexión.
        """
        lower = current_text.lower().strip()
        now = datetime.now()

        prev_user_msgs = [m["text"] for m in self.history[:-1] if m["role"] == "user"]
        prev_assistant_msgs = [m["text"] for m in self.history if m["role"] == "assistant"]
        last_assistant_msg = prev_assistant_msgs[-1].lower() if prev_assistant_msgs else ""
        last_user_msg = prev_user_msgs[-1].lower() if prev_user_msgs else ""

        time_match = re.search(r"(\d{1,2}:\d{2})", lower)
        hour_match = re.search(r"a las (\d{1,2})", lower)
        detected_time = time_match.group(1) if time_match else (f"{int(hour_match.group(1)):02d}:00" if hour_match else None)

        # 0. RESOLUCIÓN DE TAREAS RECURRENTES O HÁBITOS DIARIOS
        # Ej: "hacer ejercicio todos los días", "tomar agua todos los días", "leer 20 min diario"
        if any(w in lower for w in ["todos los días", "todos los dias", "cada día", "cada dia", "diariamente", "diario", "hábito diario"]):
            clean_title = re.sub(r"\b(todos los d[ií]as|cada d[ií]a|diariamente|diario|h[aá]bito diario)\b", "", current_text, flags=re.IGNORECASE).strip()
            clean_title = clean_title.capitalize() if clean_title else current_text
            return {
                "action": "quick_task",
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

        # 1. RESOLUCIÓN DE HORA TRAS PREGUNTA DE CITA PREVIA
        if detected_time and ("a qué hora" in last_assistant_msg or "agendemos" in last_assistant_msg):
            palabras_cita = ["cita", "médico", "medico", "dentista", "doctor", "doctora", "reunión", "reunion"]
            appt_title = next((m for m in reversed(prev_user_msgs) if any(w in m.lower() for w in palabras_cita)), "Cita médica")
            return {
                "action": "scheduled_task",
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

        # 2. DETECCIÓN DE TIEMPO DISPONIBLE
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

        if minutes_available:
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
                "message": f"Perfecto. Con {minutes_available} minutos disponibles, he distribuido tu tiempo en bloques de baja fricción para que no sientas sobrecarga:",
                "is_goal": True,
                "goal_title": f"Sesión de {minutes_available} min",
                "tasks": tasks
            }

        # 3. DETECCIÓN DE CITA MÉDICA O REUNIÓN
        palabras_cita = ["cita", "médico", "medico", "dentista", "doctor", "doctora", "reunión", "reunion"]
        dias_map = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
        detected_date = None
        detected_day_name = None

        if "mañana" in lower or "manana" in lower:
            tomorrow = now + timedelta(days=1)
            detected_date = tomorrow.strftime("%Y-%m-%d")
            detected_day_name = "Mañana"
        elif "hoy" in lower:
            detected_date = now.strftime("%Y-%m-%d")
            detected_day_name = "Hoy"
        else:
            for dia, weekday_num in dias_map.items():
                if dia in lower:
                    days_ahead = (weekday_num - now.weekday() + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    detected_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                    detected_day_name = dia.capitalize()
                    break

        if any(w in lower for w in palabras_cita) or (detected_date and detected_date != now.strftime("%Y-%m-%d")):
            if not detected_time:
                return {
                    "action": "question",
                    "message": f"Entendido, agendemos {current_text}. ¿A qué hora está programada?",
                    "options": ["09:30", "11:00", "15:00", "17:30", "Sin hora fija"],
                    "allow_custom": True,
                    "custom_placeholder": "Ej: 14:15 o a las 4 de la tarde...",
                    "target_date": detected_date or now.strftime("%Y-%m-%d")
                }
            else:
                tag_label = f"{detected_day_name or 'Agenda'} {detected_time}"
                return {
                    "action": "scheduled_task",
                    "message": f"Compromiso agendado con éxito para {detected_day_name or 'Hoy'} a las {detected_time}.",
                    "tasks": [
                        {
                            "title": current_text,
                            "tag": tag_label,
                            "scheduled_time": detected_time,
                            "scheduled_date": detected_date or now.strftime("%Y-%m-%d"),
                            "task_type": "appointment"
                        }
                    ]
                }

        # 4. CASO DE ESTUDIO O APRENDIZAJE
        palabras_estudio = ["estudiar", "estudio", "aprender", "repasar", "leer", "tesis", "curso"]
        if any(w in lower for w in palabras_estudio):
            materias = ["python", "redes", "bases de datos", "cálculo", "matemáticas", "tesis", "algoritmos", "arquitectura"]
            materia_encontrada = next((m.capitalize() for m in materias if m in lower), None)

            if not materia_encontrada and len(lower.split()) <= 4:
                return {
                    "action": "question",
                    "message": "¿Qué materia o tema específico quieres abordar hoy? Si tienes dudas, dime qué es lo que más te cuesta empezar.",
                    "options": [
                        "Python / Algoritmos",
                        "Tesis / Marco Teórico",
                        "Redes y Sistemas",
                        "Lectura de apuntes"
                    ],
                    "allow_custom": True,
                    "custom_placeholder": "Escribe la materia o describe lo que necesitas hacer..."
                }
            else:
                subject = materia_encontrada or current_text
                return {
                    "action": "propose_tasks",
                    "message": f"Para avanzar en {subject} sin que resulte pesado, te sugiero esta estructura de pasos cortos:",
                    "is_goal": True,
                    "goal_title": f"Estudio: {subject}",
                    "tasks": [
                        {"title": f"{subject}: Revisar conceptos esenciales o apuntes (20 min)", "tag": "20 min", "task_type": "micro_step"},
                        {"title": f"{subject}: Resolver 1 ejercicio o escribir 1 sección (30 min)", "tag": "30 min", "task_type": "micro_step"},
                        {"title": f"{subject}: Anotar 3 aprendizajes o pendientes (15 min)", "tag": "15 min", "task_type": "micro_step"}
                    ]
                }

        # 5. SI MENCIONA UNA MATERIA DIRECTA
        if len(lower.split()) <= 3 and any(w in lower for w in ["python", "redes", "datos", "tesis", "código", "codigo", "sql", "java"]):
            subject = current_text.capitalize()
            return {
                "action": "propose_tasks",
                "message": f"Excelente elección. Aquí tienes un desglose progresivo para {subject}:",
                "is_goal": True,
                "goal_title": f"Proyecto: {subject}",
                "tasks": [
                    {"title": f"{subject}: Configurar entorno o repasar fundamentos (20 min)", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Implementar una prueba práctica o código funcional (30 min)", "tag": "30 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Documentar o guardar avances (15 min)", "tag": "15 min", "task_type": "micro_step"}
                ]
            }

        # 6. Tarea simple directa
        return {
            "action": "quick_task",
            "message": f"He anotado '{current_text}' directamente en tu Foco de Hoy.",
            "tasks": [
                {"title": current_text, "tag": "Hoy", "scheduled_time": None, "scheduled_date": None, "task_type": "quick"}
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

        if self.client:
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
                resp = self.client.models.generate_content(
                    model=self.active_model,
                    contents=prompt
                )
                clean_json = re.sub(r"^```(?:json)?\s*", "", resp.text.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                return json.loads(clean_json)
            except Exception as e:
                print(f"[seeU] Fallback local en triage_focus: {e}")

        # Fallback local
        keep = [t["id"] for t in pending_tasks[:2]]
        postpone = [t["id"] for t in pending_tasks[2:]]
        return {
            "message": "Para aliviar la sobrecarga, nos enfocaremos únicamente en las dos primeras tareas. El resto queda en pausa para después.",
            "keep_ids": keep,
            "postpone_ids": postpone
        }
