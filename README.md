# learn-up: Playwright

Aplicación de estudio para el curso «Automatización de Testing con Playwright». Incluye 25 lecciones con videos, prácticas guiadas, preguntas por módulo y repaso. Cada estudiante usa su propia copia y guarda su progreso en su computadora.

Versión de la aplicación: **1.15**.

## Instalación

Necesitás Python 3.12 o superior, `uv`, Node.js y npm. Ejecutá estos comandos desde la carpeta de la aplicación, antes de abrirla por primera vez:

```powershell
uv sync
uv run python -m app.content.seed
uv run python -m app.content.validate
```

## Abrir la aplicación

En una terminal, desde la carpeta de la aplicación:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8011
```

En otra terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abrí <http://127.0.0.1:5173>. Mantené ambas terminales abiertas mientras estudiás; para cerrar la aplicación, presioná `Ctrl+C` en cada una. `npm ci` solo hace falta la primera vez o después de actualizar la aplicación.

## Cómo estudiar

Elegí el curso en la pantalla inicial. Leé las lecciones, mirá los videos y completá las prácticas. Usá **PRACTICAR MÓDULO** para ejercitar cada tema y el repaso para volver a las preguntas pendientes.

Tu progreso se guarda en `learn_up.duckdb`. Conservá ese archivo para continuar en próximas sesiones; no hace falta volver a sembrar el contenido cada vez que abrís la aplicación.

## Videos y material

Los videos se incluyen como archivos `.mp4` dentro de `media/playwright/`. Conservá esa carpeta junto con `content/` y respetá los nombres de los archivos. Los videos entregados se reproducen localmente y no requieren una cuenta de NotebookLM. Si falta un video, pedile el archivo al docente y guardalo en la ruta indicada por la lección.

## Preguntas sobre las lecciones

La opción «Preguntar sobre esto» es opcional y requiere un proveedor de IA configurado. Por defecto utiliza Codex CLI con tu propia sesión autenticada. Podés leer, practicar y mirar los videos sin configurar esta función. `.env.example` describe las opciones disponibles; no compartas tus credenciales.

## Incorporar material del docente

Si recibís un archivo `.learnup.zip`, podés importarlo desde «Acerca de» o, con la aplicación cerrada, ejecutar:

```powershell
uv run python scripts/manage_topic_transfer.py import curso.learnup.zip --dry-run
uv run python scripts/manage_topic_transfer.py import curso.learnup.zip --confirm
```

Revisá el informe antes de confirmar. Importá temas únicamente de personas y fuentes en las que confiás: la validación reduce riesgos comunes, pero no vuelve seguro un archivo no confiable. La transferencia incluye el material y los videos, sin el progreso ni las credenciales de otra persona.
