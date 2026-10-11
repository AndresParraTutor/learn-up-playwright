---
objective: "5.1"
title: Organización modular y reutilización
---

[Ver el resumen en video](/media/playwright/organizacion-modular-reutilizacion.mp4)

Una suite mantenible hace visible dónde vive cada responsabilidad. La organización no consiste en crear muchas carpetas, sino en permitir que una persona encuentre el comportamiento, entienda su preparación y cambie una abstracción sin romper casos no relacionados.

## Una estructura inicial

```text
playwright.config.ts
tests/
  auth/
    login.spec.ts
  checkout/
    compra.spec.ts
  fixtures/
    test.ts
  pages/
    checkout-page.ts
  data/
    usuarios.ts
```

- Los archivos `.spec.ts` contienen escenarios y expectations.
- `pages/` encapsula interacción estable cuando POM aporta valor.
- `fixtures/` administra preparación y limpieza reutilizable.
- `data/` contiene datos no sensibles y explícitos.
- La configuración conserva decisiones transversales.

No adoptes una estructura compleja antes de necesitarla. Empezá por comportamiento y extraé cuando aparezca una repetición con significado común.

## Agrupar con `describe`

```ts
test.describe('recuperación de contraseña', () => {
  test('envía instrucciones para una cuenta registrada', async ({ page }) => {
    // ...
  });

  test('muestra el mismo mensaje para una cuenta desconocida', async ({ page }) => {
    // ...
  });
});
```

`describe` organiza reportes y permite configuración local. No debería esconder una dependencia de orden entre tests.

## Hooks

```ts
test.beforeEach(async ({ page }) => {
  await page.goto('/login');
});
```

`beforeEach` se ejecuta para cada caso y conserva aislamiento. `beforeAll` se ejecuta una vez por worker y es adecuado para preparación costosa que no comparte estado mutable de la página. Si un hook crece demasiado, los tests dejan de revelar sus precondiciones.

Hooks disponibles:

- `beforeEach` y `afterEach` alrededor de cada test;
- `beforeAll` y `afterAll` alrededor de un grupo por worker.

La limpieza debe tolerar fallos parciales. Un `afterEach` no debería asumir que todos los pasos previos terminaron correctamente.

## Funciones auxiliares

Una función es útil si encapsula una operación con nombre de dominio:

```ts
async function crearProyecto(page: Page, nombre: string) {
  await page.getByRole('link', { name: 'Nuevo proyecto' }).click();
  await page.getByLabel('Nombre').fill(nombre);
  await page.getByRole('button', { name: 'Crear' }).click();
}
```

Evitá helpers genéricos que oculten Playwright:

```ts
// Difícil de leer y diagnosticar.
await doAction('button', 'click', 3, true);
```

La reutilización debe aumentar claridad. Duplicar dos líneas puede ser mejor que introducir una abstracción sin significado.

## Configuración frente a código

Opciones globales —base URL, reporter, proyectos, trace— pertenecen a `playwright.config.ts`. Datos específicos de un caso pertenecen al test o a fixtures. Mezclarlos produce configuración difícil de razonar.

```ts
export default defineConfig({
  testDir: './tests',
  use: { baseURL: 'http://127.0.0.1:4173' },
});
```

Luego:

```ts
await page.goto('/login');
```

## Why It Matters

El costo de una suite aparece durante el cambio. Una organización clara reduce el radio de impacto y permite que un fallo apunte a una capa comprensible.

Extraé comportamiento repetido, no sintaxis repetida. Si el nombre de una abstracción no explica mejor el dominio que las líneas que reemplaza, todavía no aporta suficiente valor.
