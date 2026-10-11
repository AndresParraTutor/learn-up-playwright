---
objective: "3.2"
title: Acciones con controles de formulario
---

[Ver el resumen en video](/media/playwright/acciones-controles-formulario.mp4)

Playwright ofrece acciones de alto nivel que reproducen comportamientos significativos sobre controles HTML. Elegir la acción específica produce eventos más realistas y mensajes de error más claros que manipular el DOM directamente.

## Click y entrada de texto

```ts
await page.getByRole('button', { name: 'Continuar' }).click();
await page.getByLabel('Nombre').fill('Ada Lovelace');
```

`fill()` establece el valor de un `input`, `textarea` o elemento editable y dispara el evento de entrada correspondiente. Para interfaces que reaccionan a cada tecla, puede usarse `pressSequentially()`, pero no debería ser la opción predeterminada.

```ts
await page.getByLabel('Buscador').pressSequentially('playwright', {
  delay: 40,
});
```

No agregues delay para “estabilizar” un test sin entender la necesidad. Solo modelalo si el comportamiento depende de la secuencia de teclas.

## Select, checkbox y radio

```ts
await page.getByLabel('País').selectOption('AR');
await page.getByRole('checkbox', { name: 'Acepto los términos' }).check();
await page.getByRole('radio', { name: 'Entrega express' }).check();
```

`selectOption()` puede elegir por `value`, label o índice. `check()` y `uncheck()` son preferibles a hacer clic ciegamente porque expresan el estado buscado y evitan invertir accidentalmente un checkbox que ya estaba marcado.

Después de actuar, verificá la consecuencia relevante:

```ts
await expect(page.getByLabel('País')).toHaveValue('AR');
await expect(page.getByRole('checkbox', { name: 'Acepto los términos' })).toBeChecked();
```

## Teclado y foco

```ts
await page.getByLabel('Buscar').press('Enter');
await page.getByRole('button', { name: 'Cancelar' }).focus();
await expect(page.getByRole('button', { name: 'Cancelar' })).toBeFocused();
```

Las acciones de teclado son valiosas para accesibilidad y atajos. Usalas cuando el modo de interacción sea parte del comportamiento, no como sustituto innecesario de una acción semántica.

## Un formulario autocontenido

```ts
import { test, expect } from '@playwright/test';

test('completa preferencias', async ({ page }) => {
  await page.setContent(`
    <form>
      <label>Nombre <input name="nombre"></label>
      <label>País
        <select name="pais">
          <option value="AR">Argentina</option>
          <option value="UY">Uruguay</option>
        </select>
      </label>
      <label><input type="checkbox" name="news"> Novedades</label>
      <button>Guardar</button>
      <output></output>
    </form>
    <script>
      document.querySelector('form').addEventListener('submit', event => {
        event.preventDefault();
        document.querySelector('output').textContent = 'Preferencias guardadas';
      });
    </script>
  `);

  await page.getByLabel('Nombre').fill('Lucía');
  await page.getByLabel('País').selectOption('AR');
  await page.getByRole('checkbox', { name: 'Novedades' }).check();
  await page.getByRole('button', { name: 'Guardar' }).click();
  await expect(page.getByText('Preferencias guardadas')).toBeVisible();
});
```

## Acción no es validación

Que `click()` no arroje error significa que pudo ejecutar la acción bajo sus condiciones, no que el negocio produjo el resultado correcto. Cada caso necesita una assertion sobre la consecuencia.

También evitá acciones forzadas como primera respuesta. `force: true` saltea verificaciones importantes y puede hacer que el test realice algo que una persona no podría.

## Why It Matters

Las acciones específicas comunican intención y aprovechan la accionabilidad de Playwright. Un test mantenible se lee como comportamiento: completar, elegir, aceptar y guardar; no como una secuencia de coordenadas y nodos internos.

El resultado esperado cierra el ciclo. Sin una assertion posterior, el script demuestra movimiento, no corrección.
