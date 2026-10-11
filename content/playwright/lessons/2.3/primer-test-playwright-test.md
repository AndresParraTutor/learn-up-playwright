---
objective: "2.3"
title: Primer test y Playwright Test
---

[Ver el resumen en video](/media/playwright/primer-test-playwright-test.mp4)

Un test Playwright básico combina tres ideas: preparar el contexto, actuar sobre el sistema y verificar un resultado observable. Playwright Test aporta `test`, la fixture `page` y `expect`.

```ts
import { test, expect } from '@playwright/test';

test('la página muestra su encabezado', async ({ page }) => {
  await page.setContent(`
    <main>
      <h1>Panel de calidad</h1>
      <a href="/reportes">Ver reportes</a>
    </main>
  `);

  await expect(
    page.getByRole('heading', { name: 'Panel de calidad' }),
  ).toBeVisible();
});
```

El ejemplo usa `page.setContent()` para ser autocontenido. Un test real suele comenzar con `page.goto()` hacia la aplicación bajo prueba.

## Anatomía

- `test('nombre', función)` registra un caso con título legible.
- `async ({ page })` recibe la página aislada preparada por el runner.
- `await` espera cada operación asíncrona.
- `getByRole()` expresa cómo una persona o tecnología asistiva percibe el elemento.
- `expect(...).toBeVisible()` compara el estado con una expectativa web-first.

El título debería comunicar comportamiento y resultado, no detalles vagos como “test 1”. Cuando falla, ese texto aparece en consola y reportes.

## Ejecutar desde consola

Todos los tests:

```powershell
npx playwright test
```

Un archivo:

```powershell
npx playwright test tests/panel.spec.ts
```

Un navegador configurado:

```powershell
npx playwright test --project=chromium
```

Con ventana visible:

```powershell
npx playwright test --headed
```

Modo interactivo:

```powershell
npx playwright test --ui
```

## Interpretar la salida

La consola informa cuántos tests descubrió, cuántos workers utiliza y el estado de cada ejecución. Los resultados típicos son:

- `passed`: cumplió la expectativa;
- `failed`: terminó con una assertion o error no resuelto;
- `skipped`: fue omitido por una condición o anotación;
- `flaky`: falló inicialmente y pasó en un reintento;
- `timed out`: superó un límite configurado.

Un fallo contiene ubicación, mensaje, valor esperado y observado cuando corresponde. Leé primero la assertion y el call log antes de cambiar el código.

## Un flujo completo

```ts
import { test, expect } from '@playwright/test';

test('permite activar notificaciones', async ({ page }) => {
  await page.setContent(`
    <label><input type="checkbox"> Recibir notificaciones</label>
    <p role="status">Desactivadas</p>
    <script>
      const box = document.querySelector('input');
      const status = document.querySelector('[role=status]');
      box.addEventListener('change', () => {
        status.textContent = box.checked ? 'Activadas' : 'Desactivadas';
      });
    </script>
  `);

  await page.getByRole('checkbox', { name: 'Recibir notificaciones' }).check();
  await expect(page.getByRole('status')).toHaveText('Activadas');
});
```

Este caso tiene una acción y una consecuencia explícita. No necesita `waitForTimeout`: la acción espera que el checkbox sea accionable y la assertion reintenta hasta ver el texto o agotar su timeout.

## Why It Matters

El primer objetivo no es dominar toda la API, sino construir un ciclo confiable: ejecutar, leer la salida, entender la evidencia y repetir. Si no podés explicar qué prepara, hace y verifica el test, agregará ruido aunque pase.

Preferí ejemplos autocontenidos mientras aprendés una API. Luego reemplazá el HTML local por un sistema real sin perder claridad sobre precondiciones y resultados esperados.
