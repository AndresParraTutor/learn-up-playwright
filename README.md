# learn-up: Playwright

¿Querés instalar y probar la app sin conocimientos técnicos? Seguí la [guía sencilla para Windows](GUIA_INSTALACION_SENCILLA.md), con instrucciones paso a paso y una prueba del recorrido del estudiante.

Aplicación de estudio para el curso «Automatización de Testing con Playwright». Incluye 25 lecciones con videos, prácticas guiadas, y preguntas de repaso por módulo.

Esta guía corresponde a la aplicación local. Cada estudiante usa su propia copia y guarda su progreso en su computadora.

Versión de la aplicación: **1.16**.

## Antes de empezar

Requisitos para la instalación local:

- **uv**, para administrar Python y las dependencias del back-end.
- **Python 3.12**, la versión seleccionada por este proyecto. Si no está instalada, `uv` puede [descargarla automáticamente](https://docs.astral.sh/uv/guides/install-python/) al preparar la aplicación.
- **Node.js y npm**: una versión LTS de Node.js **22.12 o superior**. npm se instala junto con Node.js.

Si todavía no tenés estas herramientas, instalalas con los pasos siguientes. Si ya cumplís los requisitos, pasá a [Verificar la instalación](#verificar-la-instalación).

Windows: Usar la terminal de Powershell, macOS/Linux: Usa la terminal

### Instalar uv

**Windows:** ejecutá el instalador oficial desde PowerShell:

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS y Linux:** ejecutá:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Abrí una terminal nueva para que se actualice el `PATH`. No necesitás instalar Python por separado: al ejecutar `uv sync` desde el repositorio, uv descarga Python 3.12 si falta. Para otros métodos o problemas específicos, consultá la [documentación de uv](https://docs.astral.sh/uv/getting-started/installation/).

### Instalar Node.js y npm

**Windows y macOS:** descargá el instalador desde [Node.js](https://nodejs.org/en/download). Seleccioná la versión **24 LTS** y tu sistema operativo; usá **Windows Installer (.msi)** en Windows o **macOS Installer (.pkg)** en macOS. Ejecutalo con las opciones predeterminadas, que incluyen npm, y abrí una terminal nueva.

**Linux (Bash o Zsh):** instalá Node.js con nvm, que permite administrar sus versiones sin una instalación global con `sudo`:

```bash
export NVM_DIR="$HOME/.nvm"
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.8/install.sh | bash
. "$NVM_DIR/nvm.sh"
nvm install 24
nvm alias default 24
```

Esto instala Node.js 24 LTS y npm, y deja esa versión como predeterminada para nuevas terminales. Si falta `curl`, instalalo con el gestor de paquetes de tu distribución. Para otros shells o problemas específicos, consultá la [documentación de nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

### Verificar la instalación

Estos comandos son iguales en PowerShell y en la terminal de macOS/Linux:

```bash
uv --version
node --version
npm --version
```

Comprobá que Node.js sea 24.x o una versión LTS compatible (22.12 o superior). Si PowerShell bloquea `npm.ps1`, usá `npm.cmd --version` y la alternativa indicada en [Problemas frecuentes](#problemas-frecuentes).

## Descargar la aplicación y los videos

La entrega tiene dos partes:

1. **Aplicación y material de estudio:** cloná el [repositorio de GitHub de learn-up Playwright](https://github.com/AndresParraTutor/learn-up-playwright) o descargalo con **Code → Download ZIP** y extraelo.
2. **Paquete con los videos:** descargá [playwright-20260906.learnup.zip](https://drive.google.com/file/d/1wH9mab2V5FNLRiHlzwIosWmfZFqupfuP/view). **No descomprimas este archivo:** se importa desde learn-up y contiene los 25 videos junto con el material del curso. Guardalo para el paso de [incorporar los videos y el material](#incorporar-los-videos-y-el-material-de-la-plataforma).

El repositorio no incluye los videos.

Ejecutá los comandos desde la **raíz del repositorio**, salvo donde se indique el cambio a `frontend/`.

Los comandos de instalación y arranque de **learn-up** tienen la misma sintaxis en PowerShell y en la terminal de macOS/Linux; los instaladores de herramientas de la sección anterior sí dependen del sistema operativo.

## Instalación inicial — una sola vez

Con el back-end detenido, instalá las dependencias de Python, cargá el contenido de `content/` en DuckDB y validá su estructura y referencias:

```bash
uv sync
uv run python -m app.content.seed
uv run python -m app.content.validate
```

`app.content.seed` crea o actualiza `learn_up.duckdb` con las lecciones, preguntas y prácticas. Esa base también almacena tu progreso. `app.content.validate` comprueba el contenido, pero no la presencia de los archivos de video.

Instalá las dependencias del front-end:

```bash
cd frontend
npm ci
cd ..
```

La configuración predeterminada funciona sin `.env` ni proveedor de IA.

En el primer inicio, completá la [importación del paquete de la plataforma](#incorporar-los-videos-y-el-material-de-la-plataforma) para disponer de los videos. Hasta entonces, podés leer las lecciones y realizar las actividades, pero en el lugar del video habrá un mensaje de error "No video found".

## Abrir y cerrar la aplicación — en cada sesión

La app necesita el **back-end** (FastAPI) y el **front-end** (React con Vite) ejecutándose en paralelo, por lo que vas a necesitar dos terminales.

**Back-end — terminal 1, desde la raíz del repositorio:**

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8011
```

**Front-end — terminal 2, desde la raíz del repositorio:**

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

En cualquier navegador, accedé a <http://127.0.0.1:5173>.

Para detenerla, usá `Ctrl+C` en ambas terminales.

En las sesiones siguientes, iniciá únicamente ambos procesos; no hace falta reinstalar dependencias ni volver a cargar el contenido.

## Cómo estudiar

- **Lecciones:** contenido y videos organizados por módulo, con búsqueda por concepto.
- **Prácticas:** ejercicios guiados con **Autocomprobación**. Ejecutá el código en el entorno indicado por la consigna y enviá las respuestas con **Comprobar**. Usá un proyecto separado del repositorio de learn-up para tus ejercicios de Playwright.
- **Panel → Practicar módulo:** cuestionarios por módulo. Al desplegar un módulo, **Preguntas** permite practicar un objetivo concreto. Usá **Enviar respuesta** para registrar cada respuesta y **Finalizar intento** para obtener el resultado.
- **Para repasar** y **Repaso rápido:** orientan el repaso. El **Historial de intentos** permite revisar resultados o continuar intentos pendientes.

El progreso se registra al enviar respuestas y comprobar prácticas; leer o mirar videos no completa un módulo. Las respuestas sin enviar no se guardan.

## Conservar tu progreso

Por defecto, `learn_up.duckdb` almacena el contenido, las respuestas y el progreso. Su ruta es relativa al directorio de trabajo del back-end: inicialo siempre desde la raíz del repositorio.

## Videos y material

La [importación del paquete de la plataforma](#incorporar-los-videos-y-el-material-de-la-plataforma) instala los `.mp4` en `media/playwright/`. Conservá la estructura y los nombres de `media/`, `content/` y `sources/`.

Las lecciones, los videos y los cuestionarios funcionan sin conexión una vez instalado el material. Los videos no requieren NotebookLM.

Si falta un video, verificá que la importación haya terminado correctamente y recargá la lección. Si persiste, reportá al tutor la lección afectada y el error.

## Incorporar los videos y el material de la plataforma

Importá `playwright-20260906.learnup.zip` una vez instalada la aplicación. Repetí el procedimiento si el tutor publica un paquete actualizado.

Desde la app:

1. En **Acerca de → Compartir un tema**, seleccioná el paquete y pulsá **Validar archivo**. Puede tardar por el tamaño de los videos.
2. Revisá el informe. Como el repositorio ya incluye el curso, el paquete se presenta como una **actualización**.
3. Pulsá **Confirmar actualización** (o **Confirmar importación** si el curso aún no existe). Al terminar, recargá la página y verificá la reproducción de un video.

La importación carga y valida el contenido automáticamente; no necesitás ejecutar el comando de carga inicial después. La transferencia incluye material y videos, pero no el progreso ni las credenciales de otra persona.

Como alternativa, podés importar el paquete desde la terminal. Detené primero el back-end con `Ctrl+C` para liberar la base de datos. Los ejemplos asumen el ZIP en la raíz del repositorio; ajustá la ruta si lo guardaste en otra ubicación. Primero validá:

```bash
uv run python -m scripts.manage_topic_transfer import "playwright-20260906.learnup.zip" --dry-run
```

`--dry-run` valida sin instalar. Revisá el informe antes de confirmar:

```bash
uv run python -m scripts.manage_topic_transfer import "playwright-20260906.learnup.zip" --confirm
```

Después, iniciá la aplicación.

Las actualizaciones de **la aplicación** se distribuyen por GitHub. Respaldá tus archivos antes de actualizar y seguí las indicaciones de esa versión; después sincronizá las dependencias del back-end y del front-end. Los paquetes de material y videos se distribuyen por la plataforma de la universidad y no requieren reinstalar dependencias.

## Preguntas con IA — opcional

Seleccioná un fragmento de una lección o práctica y usá **Preguntar sobre esto**. La respuesta se incorpora a las preguntas y respuestas del material local.

El cliente predeterminado es **Antigravity CLI (`agy`)**, de Google. También podés usar **Codex CLI** o **Claude Code**. Instalá y autenticá solo el cliente que elijas, con el mismo usuario y en el mismo entorno que el back-end: si ejecutás learn-up en WSL, instalá y autenticá el cliente dentro de WSL. La lectura, las prácticas y los videos funcionan sin esta integración.

### Antigravity CLI (`agy`) — predeterminado

`agy` es Antigravity CLI; no es el comando `gemini` de Gemini CLI. Para instalarlo, ejecutá el [instalador oficial de Google](https://www.antigravity.google/docs/getting-started/).

**Windows (PowerShell):**

```bash
irm https://antigravity.google/cli/install.ps1 | iex
```

**macOS/Linux:**

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

En una terminal nueva, verificá la instalación e iniciá sesión:

```bash
agy --version
agy
```

Completá el inicio de sesión en el navegador. [Autenticación de Antigravity](https://www.antigravity.google/docs/install?tab=cli).

Salí de la sesión interactiva con `/exit` y verificá que responda sin interacción:

```bash
agy -p "Respondé únicamente: OK"
```

learn-up usa `agy_cli` por defecto. Si ya tenías otro cliente configurado, cambiá esta línea en el archivo `.env` de la raíz del repositorio:

```dotenv
LEARNUP_LLM_BACKEND=agy_cli
```

Para elegir un modelo específico, consultá los disponibles con `agy models` y agregá `LEARNUP_AGY_CLI_MODEL=identificador-del-modelo` a `.env`. Si omitís esa variable, se usa el modelo configurado en Antigravity.

### Codex CLI

Instalá el cliente con npm y autenticá tu cuenta:

```bash
npm install -g @openai/codex@latest
codex --version
codex login
codex login status
```

Completá el flujo del navegador con una cuenta que tenga acceso a Codex. La sesión del CLI se reutiliza para las consultas. Referencias: [instalación con npm](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex#quickstart-using-goals) y [autenticación de Codex](https://learn.chatgpt.com/docs/auth).

Configurá en `.env`:

```dotenv
LEARNUP_LLM_BACKEND=codex_cli
```

Verificá una consulta desde la terminal:

```bash
codex exec --ephemeral --sandbox read-only --skip-git-repo-check "Respondé únicamente: OK"
```

### Claude Code (`claude`)

Instalá el cliente con el [instalador oficial de Anthropic](https://code.claude.com/docs/en/setup).

**Windows (PowerShell):**

```bash
irm https://claude.ai/install.ps1 | iex
```

**macOS/Linux:**

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

En una terminal nueva, ejecutá:

```bash
claude --version
claude
```

Completá el inicio de sesión con una cuenta que tenga acceso a Claude Code; si ya hay una sesión y necesitás cambiarla, usá `/login`. Después salí con `/exit`. [Autenticación de Claude Code](https://code.claude.com/docs/en/authentication).

Configurá en `.env`:

```dotenv
LEARNUP_LLM_BACKEND=claude_cli
LEARNUP_CLAUDE_CLI_MODEL=sonnet
```

Verificá una consulta desde la terminal:

```bash
claude -p "Respondé únicamente: OK" --model sonnet --tools "" --no-session-persistence
```

### Activar el cliente en learn-up

Las líneas de los bloques `dotenv` son contenido de `.env`, no comandos de terminal. Creá ese archivo si no existe o editá la selección actual: dejá una sola línea `LEARNUP_LLM_BACKEND`. No necesitás copiar todas las opciones de [`.env.example`](.env.example).

Después de instalar, autenticar o cambiar el cliente, reiniciá el back-end desde una terminal que lo tenga en el `PATH`. Probá **Preguntar sobre esto** en una lección. Si falla, ejecutá la consulta de prueba del cliente desde la misma terminal en que corre el back-end, para distinguir un problema de autenticación o acceso de uno de configuración de learn-up.

Las consultas consumen el acceso y la cuota de la cuenta autenticada; learn-up no incluye una suscripción. No compartas credenciales.

## Problemas frecuentes

| Qué ocurre | Qué revisar |
| --- | --- |
| La terminal no reconoce `uv`, `node` o `npm`. | Verificá la instalación y el `PATH`. |
| PowerShell dice que no puede ejecutar `npm.ps1`. | Usá `npm.cmd` en lugar de `npm` en los comandos de esta guía, por ejemplo `npm.cmd ci`. |
| `npm ci` informa una versión de Node.js incompatible. | Comprobá `node --version` e instalá una versión LTS de Node.js 22.12 o superior. |
| No se encuentra `pyproject.toml`, `app` o `package.json`. | Ejecutá `uv` desde la raíz del repositorio y `npm` desde `frontend/`. |
| La interfaz no carga el material. | Revisá los logs de ambos procesos. Si reiniciaste el back-end, recargá la página para renovar el token de sesión. |
| No hay lecciones. | Con el back-end detenido, ejecutá `app.content.seed` y `app.content.validate` como en la instalación inicial. |
| El puerto 8011 o 5173 está ocupado. | Liberá el puerto. Si necesitás cambiarlo, ajustá también el proxy en `frontend/vite.config.ts` y los puertos permitidos mediante `LEARNUP_BACKEND_PORT` y `LEARNUP_FRONTEND_PORT`; cambiar solo el comando de arranque no alcanza. |
| `learn_up.duckdb` está bloqueado. | Usá una sola instancia del back-end y detenela antes de cargar contenido o importar por CLI. |
| No aparece tu progreso. | Verificá el directorio de trabajo del back-end y la ubicación del `learn_up.duckdb` original. |

Si el problema continúa, compartí con el tutor el comando que ejecutaste y el mensaje de error completo, sin incluir credenciales.
