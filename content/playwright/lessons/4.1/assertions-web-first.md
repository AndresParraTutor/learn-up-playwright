---
objective: "4.1"
title: Fundamentos de assertions web-first
---

[Ver el resumen en video](/media/playwright/assertions-web-first.mp4)

Una assertion compara un resultado real con una expectativa y decide si el caso aporta la evidencia buscada. Playwright Test expone `expect` con matchers genéricos y matchers específicos para web.

```ts
import { test, expect } from '@playwright/test';
```

## Assertions genéricas

Evalúan un valor que ya fue calculado:

```ts
expect(total).toBe(42);
expect(items).toContain('Playwright');
expect(resultado.ok).toBeTruthy();
```

Son inmediatas: no vuelven a leer el sistema esperando que el valor cambie.

## Assertions web-first

Reciben un objeto como Locator o Page y vuelven a comprobar su estado:

```ts
await expect(page.getByRole('status')).toHaveText('Procesado');
await expect(page).toHaveURL(/\/resultado$/);
```

Si el mensaje tarda unos milisegundos, `toHaveText` reconsulta el elemento hasta que coincide o vence el timeout de expect. Ese reintento basado en estado reduce condiciones de carrera.

## El `await` es obligatorio

Los matchers que reintentan son asíncronos:

```ts
await expect(locator).toBeVisible();
```

Omitir `await` puede dejar una Promise sin esperar y hacer que el test termine antes de evaluar la condición. TypeScript y reglas de lint ayudan, pero la intención debe ser clara.

## Elegir la expectativa correcta

Preferí el matcher que describe el comportamiento:

```ts
await expect(campo).toHaveValue('ana@example.test');
await expect(boton).toBeEnabled();
await expect(lista).toHaveCount(3);
```

Evita patrones de lectura manual:

```ts
// Menos robusto: captura un valor instantáneo.
expect(await locator.textContent()).toBe('Procesado');
```

La versión web-first suele expresar mejor la condición y reintenta de manera segura.

## Negación y mensajes

```ts
await expect(page.getByRole('alert')).not.toBeVisible();
```

Una assertion negativa debe tener una razón de negocio. “No existe ningún error” puede ser demasiado amplia; “no se muestra el error de stock” es más diagnóstica.

Podés agregar contexto:

```ts
await expect(
  page.getByRole('status'),
  'el backend debe confirmar el guardado',
).toHaveText('Guardado');
```

## Timeouts

El timeout de una assertion no es necesariamente el timeout total del test. Puede configurarse globalmente o por caso:

```ts
await expect(status).toHaveText('Listo', { timeout: 10_000 });
```

Aumentalo cuando el comportamiento legítimo tenga una latencia conocida. Si una expectativa nunca puede cumplirse por un localizador o regla incorrectos, esperar más solo demora el diagnóstico.

## Una assertion por propósito

Un caso puede necesitar varias expectations para definir su resultado, pero evitá verificar detalles decorativos que no aportan al objetivo. Cada assertion agrega un contrato que habrá que mantener.

## Why It Matters

Las actions hacen que algo ocurra; las assertions convierten ese recorrido en un test. Una expectativa bien elegida documenta el resultado y espera exactamente la señal que el sistema debe producir.

Cuando una suite es flaky, revisá si está leyendo valores instantáneos donde debería usar matchers web-first. La sincronización correcta suele estar en la assertion, no en una pausa previa.
