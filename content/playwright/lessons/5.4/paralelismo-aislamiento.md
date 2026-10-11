---
objective: "5.4"
title: Ejecución paralela y aislamiento
---

[Ver el resumen en video](/media/playwright/paralelismo-aislamiento.mp4)

Playwright Test usa procesos worker para ejecutar archivos en paralelo. Cada worker tiene su propio entorno y el runner administra contextos aislados por test. La velocidad aparece cuando los casos pueden ejecutarse en cualquier orden sin interferirse.

## Comportamiento predeterminado

- Los archivos de test pueden ejecutarse en paralelo.
- Los tests dentro de un mismo archivo se ejecutan en orden por defecto.
- Distintos workers no comparten memoria del proceso.
- Cada test recibe un BrowserContext limpio mediante fixtures integradas.

La configuración controla el número de workers:

```ts
export default defineConfig({
  workers: process.env.CI ? 1 : undefined,
});
```

Usar un worker en CI puede priorizar estabilidad cuando los recursos son limitados. Un entorno potente puede aumentar workers después de comprobar aislamiento.

## Paralelismo dentro de un archivo

```ts
test.describe.configure({ mode: 'parallel' });
```

Esto permite que tests del grupo corran en workers distintos. Solo es seguro si no dependen de variables compartidas, orden ni entidades con el mismo identificador.

## Datos únicos

Un patrón simple usa `workerIndex`:

```ts
test('crea un proyecto', async ({ page }, testInfo) => {
  const nombre = `proyecto-worker-${testInfo.workerIndex}`;
  // crear y verificar
});
```

Si hay retries o varios tests en el mismo worker, agregá también una identidad por test o intento. La estrategia debe ajustarse al backend y su limpieza.

## Dependencias peligrosas

Este diseño es frágil:

```ts
test('crea usuario', async () => { /* ... */ });
test('edita el usuario creado por el test anterior', async () => { /* ... */ });
```

El segundo caso no puede ejecutarse solo y el primer fallo bloquea su propósito. Cada test debería preparar su propio usuario o consumir una fixture independiente.

## Modo serial

Playwright permite grupos seriales, pero deben ser excepcionales. En modo serial, un fallo puede omitir los tests siguientes y el grupo se reintenta como unidad.

Un flujo de varios pasos que deba conservar estado puede modelarse mejor como un solo test con `test.step`, siempre que represente un único objetivo. Dividirlo en tests dependientes solo para obtener más líneas en el reporte no mejora aislamiento.

## Fallos y workers

Después de un fallo, Playwright puede descartar el worker y comenzar otro limpio para los casos siguientes. Esto reduce contaminación, pero no corrige datos persistentes dejados en una base externa. El teardown y la unicidad siguen siendo responsabilidad de la suite.

## Estrategia de adopción

1. Hacé que cada test pase solo y en cualquier orden.
2. Ejecutá repetidamente con varios workers.
3. Buscá colisiones de datos y puertos.
4. Medí duración y recursos.
5. Ajustá workers y sharding según la infraestructura.

## Why It Matters

El paralelismo amplifica tanto el buen aislamiento como los defectos de diseño. Si duplicar workers vuelve flaky la suite, el problema no es necesariamente la velocidad: suele revelar estado compartido.

La unidad básica de confianza es un test que puede ejecutarse solo. Esa propiedad habilita filtrado, retries, paralelismo y diagnóstico sin depender de una secuencia oculta.
