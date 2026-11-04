import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from supervisor.repositories import settings_repository

load_dotenv()

class AIService:
    def __init__(self):
        db_key = settings_repository.get_setting("gemini_api_key")
        self.api_key = db_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
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
                "message": "Sin clave configurada. Operando en modo local offline."
            }

        if not self.client:
            self._init_client()

        if not self.client:
            return {
                "status": "error",
                "message": "Librería google-genai no inicializada."
            }

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Di 'OK' para verificar conexion.",
            )
            if response and response.text:
                return {
                    "status": "ok",
                    "message": "Conectado a Gemini 2.5 Flash con éxito."
                }
        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg or "expired" in err_msg.lower():
                return {
                    "status": "error",
                    "message": "Clave de API inválida o expirada."
                }
            return {
                "status": "error",
                "message": f"Error de conexión: {err_msg[:60]}"
            }

        return {"status": "error", "message": "No se recibió respuesta válida."}

    def process_input(self, user_text: str) -> Dict[str, Any]:
        text = user_text.strip()
        if not text:
            return {"action": "none"}

        if self.client:
            try:
                return self._call_gemini(text)
            except Exception as e:
                print(f"[seeU] Fallback a motor local tras error de API: {e}")

        return self._local_rule_engine(text)

    def _call_gemini(self, text: str) -> Dict[str, Any]:
        now = datetime.now()
        fecha_actual = now.strftime("%Y-%m-%d (%A)")

        prompt = f"""
Eres seeU, un supervisor y compañero personal sobrio, calmado y enfocado en eliminar la sobrecarga cognitiva y la ansiedad.
Fecha y hora de referencia: {fecha_actual}, {now.strftime("%H:%M")}.
Intención o frase del usuario: "{text}".

Reglas estrictas:
- Sin tono publicitario, sin introducciones vacías, CERO emojis.
- Si el usuario menciona una cita, trámite, reunión o evento con fecha/hora (ej: "el martes al mediodía médico"):
  - Si falta la hora:
    - action: "question"
    - question: "¿A qué hora lo programamos?"
    - options: ["10:00", "12:00", "16:30", "Sin hora fija"]
    - tasks: [{{"title": "texto limpio de la cita", "scheduled_date": "YYYY-MM-DD", "task_type": "appointment"}}]
  - Si la hora está clara o inferida:
    - action: "scheduled_task"
    - tasks: [{{"title": "Cita o evento limpio", "tag": "Hora o Fecha", "scheduled_time": "HH:MM", "scheduled_date": "YYYY-MM-DD", "task_type": "appointment"}}]
- Si es un objetivo grande de estudio, hábito o proyecto (ej: "estudiar python", "avanzar tesis", "redactar informe de título"):
  - action: "micro_steps"
  - question: "Desglose en 3 micro-pasos de baja resistencia mental:"
  - is_goal: true
  - goal_title: "Título de la meta"
  - tasks: [
      {{"title": "Paso 1 muy concreto (20 min)", "tag": "20 min", "task_type": "micro_step"}},
      {{"title": "Paso 2 enfocado (30 min)", "tag": "30 min", "task_type": "micro_step"}},
      {{"title": "Paso 3 de consolidación (15 min)", "tag": "15 min", "task_type": "micro_step"}}
    ]
- Si es una tarea directa para hoy (ej: "comprar leche", "mandar correo a profesor"):
  - action: "quick_task"
  - tasks: [{{"title": "texto limpio", "tag": "Hoy", "task_type": "quick"}}]

Responde ÚNICAMENTE un JSON válido sin bloques markdown adicionales:
{{
  "action": "question" | "micro_steps" | "quick_task" | "scheduled_task",
  "question": "texto de la pregunta si corresponde",
  "options": ["opcion 1", "opcion 2"],
  "is_goal": false,
  "goal_title": "",
  "tasks": [
    {{"title": "texto", "tag": "Hoy", "scheduled_time": null, "scheduled_date": null, "task_type": "quick"}}
  ]
}}
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw_text = response.text.strip()
        clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text)
        clean_json = re.sub(r"\s*```$", "", clean_json)
        return json.loads(clean_json)

    def triage_focus(self, pending_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Función anti-ansiedad ('Despejar Foco'):
        Ayuda a priorizar de forma calmada cuando la persona se siente colapsada.
        """
        if not pending_tasks:
            return {
                "message": "No tienes tareas pendientes ahora mismo. Tienes el foco totalmente libre.",
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
Eres seeU. El usuario tiene sobrecarga mental y ansiedad frente a esta lista de tareas pendientes:
{chr(10).join(task_summaries)}

Selecciona únicamente 2 tareas esenciales para completar hoy y recuperar la sensación de avance y calma.
El resto serán marcadas para pausar o reprogramar sin remordimientos.

Responde ÚNICAMENTE un JSON válido:
{{
  "message": "Explicación breve y reconfortante de por qué estas 2 tareas te devolverán el control hoy.",
  "keep_ids": [id1, id2],
  "postpone_ids": [id3, id4]
}}
"""
                resp = self.client.models.generate_content(
                    model="gemini-2.5-flash",
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

    def _local_rule_engine(self, text: str) -> Dict[str, Any]:
        lower = text.lower()
        now = datetime.now()

        # Detección de día de la semana
        dias_map = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
        }

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
                    target_date = now + timedelta(days=days_ahead)
                    detected_date = target_date.strftime("%Y-%m-%d")
                    detected_day_name = dia.capitalize()
                    break

        # Detección de hora
        time_match = re.search(r"(\d{1,2}:\d{2})|a las (\d{1,2})", lower)
        detected_time = None
        if time_match:
            detected_time = time_match.group(1) or f"{int(time_match.group(2)):02d}:00"

        # Es cita o evento
        is_appointment = any(w in lower for w in [
            "cita", "médico", "medico", "dentista", "doctor", "reunión", "reunion", 
            "entrega", "evaluación", "evaluacion", "certamen", "examen", "clase"
        ])

        if is_appointment or (detected_date and detected_date != now.strftime("%Y-%m-%d")):
            if not detected_time:
                date_label = detected_day_name or "la fecha indicada"
                return {
                    "action": "question",
                    "title": text,
                    "question": f"¿A qué hora agendamos '{text}' para {date_label}?",
                    "options": ["10:00", "12:00", "15:30", "Sin hora fija"],
                    "scheduled_date": detected_date or now.strftime("%Y-%m-%d")
                }
            else:
                tag_label = f"{detected_day_name or 'Agenda'} {detected_time}"
                return {
                    "action": "scheduled_task",
                    "tasks": [
                        {
                            "title": text,
                            "tag": tag_label,
                            "scheduled_time": detected_time,
                            "scheduled_date": detected_date or now.strftime("%Y-%m-%d"),
                            "task_type": "appointment"
                        }
                    ]
                }

        # Es objetivo de estudio o proyecto
        if any(w in lower for w in ["estudiar", "aprender", "curso", "tesis", "proyecto", "python", "leer", "práctica", "practica"]):
            subject = "el tema"
            if "python" in lower:
                subject = "Python"
            elif "tesis" in lower:
                subject = "Tesis"

            return {
                "action": "micro_steps",
                "question": f"Desglose para avanzar en {subject} con baja fricción:",
                "is_goal": True,
                "goal_title": text,
                "tasks": [
                    {"title": f"{subject}: Revisión inicial o lectura corta (20 min)", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Práctica enfocada de 1 módulo o función (30 min)", "tag": "30 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Síntesis de lo aprendido (15 min)", "tag": "15 min", "task_type": "micro_step"}
                ]
            }

        # Tarea directa
        return {
            "action": "quick_task",
            "tasks": [
                {"title": text, "tag": "Hoy", "scheduled_time": None, "scheduled_date": None, "task_type": "quick"}
            ]
        }
