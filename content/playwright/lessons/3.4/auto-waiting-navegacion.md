---
objective: "3.4"
title: Auto-waiting y navegación
---

[Ver el resumen en video](/media/playwright/auto-waiting-navegacion.mp4)

Playwright espera automáticamente condiciones relevantes antes de ejecutar acciones. Para un `click`, comprueba que el localizador resuelva un único elemento y que este sea visible, estable, habilitado y capaz de recibir eventos.

```ts
await page.getByRole('button', { name: 'Guardar' }).click();
```

La línea ya incluye una espera por accionabilidad. Agregar `waitForTimeout(2000)` antes del click suele hacer el test más lento sin volverlo correcto.

## Accionabilidad

Las verificaciones dependen de la acción:

- `click()` necesita visibilidad, estabilidad, recepción de eventos y habilitación;
- `fill()` necesita visibilidad, habilitación y edición;
- `check()` valida condiciones apropiadas para un control seleccionable;
- `screenshot()` necesita que el elemento sea visible y estable.

Si una condición no se cumple antes del timeout, la acción falla con un mensaje que permite investigar. Usar `force: true` desactiva controles no esenciales y debería reservarse para un comportamiento intencional que no pueda modelarse de otro modo.

## Assertions que reintentan

El auto-waiting de una acción no verifica la consecuencia posterior. Para estados que aparecen de manera eventual:

```ts
await expect(page.getByRole('status')).toHaveText('Guardado');
```

La assertion vuelve a consultar el localizador hasta que coincide o vence su timeout. Es preferible a leer el texto una vez y agregar una pausa fija.

## Navegación explícita

```ts
await page.goto('https://example.com');
```

`goto()` espera el evento de carga configurado. Eso no significa necesariamente que toda lógica asíncrona de negocio haya terminado. Esperá una señal específica de preparación, como un encabezado o control utilizable.

```ts
await page.goto('/panel');
await expect(page.getByRole('heading', { name: 'Panel' })).toBeVisible();
```

## Navegación provocada por una acción

Cuando un click cambia la URL, afirmá el destino:

```ts
await page.getByRole('link', { name: 'Configuración' }).click();
await expect(page).toHaveURL(/\/configuracion$/);
```

Si necesitás coordinar explícitamente un evento de navegación:

```ts
await Promise.all([
  page.waitForURL(/\/confirmacion$/),
  page.getByRole('button', { name: 'Confirmar' }).click(),
]);
```

Registrá la espera antes de la acción para no perder un evento rápido. No uses este patrón mecánicamente cuando una assertion posterior ya expresa mejor el resultado.

## Cuándo esperar explícitamente

Una espera explícita es válida cuando representa una señal real:

- URL esperada;
- respuesta de red específica;
- elemento que aparece o desaparece;
- popup, descarga o evento conocido.

Una pausa temporal fija solo dice “dormir”, no qué condición se necesita. Si el sistema tarda más, falla; si tarda menos, desperdicia tiempo.

## Diagnóstico

Ante un timeout:

1. leé qué condición no se cumplió;
2. comprobá que el localizador represente el elemento correcto;
3. observá si hay overlay, animación o estado deshabilitado;
4. revisá la señal de preparación del producto;
5. ajustá el timeout solo si el comportamiento legítimo necesita más tiempo.

## Why It Matters

La estabilidad no se obtiene aumentando pausas, sino esperando condiciones significativas. Auto-waiting y assertions web-first alinean el test con estados observables y reducen carreras.

Cuando sentís la tentación de usar `waitForTimeout`, escribí primero qué evento debería ocurrir. Esa frase suele apuntar a la espera o assertion correcta.
