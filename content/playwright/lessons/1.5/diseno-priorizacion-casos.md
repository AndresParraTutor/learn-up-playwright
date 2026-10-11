---
objective: "1.5"
title: Diseño sistemático y priorización de casos
---

[Ver el resumen en video](/media/playwright/diseno-priorizacion-casos.mp4)

Probar todas las combinaciones es inviable salvo en problemas triviales. Las técnicas de diseño seleccionan un conjunto pequeño con capacidad razonable de revelar defectos. Automatizar sin esta selección solo acelera una cobertura arbitraria.

## Particiones de equivalencia

Dividí un conjunto de valores en grupos que deberían recibir el mismo tratamiento. Si una edad válida es de 18 a 120 inclusive, aparecen al menos tres particiones:

- menores de 18: inválida;
- entre 18 y 120: válida;
- mayores de 120: inválida.

Elegir un representante de cada partición reduce casos sin ignorar clases completas. Las particiones pueden aplicarse a entradas, salidas, configuraciones o estados.

## Análisis de valores límite

Los defectos se concentran cerca de fronteras. Para el rango 18–120, valores útiles son 17, 18, 19, 119, 120 y 121. La cantidad exacta depende del enfoque elegido, pero la idea es probar la frontera y sus vecinos, no solo un valor “normal”.

En Playwright, una tabla de datos puede expresar estos casos sin duplicar estructura:

```ts
const casos = [
  { edad: 17, permitido: false },
  { edad: 18, permitido: true },
  { edad: 120, permitido: true },
  { edad: 121, permitido: false },
];
```

## Tablas de decisión

Cuando el resultado depende de combinaciones de condiciones, una tabla hace visibles reglas faltantes o contradictorias.

| Usuario activo | Pago válido | Stock | Resultado |
| --- | --- | --- | --- |
| Sí | Sí | Sí | Compra confirmada |
| No | Sí | Sí | Solicitar acceso |
| Sí | No | Sí | Rechazar pago |
| Sí | Sí | No | Informar falta de stock |

No siempre hace falta ejecutar todas las combinaciones posibles. Primero identificá reglas distintas y luego elegí casos que las cubran.

## Transiciones de estado

Algunos defectos dependen de la secuencia, no solo de los datos. Una cuenta puede pasar por estados `activa`, `bloqueada` y `recuperación`. Diseñá casos para:

- transiciones válidas;
- intentos de transición inválidos;
- eventos repetidos;
- estado inicial y final;
- recuperación después de un fallo.

Un test que abre una página nueva para cada paso podría perder el historial necesario. El modelo de estados ayuda a decidir cuándo una secuencia debe permanecer dentro del mismo caso.

## Cobertura y riesgo

La cobertura mide qué elementos definidos fueron ejercitados: particiones, límites, reglas, estados, requisitos o riesgos. Cien por ciento de una métrica no significa ausencia de defectos; solo describe lo cubierto respecto de ese modelo.

Para priorizar, combiná de forma cualitativa:

- probabilidad de fallo;
- impacto para personas, negocio o cumplimiento;
- frecuencia de uso;
- historial de defectos;
- costo y velocidad de detección por otras capas.

Los casos de mayor riesgo deberían ejecutarse antes y con una señal clara. Un caso costoso y de bajo impacto puede quedar manual, ejecutarse con menor frecuencia o descartarse conscientemente.

## Why It Matters

Las técnicas de diseño convierten “probemos el formulario” en una estrategia defendible. También mejoran la automatización: los datos se vuelven explícitos, los títulos describen reglas y los fallos apuntan a una condición precisa.

El objetivo no es maximizar el número de tests. Es maximizar información útil por unidad de esfuerzo, manteniendo visible qué riesgo queda sin cubrir.
