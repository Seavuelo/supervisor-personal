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
        """
        Procesa la intención del usuario.
        Si la intención es ambigua, vaga o carece de datos esenciales (hora, materia, plazo),
        la IA DEBE intervenir activamente preguntando para guiar al usuario y aliviar su sobrecarga.
        """
        text = user_text.strip()
        if not text:
            return {"action": "none"}

        if self.client:
            try:
                return self._call_gemini(text)
            except Exception as e:
                print(f"[seeU] Fallback a motor local tras error de API: {e}")

        return self._local_rule_engine(text)

    def process_followup(self, original_text: str, user_answer: str, context_type: str, extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Procesa la segunda fase de la conversación: cuando el usuario responde a la pregunta de la IA.
        """
        ans = user_answer.strip()
        extra = extra_data or {}

        # 1. Contexto de estudio: el usuario especificó la materia o tema
        if context_type == "study_topic":
            subject = ans if ans.lower() not in ["otro tema...", "sin definir"] else original_text
            # Generar desglose en micro-pasos
            return {
                "action": "micro_steps",
                "question": f"Desglose para estudiar {subject} con baja fricción:",
                "is_goal": True,
                "goal_title": f"Estudio: {subject}",
                "tasks": [
                    {"title": f"{subject}: Revisión inicial o lectura de conceptos (20 min)", "tag": "20 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Ejercicio o práctica de 1 caso concreto (30 min)", "tag": "30 min", "task_type": "micro_step"},
                    {"title": f"{subject}: Apuntes o síntesis de lo aprendido (15 min)", "tag": "15 min", "task_type": "micro_step"}
                ]
            }

        # 2. Contexto de cita médica / reunión: el usuario especificó la hora
        if context_type == "appointment_time":
            time_val = None if ans.lower() in ["sin hora fija", "sin hora"] else ans
            date_val = extra.get("target_date")
            tag_label = f"{time_val}" if time_val else "Cita"
            return {
                "action": "scheduled_task",
                "tasks": [
                    {
                        "title": original_text,
                        "tag": tag_label,
                        "scheduled_time": time_val,
                        "scheduled_date": date_val,
                        "task_type": "appointment"
                    }
                ]
            }

        # 3. Contexto de plazo / deadline
        if context_type == "deadline":
            tag_label = ans
            return {
                "action": "quick_task",
                "tasks": [
                    {
                        "title": f"{original_text} ({ans})",
                        "tag": tag_label,
                        "scheduled_time": None,
                        "scheduled_date": None,
                        "task_type": "quick"
                    }
                ]
            }

        # Por defecto
        return {
            "action": "quick_task",
            "tasks": [{"title": f"{original_text} - {ans}", "tag": "Hoy", "task_type": "quick"}]
        }

    def _call_gemini(self, text: str) -> Dict[str, Any]:
        now = datetime.now()
        fecha_actual = now.strftime("%Y-%m-%d (%A)")

        prompt = f"""
Eres seeU, un supervisor y compañero personal proactivo, enfocado en quitarle al usuario el agobio de pensar y estructurar sus notas.
Fecha y hora de referencia: {fecha_actual}, {now.strftime("%H:%M")}.
Entrada rápida del usuario: "{text}".

Directrices críticas:
1. Cero tono publicitario, CERO emojis.
2. Si el texto es VAGO o le faltan detalles esenciales, TU DEBER ES INTERVENIR Y PREGUNTAR:
   - Si dice "quiero estudiar", "estudiar", "tengo que estudiar", "leer" sin decir qué:
     action: "question"
     context_type: "study_topic"
     question: "¿Qué materia o tema específico quieres estudiar?"
     options: ["Programación / Código", "Tesis / Grado", "Lectura técnica", "Matemáticas"]
     allow_custom: true
     custom_placeholder: "O escribe la materia o tema..."
   - Si menciona una cita, médico, dentista, reunión o evento pero NO especifica la hora exacta:
     action: "question"
     context_type: "appointment_time"
     question: "¿A qué hora tienes programada la cita?"
     options: ["09:00", "11:30", "15:00", "17:00", "Sin hora fija"]
     allow_custom: true
     custom_placeholder: "O escribe la hora exacta (ej: 14:15)..."
     target_date: fecha inferida (si dijo 'mañana', calcular la fecha ISO de mañana)
   - Si menciona una entrega, informe, proyecto o tarea grande sin plazo:
     action: "question"
     context_type: "deadline"
     question: "¿Para cuándo necesitas tenerlo listo?"
     options: ["Para hoy", "Para mañana", "Esta semana"]
     allow_custom: true
     custom_placeholder: "O escribe la fecha o plazo..."
3. Si el texto YA TIENE todos los detalles necesarios (ej: "médico mañana a las 11:30" o "comprar leche en el súper"):
   - Si es cita con hora y/o fecha:
     action: "scheduled_task"
     tasks: [{{"title": "texto limpio", "tag": "Hora o Fecha", "scheduled_time": "HH:MM", "scheduled_date": "YYYY-MM-DD", "task_type": "appointment"}}]
   - Si es tarea directa para hoy:
     action: "quick_task"
     tasks: [{{"title": "texto limpio", "tag": "Hoy", "scheduled_time": null, "scheduled_date": null, "task_type": "quick"}}]

Responde ÚNICAMENTE un JSON válido:
{{
  "action": "question" | "micro_steps" | "quick_task" | "scheduled_task",
  "context_type": "study_topic" | "appointment_time" | "deadline" | "general",
  "question": "texto de la pregunta si corresponde",
  "options": ["opcion 1", "opcion 2"],
  "allow_custom": true,
  "custom_placeholder": "texto sugerido en el campo de texto libre",
  "target_date": "YYYY-MM-DD o null",
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
        lower = text.lower().strip()
        now = datetime.now()

        # Detección de fechas relativas
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

        # Detección de hora explícita
        time_match = re.search(r"(\d{1,2}:\d{2})", lower)
        detected_time = None
        if time_match:
            detected_time = time_match.group(1)
        else:
            hour_match = re.search(r"a las (\d{1,2})", lower)
            if hour_match:
                detected_time = f"{int(hour_match.group(1)):02d}:00"

        # 1. CASO ESTUDIO: Detectar si es vago o específico
        palabras_estudio = ["estudiar", "estudio", "aprender", "curso", "repasar", "leer"]
        if any(w in lower for w in palabras_estudio):
            # Revisar si especificó materia
            materias_conocidas = ["python", "tesis", "programación", "programacion", "redes", "bases de datos", "cálculo", "calculo", "matemáticas", "matematicas", "inglés", "ingles", "química", "quimica"]
            materia_encontrada = None
            for m in materias_conocidas:
                if m in lower:
                    materia_encontrada = m.capitalize()
                    break

            if not materia_encontrada and len(text.split()) <= 4:
                # Es vago (ej: "quiero estudiar", "tengo que estudiar") -> LA IA DEBE PREGUNTAR
                return {
                    "action": "question",
                    "context_type": "study_topic",
                    "question": "¿Qué materia o tema específico quieres estudiar?",
                    "options": ["Python / Programación", "Tesis / Proyecto de Grado", "Lectura técnica", "Matemáticas"],
                    "allow_custom": True,
                    "custom_placeholder": "O escribe la materia o tema..."
                }
            else:
                subject = materia_encontrada or text
                return {
                    "action": "micro_steps",
                    "question": f"Desglose para estudiar {subject} con baja fricción:",
                    "is_goal": True,
                    "goal_title": f"Estudio: {subject}",
                    "tasks": [
                        {"title": f"{subject}: Revisión inicial o lectura corta (20 min)", "tag": "20 min", "task_type": "micro_step"},
                        {"title": f"{subject}: Práctica enfocada de 1 módulo o función (30 min)", "tag": "30 min", "task_type": "micro_step"},
                        {"title": f"{subject}: Síntesis de lo aprendido (15 min)", "tag": "15 min", "task_type": "micro_step"}
                    ]
                }

        # 2. CASO CITA MÉDICA / REUNIÓN / TRÁMITE
        palabras_cita = [
            "cita", "médico", "medico", "dentista", "doctor", "doctora", 
            "reunión", "reunion", "evaluación", "evaluacion", "certamen", "examen", "terapia"
        ]
        if any(w in lower for w in palabras_cita) or (detected_date and detected_date != now.strftime("%Y-%m-%d")):
            if not detected_time:
                # Falta la hora -> LA IA DEBE PREGUNTAR
                target_str = detected_day_name or "la cita"
                return {
                    "action": "question",
                    "context_type": "appointment_time",
                    "question": f"¿A qué hora agendamos {text} ({target_str})?",
                    "options": ["09:00", "11:30", "15:00", "17:00", "Sin hora fija"],
                    "allow_custom": True,
                    "custom_placeholder": "O escribe la hora exacta (ej: 14:15)...",
                    "target_date": detected_date or now.strftime("%Y-%m-%d")
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

        # 3. CASO ENTREGA O INFORME SIN PLAZO
        if any(w in lower for w in ["informe", "reporte", "entrega", "tarea"]):
            if not detected_date and not detected_time:
                return {
                    "action": "question",
                    "context_type": "deadline",
                    "question": "¿Para cuándo necesitas tener listo este trabajo?",
                    "options": ["Para hoy", "Para mañana", "Esta semana"],
                    "allow_custom": True,
                    "custom_placeholder": "O escribe la fecha límite..."
                }

        # 4. Tarea directa para hoy
        return {
            "action": "quick_task",
            "tasks": [
                {"title": text, "tag": "Hoy", "scheduled_time": None, "scheduled_date": None, "task_type": "quick"}
            ]
        }
