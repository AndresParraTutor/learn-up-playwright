---
objective: "6.3"
title: Reportes HTML y troubleshooting
---

[Ver el resumen en video](/media/playwright/reportes-troubleshooting-defectos.mp4)

Un reporter transforma eventos de ejecución en información para personas o sistemas. Playwright Test incluye reporters de terminal, HTML y formatos estructurados.

## Reporter HTML

```ts
export default defineConfig({
  reporter: [['html', { open: 'never' }]],
});
```

Después de ejecutar:

```powershell
npx playwright show-report
```

El reporte permite filtrar tests pasados, fallidos, flaky, omitidos y revisar errores, pasos y attachments.

## Reporters según contexto

```ts
reporter: process.env.CI
  ? [['dot'], ['html', { open: 'never' }]]
  : [['list'], ['html']],
```

- `list` muestra una línea detallada por test.
- `line` reutiliza una línea y reduce ruido.
- `dot` es compacto para CI.
- `html` crea un reporte navegable.
- JSON o JUnit integran resultados con otras plataformas.

Un reporte no corrige un test; conserva y presenta su señal.

## Troubleshooting por capas

Ante un fallo, recorré capas en orden:

1. **Expectation:** qué se esperaba y qué ocurrió.
2. **Localizador/acción:** qué elemento se encontró y por qué fue o no accionable.
3. **Producto:** consola, red, DOM y estado visible.
4. **Datos:** precondiciones, colisiones y limpieza.
5. **Entorno:** versiones, navegador, recursos, servicios y configuración.

Usá el reporte para seleccionar evidencia, luego Inspector o Trace Viewer para profundizar.

## Timeouts y retries

Un timeout señala una condición ausente dentro de un límite. Un retry vuelve a ejecutar el test. Ninguno explica la causa.

Los retries clasifican resultados:

- passed en el primer intento;
- flaky si falla y luego pasa;
- failed si no pasa tras los intentos permitidos.

Una suite que “se arregla” aumentando retries puede estar ocultando carreras o contaminación de datos. Tratá los flaky como defectos del sistema de pruebas o del producto.

## Reporte de defecto reproducible

Cuando la evidencia apunta al producto, un reporte útil incluye:

- identificador y título claro;
- entorno y versión;
- referencia al requisito, riesgo o caso;
- precondiciones y datos no sensibles;
- pasos mínimos de reproducción;
- resultado esperado y real;
- frecuencia o intento;
- severidad/impacto y prioridad acordada;
- attachments relevantes;
- estado del defecto.

Ejemplo breve:

```text
Título: Checkout permite confirmar sin stock
Entorno: build 2026.08.28, Chromium
Precondición: producto SKU-42 con stock 0
Pasos: abrir carrito -> confirmar compra
Esperado: mensaje “Sin stock”, sin crear pedido
Real: pedido creado y navegación a /confirmacion/918
Evidencia: trace.zip del test checkout-stock-001
```

Evitá “no funciona” y videos sin contexto. La reproducción debe permitir que otra persona observe el mismo resultado.

## Why It Matters

La salida verde o roja es el comienzo de una conversación, no su final. Reportes y trazas convierten un estado en evidencia; un proceso de troubleshooting convierte evidencia en causa probable; un reporte de defecto convierte esa causa en trabajo accionable.

El objetivo operativo es reducir el tiempo desde el fallo hasta una decisión confiable, sin silenciar señales ni saturar al equipo con artefactos irrelevantes.
