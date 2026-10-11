---
objective: "4.2"
title: Validaciones de texto, atributos y estados
---

[Ver el resumen en video](/media/playwright/validaciones-texto-atributos-estados.mp4)

Las assertions sobre Locator verifican lo que la interfaz presenta y cómo puede usarse. Elegí la señal más cercana al comportamiento que querés demostrar.

## Texto

```ts
await expect(page.getByRole('status')).toHaveText('Guardado');
await expect(page.getByRole('alert')).toContainText('correo inválido');
```

`toHaveText` busca la coincidencia completa normalizada; `toContainText` permite que el contenido tenga texto adicional. También aceptan expresiones regulares cuando la variación está prevista:

```ts
await expect(page.getByRole('status')).toHaveText(/Guardado a las \d{2}:\d{2}/);
```

No conviertas en regex todo texto para hacer pasar el test. La flexibilidad debe corresponder a una variación válida.

## Atributos y valores

```ts
await expect(link).toHaveAttribute('href', '/cuenta');
await expect(campo).toHaveValue('ana@example.test');
await expect(imagen).toHaveAttribute('alt', 'Equipo de soporte');
```

Un atributo es adecuado cuando forma parte del contrato observable: destino de un enlace, descripción accesible o estado definido. Las clases CSS internas rara vez son la mejor evidencia funcional.

## Visibilidad

```ts
await expect(mensaje).toBeVisible();
await expect(spinner).toBeHidden();
```

Visible no significa solo presente en el DOM. Playwright considera caja y estilos relevantes. Un elemento con `display: none` no es visible; uno con `opacity: 0` puede considerarse visible según la definición de accionabilidad, por lo que conviene afirmar el comportamiento que realmente importa.

## Habilitación y edición

```ts
await expect(botonEnviar).toBeEnabled();
await expect(campoSoloLectura).not.toBeEditable();
await expect(control).toBeDisabled();
```

Estas expectations son más claras que inspeccionar manualmente atributos si la pregunta es si una persona puede interactuar.

## Selección

```ts
await expect(page.getByRole('checkbox', { name: 'Novedades' })).toBeChecked();
await expect(page.getByLabel('País')).toHaveValue('AR');
```

En un `select` múltiple puede usarse `toHaveValues`.

## Cantidad y colecciones

```ts
const filas = page.getByRole('row');
await expect(filas).toHaveCount(4);
```

Para listas, `toHaveText` puede recibir un arreglo y comprobar orden y contenido:

```ts
await expect(page.getByRole('listitem')).toHaveText([
  'Pendiente',
  'En curso',
  'Finalizado',
]);
```

## Evitar assertions de implementación

Compará estas opciones:

```ts
await expect(boton).toHaveClass(/is-active/);
await expect(boton).toHaveAttribute('aria-pressed', 'true');
```

Si el comportamiento es un botón de alternancia accesible, `aria-pressed` representa mejor el contrato. La clase podría cambiar con un rediseño sin alterar la función.

## Why It Matters

Una assertion es una decisión sobre qué parte de la interfaz constituye evidencia. Elegir texto, estado o atributo semántico reduce falsos fallos y hace que el reporte explique el contrato roto.

Preguntá siempre: si esta assertion falla, ¿significa que la persona perdió el comportamiento que estamos probando? Si la respuesta es “no necesariamente”, buscá una señal más cercana al objetivo.
