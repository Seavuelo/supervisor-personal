# seeU

Un supervisor de escritorio sobrio y calmado, pensado para personas que nos sentimos sobrecargadas y necesitamos poner orden en el día a día sin que la herramienta se convierta en otra fuente de estrés.

## Por qué creé este proyecto

Como estudiante de informática a punto de egresar, muchas veces me descubro con demasiadas cosas en la cabeza, sintiendo esa parálisis clásica donde quiero hacer de todo pero el agobio me impide dar el primer paso.

Las aplicaciones de notas tradicionales me terminaban saturando todavía más, porque me llenaban de notificaciones ruidosas, interfaces repletas de botones o metodologías complejas que solo aumentaban mi ansiedad.

Por eso construí seeU, concibiéndolo como un compañero silencioso y liviano que vive en mi pantalla secundaria, listo para recibir cualquier pendiente rápido, negociar mis tiempos de estudio y permitirme tachar actividades para recuperar la calma mental.

## Lo que hace seeU

- Modo Foco, pensado para mantener en pantalla solo lo que importa hoy y despejar el ruido mental.
- Micro orbe flotante, que comprime toda la interfaz en un círculo diminuto de vidrio oscuro cuando necesito espacio en el monitor.
- Presencia en la bandeja del sistema, permitiendo que la ventana viva en segundo plano al lado del reloj y el volumen sin estorbar en la barra de tareas.
- Modo Enfoque con estrella prioritaria, para destacar aquellas tareas esenciales y filtrarlas con un clic, desactivándose automáticamente cada vez que reinicio el programa para arrancar fresco al día siguiente.
- Carrusel ambiental con transición suave, el cual rota de forma pausada entre el Foco, la Agenda y las Metas cada diez segundos, deteniéndose de inmediato al pasar el ratón por encima o al interactuar con la ventana.
- Heatmap semanal de lunes a domingo, mostrando cuadritos elegantes que cambian de brillo según el volumen de actividades de cada día.
- Revisión directa de pendientes anteriores, con un mensaje sobrio que me consulta si movemos esas tareas para hoy o si las descartamos sin complicaciones.
- Mini agente conversacional, integrado para guiarme si escribo algo vago como estudiar o agendar médico, calculando tiempos realistas o funcionando de manera totalmente autónoma si estoy sin conexión.
- Hábitos diarios recurrentes, permitiendo registrar actividades como hacer ejercicio todos los días sin amarrarlas a una fecha única.

## Cómo correrlo en Windows

Para clonar y poner a andar seeU en una computadora con Windows, abro una terminal de PowerShell o CMD en la carpeta donde quiera el proyecto y ejecuto los siguientes pasos.

```cmd
cd supervisor-personal
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python src\supervisor\main.py
```

Al abrir el programa por primera vez, este creará su propia base de datos SQLite de forma automática en la carpeta data, guardando ahí todas las tareas de manera local y segura.

## Cómo correrlo en Linux

En entornos Linux como Debian, Ubuntu, Arch o distribuciones ligeras, abro la terminal y sigo esta secuencia.

```bash
cd supervisor-personal
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 src/supervisor/main.py
```

## Configuración y uso de Inteligencia Artificial

seeU funciona de manera completa y autónoma sin necesidad de internet, gracias a su motor conversacional interno de reglas lógicas.

Si quiero potenciar el mini agente con modelos de Google, simplemente voy a la pestaña de ajustes dentro de seeU e ingreso mi clave de Gemini, la cual queda cifrada y guardada en mi equipo local para responder con calidez y memoria contextual.

En esa misma pantalla de ajustes puedo activar el inicio automático al encender el equipo, permitiendo que seeU me acompañe desde que prendo el computador sin tener que buscarlo manualmente.

## Filosofía de diseño y rendimiento

Toda la interfaz fue construida bajo la premisa Ponytail de bajo consumo, utilizando PyQt6 y pywebview para lograr una estética oscura de cristal esmerilado que se mantiene en cero por ciento de uso de procesador en reposo.

No busco competir con plataformas corporativas complejas, sino tener una herramienta honesta, ligera y propia que me ayude a terminar mi carrera con la mente en paz.

Desarrollado con dedicación por Seavuelo.
