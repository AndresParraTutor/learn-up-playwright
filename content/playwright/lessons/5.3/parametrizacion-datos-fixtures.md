---
objective: "5.3"
title: Parametrización y datos de prueba
---

[Ver el resumen en video](/media/playwright/parametrizacion-datos-fixtures.mp4)

Parametrizar permite aplicar la misma estructura a datos que representan reglas distintas. No consiste en multiplicar casos sin criterio: los datos deberían provenir de técnicas de diseño y cada fila debe tener un propósito reconocible.

## Tests parametrizados

```ts
const casos = [
  { edad: 17, permitido: false, motivo: 'inferior al límite' },
  { edad: 18, permitido: true, motivo: 'límite mínimo' },
  { edad: 120, permitido: true, motivo: 'límite máximo' },
  { edad: 121, permitido: false, motivo: 'superior al límite' },
];

for (const caso of casos) {
  test(`edad ${caso.edad}: ${caso.motivo}`, async ({ page }) => {
    // preparar formulario, ingresar edad y verificar caso.permitido
  });
}
```

Los títulos son únicos y explican el dato. Si una fila falla, el reporte identifica la regla.

No generes casos dentro de un test en un loop si querés resultados independientes: el runner vería un solo test y el primer fallo impediría evaluar las filas restantes.

## Datos de prueba

Separá datos no sensibles del flujo cuando mejore claridad:

```ts
export const usuarioValido = {
  nombre: 'Ana Prueba',
  correo: 'ana@example.test',
};
```

No guardes contraseñas reales. Si el entorno requiere secretos, referenciá variables de entorno y documentá su propósito sin registrar valores.

Los datos para paralelismo deben evitar colisiones. Un identificador puede incorporar el índice del worker o un sufijo único controlado.

## Fixtures personalizadas

Una fixture prepara una capacidad y la entrega al test:

```ts
import { test as base } from '@playwright/test';

type Fixtures = {
  nombreProyecto: string;
};

export const test = base.extend<Fixtures>({
  nombreProyecto: async ({}, use, testInfo) => {
    const nombre = `proyecto-${testInfo.workerIndex}-${testInfo.retry}`;
    await use(nombre);
    // limpieza tolerante a que el test haya fallado
  },
});
```

La función ejecuta preparación antes de `use()` y teardown después. El test declara solo las fixtures que necesita.

## Alcance

- Una fixture de test se prepara para cada caso.
- Una fixture de worker se comparte entre tests del mismo worker y debe manejar con cuidado el estado mutable.

Elegí el alcance mínimo que conserve eficiencia. Compartir datos mutables por worker puede causar dependencia y carreras.

## Setup y teardown

El teardown debe ser idempotente cuando sea posible: ejecutarlo dos veces o después de una preparación parcial no debería empeorar el estado.

```ts
try {
  await borrarProyectoSiExiste(nombre);
} catch (error) {
  // registrar y volver a lanzar si la limpieza fallida compromete el entorno
  throw error;
}
```

No ocultes fallos importantes de limpieza; pueden contaminar casos posteriores.

## Why It Matters

Los datos transforman una técnica de diseño en ejecuciones concretas. Parametrización y fixtures permiten escalar esa intención sin duplicar scripts ni compartir estado accidentalmente.

Cuando un test parametrizado falla, debería revelar la regla y el dato que la ejercitaron. Cuando una fixture falla, debería revelar qué capacidad no pudo preparar o limpiar.
