---
objective: "3.1"
title: Selectores y localizadores resilientes
---

[Ver el resumen en video](/media/playwright/localizadores-resilientes.mp4)

Un localizador describe cómo encontrar un elemento en el momento de usarlo. No guarda un nodo viejo: vuelve a resolver el elemento antes de cada acción. Esto permite tolerar re-renderizados cuando la identidad perceptible del control se mantiene.

## Priorizar la interfaz observable

Playwright recomienda atributos visibles para la persona o contratos explícitos:

```ts
page.getByRole('button', { name: 'Guardar' });
page.getByLabel('Correo electrónico');
page.getByText('Operación completada');
page.getByPlaceholder('nombre@empresa.com');
page.getByAltText('Logo de la empresa');
page.getByTestId('resultado-total');
```

`getByRole` suele ser la primera opción porque combina semántica y nombre accesible. Un botón con texto visible puede localizarse así:

```ts
await page.getByRole('button', { name: 'Ingresar' }).click();
```

El localizador documenta intención mejor que `.btn.primary:nth-child(3)` y también incentiva una interfaz accesible.

## Texto, label y test id

- `getByText` es apropiado para contenido visible, especialmente mensajes y texto estático.
- `getByLabel` conecta un control con su etiqueta accesible y es ideal para formularios.
- `getByTestId` establece un contrato técnico cuando no hay una señal semántica estable.

Un test id no es un fracaso: puede ser la opción más estable para contenido sin semántica adecuada. Debe tratarse como parte del contrato del producto, no como un selector accidental.

## CSS con moderación

`page.locator()` acepta CSS:

```ts
page.locator('button[type="submit"]');
```

CSS es útil cuando la estructura o un atributo forman parte de un contrato conocido. Se vuelve frágil cuando depende de detalles de implementación:

```ts
page.locator('#app > div:nth-child(2) > section > button.primary');
```

Un cambio de layout puede romperlo aunque la persona siga viendo el mismo botón. XPath y cadenas CSS profundas tienen el mismo problema.

## Strictness

Una acción que requiere un elemento falla si el localizador coincide con varios. Esa strictness evita hacer clic silenciosamente en un control arbitrario.

```ts
await page.getByRole('button', { name: 'Eliminar' }).click();
```

Si hay varios botones “Eliminar”, agregá contexto:

```ts
const fila = page.getByRole('row').filter({ hasText: 'Proyecto Alfa' });
await fila.getByRole('button', { name: 'Eliminar' }).click();
```

Usar `.first()` para apagar la ambigüedad puede ocultar un problema. Preferí describir cuál elemento corresponde al caso.

## Encadenar y filtrar

Los localizadores se refinan desde un contenedor:

```ts
const tarjeta = page
  .getByRole('listitem')
  .filter({ hasText: 'Plan profesional' });

await tarjeta.getByRole('button', { name: 'Elegir' }).click();
await expect(tarjeta).toContainText('Seleccionado');
```

La misma referencia conceptual puede usarse para actuar y verificar, manteniendo el contexto del caso.

## Diagnosticar un localizador

Cuando falla, preguntá:

1. ¿la semántica o el nombre accesible son los esperados?;
2. ¿coincide con cero o con varios elementos?;
3. ¿está dentro de un iframe o contenedor específico?;
4. ¿el elemento representa intención de usuario o un detalle interno?;
5. ¿un cambio válido de texto requiere una expresión regular o contrato distinto?

## Why It Matters

La mayoría de los tests UI interactúa a través de localizadores; su calidad determina mantenimiento y señal. Un localizador resiliente falla cuando cambia el comportamiento relevante, no cuando alguien reorganiza un `div`.

Pensá el localizador como una afirmación sobre la interfaz: “existe un botón accesible llamado Guardar dentro de esta fila”. Esa frase debería seguir siendo cierta aunque cambie la implementación visual.
