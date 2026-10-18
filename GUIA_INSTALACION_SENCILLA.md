# Guía sencilla: instalar y probar learn-up en Windows

Esta guía está pensada para personas que quieran conocer la aplicación sin que necesiten saber programar: seguí los pasos en orden y copiá los textos indicados.

Al terminar vas a poder abrir el curso, ver un video y probar un cuestionario. La aplicación y el progreso quedan guardados en tu computadora; esta prueba no modifica el trabajo de los estudiantes.

## 1. Antes de empezar

Necesitás una computadora con Windows, conexión a Internet para las descargas y un navegador, como Edge o Chrome.

La preparación se hace una sola vez: pasos 2 a 6. Para usar la app otro día, repetí solo el paso 8.

## 2. Instalar las dos herramientas necesarias

Estas herramientas permiten que la app funcione. No necesitás aprender a usarlas.

### Node.js

1. Abrí la [página oficial de descarga de Node.js](https://nodejs.org/en/download).
2. Elegí la versión **24 LTS**, el sistema **Windows** y el instalador **Windows Installer (.msi)**.
3. Abrí el archivo descargado y seguí el asistente con las opciones predeterminadas hasta terminar. Si ofrece herramientas adicionales, no son necesarias para esta prueba.

### uv

1. Abrí el menú **Inicio** de Windows, escribí **PowerShell** y abrí **Windows PowerShell**. Aparecerá una ventana donde se pueden escribir instrucciones.
2. Copiá la línea siguiente, pegala en esa ventana con el botón derecho del mouse y presioná **Enter**. Es el comando del [instalador oficial de uv](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. Esperá a que termine y cerrá la ventana.
4. Abrí **Windows PowerShell** de nuevo (es importante que no sea la ventana anterior, porque no tendría reflejados los cambios). Copiá y ejecutá estas líneas **una por vez**, presionando **Enter** después de cada una:

```powershell
uv --version
node --version
npm.cmd --version
```

**Cómo saber si salió bien:** cada línea muestra un número de versión; la de Node.js debe comenzar con `v24.` si instalaste la versión indicada. Si aparece «no se reconoce», consultá el paso 9 antes de continuar. Podés cerrar esta ventana al terminar.

## 3. Descargar la aplicación y los videos

Son **dos descargas distintas**:

| Descarga | Qué hacer con ella |
| --- | --- |
| [Aplicación learn-up en GitHub](https://github.com/AndresParraTutor/learn-up-playwright) | Pulsá el botón verde **Code → Download ZIP**. Después, en **Descargas**, hacé clic derecho sobre el archivo y elegí **Extraer todo…**. Elegí una carpeta que puedas conservar, por ejemplo dentro de **Documentos**. |
| [Paquete de videos del curso](https://drive.google.com/file/d/1wH9mab2V5FNLRiHlzwIosWmfZFqupfuP/view) | Pulsá **Descargar** y esperá a que termine. Se llama `playwright-20260906.learnup.zip`. **No lo extraigas**: la app lo abrirá en el paso 6. |

Abrí la carpeta extraída de la aplicación. Si adentro hay otra carpeta, entrá en ella hasta ver **README.md**, **pyproject.toml** y las carpetas **app** y **frontend**. Windows puede ocultar las terminaciones `.md` y `.toml`.

En esta guía llamamos **carpeta de la aplicación** a esa carpeta. Recordá dónde la guardaste: vas a usarla cada vez que abras learn-up. Trabajá siempre en la carpeta extraída, no dentro del ZIP.

## 4. Preparar la aplicación — solo la primera vez

### Abrir una ventana en la carpeta correcta

1. En el Explorador de archivos, abrí la **carpeta de la aplicación** del paso anterior.
2. Hacé clic en la barra de direcciones de arriba, donde aparece la ubicación de la carpeta; no en el cuadro de búsqueda.
3. Escribí `powershell` y presioná **Enter**. Se abre una ventana preparada para trabajar en esa carpeta.

### Copiar las instrucciones

Copiá las siguientes líneas **una por vez** y presioná **Enter**. Esperá a que reaparezca una línea que empieza con `PS` y termina con `>` antes de pegar la siguiente. Las descargas pueden tardar varios minutos. Si aparece un error, detenete y consultá el paso 9.

```powershell
uv sync
uv run python -m app.content.seed
uv run python -m app.content.validate
```

**Cómo saber si salió bien:** aparecen los mensajes **Contenido sembrado correctamente.** y **Validación de contenido correcta.** Son las confirmaciones de que el curso quedó preparado.

En la misma ventana, ejecutá estas tres líneas, también una por vez:

```powershell
cd frontend
npm.cmd ci
cd ..
```

La segunda línea descarga los componentes de la pantalla de la app. Al terminar, la tercera vuelve a la carpeta de la aplicación. No necesitás crear archivos de configuración ni configurar inteligencia artificial para esta prueba.

## 5. Abrir learn-up

La app necesita **dos ventanas de PowerShell abiertas al mismo tiempo**. Podés minimizarlas mientras usás el navegador.

### Primera ventana

Usá la ventana del paso 4, después de ejecutar `cd ..`. Si la cerraste, abrí otra desde la carpeta de la aplicación como se explicó antes.

Pegá esta línea y presioná **Enter**:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8011
```

**Cómo saber si salió bien:** aparece `Uvicorn running on http://127.0.0.1:8011`. Esta vez la ventana queda ocupada: es normal. Dejala abierta y no escribas más instrucciones en ella.

### Segunda ventana

Volvé al Explorador de archivos y abrí **otra** ventana de PowerShell desde la misma **carpeta de la aplicación**: escribí `powershell` en la barra de direcciones y presioná **Enter**.

Ejecutá estas líneas una por vez:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

**Cómo saber si salió bien:** aparece la dirección `http://127.0.0.1:5173`. Dejá esta ventana abierta también.

### Abrir la pantalla del curso

Abrí Edge o Chrome y pegá esta dirección en la barra de direcciones:

**<http://127.0.0.1:5173>**

Esa dirección abre la aplicación de tu propia computadora. Podés guardarla en Favoritos, pero las dos ventanas deben estar funcionando para que abra.

## 6. Incorporar los videos — solo la primera vez

1. Dentro de learn-up, entrá en **Acerca de** y buscá **Compartir un tema**.
2. En **Archivo del tema**, seleccioná el archivo `playwright-20260906.learnup.zip` que descargaste en el paso 3.
3. Pulsá **Validar archivo** y esperá. Puede tardar porque contiene los videos.
4. Revisá el informe: debe indicar que el archivo es compatible. Es normal que diga **una actualización**, porque el curso ya viene en la aplicación.
5. Pulsá **Confirmar actualización**. Si aparece **Confirmar importación**, usá ese botón.
6. Esperá a que termine la operación y los botones vuelvan a estar disponibles. Si aparece un error, consultá el paso 9. Recargá la página con **F5**, abrí una lección y probá reproducir el video.

Después de instalar el material, las lecciones, los videos y los cuestionarios se pueden usar sin Internet.

## 7. Hacer una prueba como estudiante

No necesitás conocer Playwright para comprobar el funcionamiento. Podés elegir respuestas de prueba aunque no sean correctas.

- [ ] Entrá en **Lecciones**, abrí una lección y comprobá que se puede leer el contenido.
- [ ] Reproducí su video y probá pausarlo y continuarlo.
- [ ] Entrá en **Panel** y pulsá **Practicar módulo** en uno de los módulos.
- [ ] Elegí una respuesta y pulsá **Enviar respuesta**. Comprobá que aparece una explicación.
- [ ] Usá **Siguiente** y enviá una respuesta para cada pregunta. Después aparecerá **Finalizar intento**: pulsalo para ver el resultado.
- [ ] Volvé al **Panel** y revisá el **Historial de intentos**.
- [ ] Entrá en **Prácticas** y comprobá que se ven las consignas. Resolver los ejercicios de programación puede quedar para una prueba con el tutor.
- [ ] Cerrá y volvé a abrir la app siguiendo el paso 8; comprobá que el intento sigue en el historial.

**El progreso se guarda al enviar respuestas o comprobar prácticas.** Leer una lección o mirar un video no marca un módulo como completado. Las respuestas que todavía no enviaste no se guardan.

La función **Preguntar sobre esto** requiere una configuración adicional de IA. Podés completar esta prueba sin usarla.

## 8. Cerrar la app y volver a abrirla otro día

**Para cerrar:** terminá de enviar tus respuestas. En cada una de las dos ventanas de PowerShell, mantené presionada **Ctrl** y pulsá **C**. Si pregunta si querés terminar el trabajo, confirmá según las opciones que muestre. Luego cerrá las ventanas y la pestaña del navegador. Cerrar solo la pestaña no detiene la app.

**Para volver a abrir:** repetí únicamente el **paso 5**, abriendo las dos ventanas desde la misma carpeta de la aplicación. No repitas la instalación ni la importación de videos.

Conservá esa carpeta: el archivo `learn_up.duckdb` guarda tus respuestas y tu progreso. Para hacer una copia de seguridad, cerrá la app como se indicó y copiá la carpeta completa a otra ubicación. Cada estudiante debe tener su propia copia; tu instalación de prueba no es un registro compartido de la Universidad.

## 9. Si algo no funciona

| Qué ves | Qué hacer |
| --- | --- |
| «uv no se reconoce», «node no se reconoce» o «npm.cmd no se reconoce». | Cerrá las ventanas de PowerShell y abrí una nueva. Repetí las comprobaciones del paso 2. Si sigue igual, pedí ayuda para revisar la instalación de esa herramienta. |
| Un error menciona `pyproject.toml`, `app` o `package.json` y dice que no lo encuentra. | Revisá que abriste PowerShell desde la carpeta que contiene **app** y **frontend**. Los comandos que empiezan con `npm.cmd` se ejecutan después de `cd frontend`. |
| El navegador dice que no puede acceder a la página. | Revisá que las dos ventanas sigan abiertas y muestren las direcciones del paso 5. Usá exactamente `http://127.0.0.1:5173`. |
| La pantalla abre, pero no muestra el curso. | Revisá la primera ventana y recargá la página con **F5**. Si sigue igual, enviá el error al tutor. |
| El video muestra «No video found». | Completá el paso 6 y recargá la lección. Si ya lo hiciste, indicá al tutor qué lección falla. |
| Aparece «port is already in use», «puerto ocupado» o un error que dice que la base está bloqueada. | Buscá ventanas de learn-up que hayan quedado abiertas, detenelas con **Ctrl+C** y repetí el paso 5 una sola vez. Si continúa, reiniciá la computadora. |
| Una descarga o instalación está bloqueada por la Universidad, o no podés acceder al paquete de videos. | Pedí ayuda al área de informática o al tutor e indicá cuál es la descarga que no podés completar. |

Para pedir ayuda, enviá el **número de paso**, el **texto del error o una captura de pantalla** y una frase sobre qué estabas haciendo. Por ejemplo: «Estoy en el paso 5, segunda ventana. Pegué el comando y apareció este mensaje». Así el tutor puede ayudarte sin que tengas que interpretar el error.
