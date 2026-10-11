---
objective: "6.2"
title: Evidencias de ejecución
---

[Ver el resumen en video](/media/playwright/evidencias-ejecucion.mp4)

La evidencia permite investigar después de la ejecución, especialmente en CI donde no observamos el navegador. Playwright puede conservar capturas, videos, trazas, logs y adjuntos.

## Screenshots

```ts
await page.screenshot({ path: 'evidencias/pagina.png', fullPage: true });
await page.getByRole('dialog').screenshot({ path: 'evidencias/dialogo.png' });
```

Una captura muestra apariencia en un instante. Es útil para layout y estado visible, pero no revela por sí sola la secuencia, red o DOM anterior.

## Videos

```ts
export default defineConfig({
  use: {
    video: 'retain-on-failure',
  },
});
```

Opciones frecuentes:

- `off`;
- `on`;
- `retain-on-failure`;
- `on-first-retry`.

El video se guarda cuando cierra el BrowserContext. Grabar todo aumenta almacenamiento y tiempo; elegí una política acorde al diagnóstico.

## Trazas

```ts
export default defineConfig({
  use: {
    trace: 'on-first-retry',
  },
});
```

Una traza de Playwright Test puede incluir:

- acciones y sus tiempos;
- snapshots del DOM antes y después;
- source del test;
- red;
- consola;
- errores y attachments.

Abrir el reporte o una traza:

```powershell
npx playwright show-report
npx playwright show-trace trace.zip
```

Para fallos CI, la documentación recomienda normalmente trazas en lugar de grabar siempre videos y screenshots, porque concentran más contexto. `on-first-retry` evita el costo en cada ejecución y captura evidencia durante el primer intento de reproducción.

## Logs

Podés escuchar mensajes de consola:

```ts
page.on('console', message => {
  console.log(`[browser:${message.type()}] ${message.text()}`);
});
```

Y errores no manejados:

```ts
page.on('pageerror', error => {
  console.error(`[pageerror] ${error.message}`);
});
```

No conviertas cada log en assertion sin criterio. Primero decidí qué mensajes forman parte del contrato y cuáles son evidencia diagnóstica.

## Privacidad y tamaño

Capturas, videos y trazas pueden contener datos visibles, URLs, payloads o tokens de una sesión de prueba. Usá datos sintéticos, protegé artefactos CI y definí retención. Nunca publiques una traza sin revisar su contenido.

También evitá conservar todo indefinidamente. Una política razonable puede retener artefactos solo en fallos y eliminarlos después de un período.

## Elegir evidencia

| Necesidad | Evidencia principal |
| --- | --- |
| Comparar apariencia puntual | Screenshot. |
| Observar movimiento continuo | Video. |
| Reconstruir acciones, DOM, red y consola | Trace. |
| Integrar con búsquedas o alertas | Logs estructurados. |

## Why It Matters

Un fallo que solo ocurre en CI no debería obligar a adivinar. La política de evidencia debe responder preguntas concretas con el menor costo y exposición posibles.

Capturar más no siempre informa más. Elegí artefactos que permitan diferenciar producto, test y entorno, y asegurá que puedan asociarse con el caso y el intento correctos.
