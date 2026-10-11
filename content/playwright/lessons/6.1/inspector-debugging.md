---
objective: "6.1"
title: Inspector y debugging paso a paso
---

[Ver el resumen en video](/media/playwright/inspector-debugging.mp4)

Debugging de tests consiste en reconstruir qué ocurrió, separar hipótesis y localizar la causa. Playwright ofrece herramientas que muestran acciones, DOM, localizadores, red, consola y código fuente.

## Modo debug e Inspector

```powershell
npx playwright test tests/login.spec.ts --debug
```

El modo debug ejecuta normalmente con navegador visible y abre Playwright Inspector. Desde allí podés:

- avanzar acción por acción;
- pausar y reanudar;
- inspeccionar localizadores;
- observar el call log;
- evaluar qué elementos coinciden.

También podés limitar a un test por ubicación:

```powershell
npx playwright test tests/login.spec.ts:12 --debug
```

Reducir el alcance acelera el ciclo de investigación.

## Pausas controladas

```ts
await page.pause();
```

La pausa abre herramientas interactivas cuando la ejecución llega a esa línea. Es útil localmente, pero no debe quedar en una suite CI: requiere intervención humana.

## UI Mode

```powershell
npx playwright test --ui
```

UI Mode permite elegir tests, observar pasos, volver a ejecutar y recorrer una línea temporal. Es especialmente útil durante desarrollo porque combina ejecución, watch y trazas.

## Debugger del editor

La extensión de VS Code puede ejecutar con breakpoints. Un breakpoint detiene el código TypeScript y permite inspeccionar variables, mientras el navegador queda disponible para observar estado.

Elegí la herramienta según la pregunta:

| Pregunta | Herramienta útil |
| --- | --- |
| ¿Por qué el localizador no coincide? | Inspector o locator picker. |
| ¿Qué valor tiene una variable? | Debugger de VS Code. |
| ¿Qué ocurrió antes del fallo en CI? | Trace Viewer. |
| ¿Qué mensaje emitió la aplicación? | Consola o traza. |

## Un proceso sistemático

1. Reproducí el caso más pequeño posible.
2. Leé la assertion, el error y el call log.
3. Clasificá la hipótesis: producto, test o entorno.
4. Observá estado justo antes del fallo.
5. Cambiá una variable por vez.
6. Confirmá la causa con una nueva ejecución.
7. Corregí y agregá evidencia que evite la regresión.

No empieces cambiando localizadores, timeouts y datos simultáneamente: si el test pasa, no sabrás qué modificación resolvió la causa.

## Diagnosticar localizadores

Inspector puede mostrar coincidencias y permitir ajustar la consulta. Revisá nombres accesibles y strictness antes de adoptar CSS profundo. Si el elemento no es accionable, investigá overlays, animaciones o estados deshabilitados en lugar de forzar el click.

## Why It Matters

Una herramienta de debugging aporta observaciones; el método convierte esas observaciones en una causa comprobada. El objetivo no es lograr una ejecución verde por cualquier medio, sino restaurar una señal confiable.

Cuanto más pequeño y reproducible sea el caso, menos hipótesis compiten. Filtrar un archivo, un proyecto y una línea suele ser el primer acelerador real del diagnóstico.
