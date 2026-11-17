# seeU

Un supervisor de escritorio sobrio y calmado, pensado para personas que nos sentimos sobrecargadas y necesitamos poner orden en el día a día sin que la herramienta se convierta en otra fuente de estrés.

## Por qué creé este proyecto

Como estudiante de informática a punto de egresar, muchas veces me descubro con demasiadas cosas en la cabeza, sintiendo esa parálisis clásica donde quiero hacer de todo pero el agobio me impide dar el primer paso.

Las aplicaciones de notas tradicionales me terminaban saturando todavía más, porque me llenaban de notificaciones ruidosas, interfaces repletas de botones o metodologías complejas que solo aumentaban mi ansiedad.

Por eso construí seeU, concibiéndolo como un compañero silencioso y liviano que vive en mi pantalla secundaria, listo para recibir cualquier pendiente rápido, negociar mis tiempos de estudio y permitirme tachar actividades para recuperar la calma mental.

## Lo que hace seeU

- Modo Foco, pensado para mantener en pantalla solo lo que importa hoy y despejar el ruido mental.
- Micro orbe flotante de 34 px, con un brillo suave al pasar el mouse y un contador que se actualiza en segundo plano.
- Presencia en la bandeja del sistema. Al ocultar la ventana, seeU pausa el reloj, el carrusel, la sincronización periódica y los avisos de la ventana hasta que vuelvas a abrirla.
- Modo Enfoque con estrella prioritaria, para destacar aquellas tareas esenciales y filtrarlas con un clic, desactivándose automáticamente cada vez que reinicio el programa para arrancar fresco al día siguiente.
- Carrusel ambiental con transición suave, el cual rota de forma pausada entre el Foco, la Agenda y las Metas cada diez segundos, deteniéndose de inmediato al pasar el ratón por encima o al interactuar con la ventana.
- Heatmap semanal de lunes a domingo, mostrando cuadritos elegantes que cambian de brillo según el volumen de actividades de cada día.
- Revisión directa de pendientes anteriores, con un mensaje sobrio que me consulta si movemos esas tareas para hoy o si las descartamos sin complicaciones.
- Mini agente conversacional, integrado para guiarme si escribo algo vago como estudiar o agendar médico, calculando tiempos realistas o funcionando de manera totalmente autónoma si estoy sin conexión.
- Hábitos diarios recurrentes, permitiendo registrar actividades como hacer ejercicio todos los días sin amarrarlas a una fecha única.
- Conexión con agentes externos de Inteligencia Artificial mediante CLI y protocolo MCP, para que asistentes como Codex, Gemini o Claude puedan añadir tareas, crear planes de estudio o consultar mis estadísticas de ticks por meses.

## Cómo correrlo en Windows

Para poner a andar seeU en Windows de la manera más sencilla posible, preparé un instalador asistido y un lanzador directo que se encargan de todo sin pelear con rutas de módulos.

Si es la primera vez que lo uso, simplemente hago doble clic sobre el archivo instalar_windows.bat y este script se encarga de crear el entorno virtual e instalar las librerías necesarias.

Para abrir seeU en el día a día, solo hago doble clic en el archivo iniciar_seeU.bat o ejecuto el punto de entrada universal desde PowerShell.

```cmd
cd supervisor-personal
python run_seeu.py
```

Al abrir el programa, seeU guarda las tareas y preferencias en SQLite. En Windows, la ubicación predeterminada es `%APPDATA%\seeU\data\supervisor.db`. En Linux es `~/.local/share/seeU/data/supervisor.db`. Si ejecutas desde el código y ya tienes `data/supervisor.db` en el proyecto, seeU sigue usando esa base.

El [instalador de GitHub Releases](https://github.com/Seavuelo/supervisor-personal/releases) incluye las dependencias de escritorio. Puedes instalarlo sobre una versión previa con la misma cuenta de Windows para conservar tareas y ajustes. Si ejecutas el código fuente, usa Python 3.11 o superior.

## Cómo compilar el ejecutable EXE para Windows

Si quiero entregar el programa listo para que cualquiera lo use sin necesidad de tener Python instalado, puedo generar el archivo EXE de dos formas muy cómodas.

En mi propio computador con Windows puedo hacer doble clic sobre compilar_exe.bat para que PyInstaller empaquete seeU.exe dentro de la carpeta dist.

Además, dejé configurado un flujo automático de GitHub Actions que compila el ejecutable nativo en los servidores de GitHub cada vez que subo cambios, permitiendo descargar el archivo comprimido directamente desde la sección de acciones de mi repositorio.

## Cómo correrlo en Linux

En entornos Linux como Debian, Ubuntu, Arch o distribuciones ligeras, abro la terminal y sigo esta secuencia.

```bash
cd supervisor-personal
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 run_seeu.py
```

## Integración con agentes de Inteligencia Artificial

seeU fue diseñado para entenderse de forma natural con agentes autónomos como Codex, Gemini o asistentes en terminal, permitiéndoles consultar el calendario o planificar semanas de estudio.

Puedo pedirle a un agente que consulte mis métricas o que cree un plan completo ejecutando comandos limpios que entregan respuestas en texto o en formato JSON estructurado.

```bash
python -m supervisor.cli stats
python -m supervisor.cli month
python -m supervisor.cli plan "Preparar examen de redes" --steps "Lectura capitulo 1, Hacer resumen, 5 ejercicios"
python -m supervisor.cli task add "Dentista manana" --date 2026-11-05 --time 15.00
python -m supervisor.cli task tick 1
```

Si utilizo herramientas compatibles con el protocolo MCP como Claude Desktop o Cursor, seeU cuenta con su propio servidor integrado que se inicia ejecutando el subcomando mcp, permitiendo que la inteligencia artificial añada actividades o revise los ticks completados en tiempo real.

## Configuración de Gemini

seeU funciona de manera completa y autónoma sin necesidad de internet, gracias a su motor conversacional interno de reglas lógicas.

Para usar Gemini, pega la clave de Google AI Studio en Ajustes y selecciona **Guardar clave**. seeU la verifica antes de guardarla en el almacén de credenciales de tu sistema y migra las claves guardadas en SQLite al actualizar. La clave guardada está vinculada a tu cuenta del sistema. En otro equipo, pégala de nuevo.

Si falla la comprobación, el mensaje distingue entre pérdida de conexión, clave rechazada, permisos, cuota y disponibilidad del modelo. Revisa los permisos y el uso del proyecto en Google AI Studio. En Linux, si el almacén de credenciales no está disponible, la clave dura la sesión. También puedes configurar la variable de entorno `GEMINI_API_KEY`.

En esa misma pantalla de ajustes puedo activar el inicio automático al encender el equipo, permitiendo que seeU me acompañe desde que prendo el computador sin tener que buscarlo manualmente.

## Filosofía de diseño y rendimiento

La interfaz usa PyQt6 y pywebview. Los estilos se cargan desde el equipo, y SQLite indica si hay cambios antes de que seeU vuelva a cargar los datos.

No busco competir con plataformas corporativas complejas, sino tener una herramienta honesta, ligera y propia que me ayude a terminar mi carrera con la mente en paz.

Desarrollado con dedicación por Seavuelo.
