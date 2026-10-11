---
objective: "4.3"
title: Validaciones de URL, errores y buenas prácticas
---

[Ver el resumen en video](/media/playwright/urls-errores-buenas-practicas.mp4)

Una URL puede ser parte del resultado esperado cuando representa navegación o identidad de una vista:

```ts
await expect(page).toHaveURL('/panel');
await expect(page).toHaveURL(/\/pedidos\/\d+$/);
```

`toHaveURL` reintenta y entiende la URL de la Page. Comparar `page.url()` con una assertion genérica captura solo un instante.

## Diseñar el resultado completo

Después de enviar un formulario, una sola señal puede ser insuficiente. Un caso de creación podría afirmar:

```ts
await expect(page).toHaveURL(/\/proyectos\/\d+$/);
await expect(page.getByRole('heading')).toHaveText('Proyecto creado');
await expect(page.getByRole('status')).toContainText('Guardado');
```

Las expectations se complementan: destino, contenido y confirmación. Evitá verificar cada detalle de layout, porque aumentaría acoplamiento sin mejorar la evidencia del objetivo.

## Errores esperados

Los errores de negocio también son resultados correctos para entradas inválidas:

```ts
await page.getByLabel('Correo').fill('sin-arroba');
await page.getByRole('button', { name: 'Continuar' }).click();

await expect(page.getByRole('alert')).toHaveText('Ingresá un correo válido');
await expect(page).toHaveURL(/\/registro$/);
```

El caso comprueba el mensaje y que la navegación incorrecta no ocurrió.

## No ocultar fallos

Este patrón destruye la señal:

```ts
try {
  await expect(status).toHaveText('Guardado');
} catch {
  // continuar como si el test hubiera pasado
}
```

Capturá un error solo si el caso lo espera o si vas a enriquecerlo y volver a lanzarlo. Un test que silencia una expectation no protege el producto.

## Distinguir timeouts

Playwright tiene límites diferentes:

- timeout total del test;
- timeout de una action;
- timeout de navegación;
- timeout de `expect`;
- timeout de hooks o fixtures.

Ante un mensaje de timeout, identificá cuál venció. Aumentar el timeout global puede no afectar la assertion que falla o puede hacer toda la suite más lenta.

## Buenas prácticas

- Una intención clara por caso.
- Arrange, Act, Assert visibles aunque no estén rotulados.
- Localizadores orientados a la persona.
- Assertions web-first sobre consecuencias.
- Datos controlados y aislamiento.
- Sin waits temporales arbitrarios.
- Mensajes y títulos que ayuden a diagnosticar.

Un caso completo y legible:

```ts
test('mantiene al usuario en registro si el correo es inválido', async ({ page }) => {
  await page.goto('/registro');
  await page.getByLabel('Correo').fill('incorrecto');
  await page.getByRole('button', { name: 'Crear cuenta' }).click();

  await expect(page.getByRole('alert')).toHaveText('Ingresá un correo válido');
  await expect(page).toHaveURL(/\/registro$/);
});
```

## Why It Matters

Una falla útil indica qué contrato se rompió y conserva evidencia suficiente para reproducirla. Assertions vagas, silenciosas o excesivamente internas generan mantenimiento sin orientar una corrección.

No trates el timeout como causa; es el síntoma de una condición que no se cumplió a tiempo. El diagnóstico comienza identificando esa condición y revisando si representa el comportamiento correcto.
