---
objective: "3.3"
title: Carga de archivos y flujos completos
---

[Ver el resumen en video](/media/playwright/uploads-y-flujos-completos.mp4)

Un flujo completo conecta varias interacciones alrededor de un objetivo observable. No significa que deba abarcar toda la aplicación: un buen caso tiene un propósito, precondiciones controladas y una frontera clara.

## Login como preparación o comportamiento

Si el objetivo es verificar el login, atravesá la interfaz y afirmá su resultado:

```ts
test('rechaza una contraseña inválida', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo').fill('ana@example.test');
  await page.getByLabel('Contraseña').fill('incorrecta');
  await page.getByRole('button', { name: 'Ingresar' }).click();

  await expect(page.getByRole('alert')).toHaveText('Credenciales inválidas');
  await expect(page).toHaveURL(/\/login$/);
});
```

Si el login es solo una precondición para veinte tests distintos, repetirlo por UI agrega tiempo y puntos de fallo. Más adelante puede prepararse un estado autenticado controlado, sin quitar los casos específicos que prueban el login.

Nunca almacenes credenciales reales en el repositorio. Usá cuentas de prueba, variables de entorno documentadas o estados generados por el entorno de testing.

## Carga de archivos

Para un `input[type=file]`:

```ts
await page.getByLabel('Adjuntar comprobante').setInputFiles(
  'tests/fixtures/comprobante.pdf',
);
```

También puede cargarse un archivo en memoria:

```ts
await page.getByLabel('Adjuntar texto').setInputFiles({
  name: 'nota.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from('evidencia de prueba'),
});
```

El archivo en memoria hace el ejemplo autocontenido y evita depender de una ruta externa. Después, verificá la consecuencia de negocio: nombre listado, vista previa, estado de carga o mensaje de error.

## Formularios y mensajes

Un caso completo suele tener:

1. datos explícitos;
2. acciones que una persona realizaría;
3. envío;
4. assertion de resultado;
5. assertion negativa cuando evita una transición incorrecta.

```ts
await page.getByLabel('Nombre').fill('María');
await page.getByLabel('Plan').selectOption('pro');
await page.getByRole('checkbox', { name: 'Acepto condiciones' }).check();
await page.getByRole('button', { name: 'Crear cuenta' }).click();

await expect(page.getByRole('status')).toHaveText('Cuenta creada');
await expect(page).toHaveURL(/\/bienvenida$/);
```

## Evitar flujos gigantes

Un solo test que registra, compra, edita perfil, cancela y vuelve a comprar es difícil de diagnosticar. Si falla en el primer paso, nunca evalúa los demás. Separá objetivos cuando puedan tener precondiciones independientes.

Un flujo largo se justifica cuando la secuencia completa es el comportamiento bajo prueba, por ejemplo conservar un carrito a través de una autenticación. Incluso entonces, usá pasos claros y evidencia intermedia útil.

## Datos y limpieza

Los datos deben ser:

- únicos cuando los tests corren en paralelo;
- repetibles cuando el escenario se reintenta;
- descartables y sin información sensible;
- creados y limpiados por mecanismos conocidos.

Evitar estado compartido reduce la dependencia del orden. Un test no debería necesitar que otro se ejecute primero.

## Why It Matters

Los flujos completos aportan confianza cuando conectan acciones con una consecuencia de negocio. Su valor cae rápidamente si esconden precondiciones, credenciales o datos compartidos.

Diseñá cada flujo para que un fallo explique qué objetivo se perdió. La longitud no es una medida de realismo: el control de estado y la claridad del resultado lo son.
