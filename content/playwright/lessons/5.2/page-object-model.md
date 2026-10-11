---
objective: "5.2"
title: Page Object Model
---

[Ver el resumen en video](/media/playwright/page-object-model.mp4)

Page Object Model encapsula una parte de la interfaz detrás de una API orientada al dominio. Un page object conserva una `Page`, localizadores relevantes y operaciones que una persona realiza en esa vista.

## Un modelo simple

```ts
import { type Locator, type Page } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly correo: Locator;
  readonly contrasena: Locator;
  readonly ingresar: Locator;

  constructor(page: Page) {
    this.page = page;
    this.correo = page.getByLabel('Correo');
    this.contrasena = page.getByLabel('Contraseña');
    this.ingresar = page.getByRole('button', { name: 'Ingresar' });
  }

  async goto() {
    await this.page.goto('/login');
  }

  async iniciarSesion(correo: string, contrasena: string) {
    await this.correo.fill(correo);
    await this.contrasena.fill(contrasena);
    await this.ingresar.click();
  }
}
```

El test se concentra en el escenario:

```ts
test('rechaza credenciales inválidas', async ({ page }) => {
  const login = new LoginPage(page);
  await login.goto();
  await login.iniciarSesion('ana@example.test', 'incorrecta');

  await expect(page.getByRole('alert')).toHaveText('Credenciales inválidas');
});
```

## Responsabilidades

Un page object suele:

- encapsular localizadores de una región o página;
- ofrecer métodos de interacción con nombres del dominio;
- centralizar navegación propia de esa vista;
- ocultar detalles de DOM que no interesan al test.

No debería:

- compartir una Page global entre workers;
- contener datos sensibles;
- realizar decenas de assertions invisibles en cada método;
- convertirse en una clase gigantesca que representa toda la aplicación.

## ¿Dónde van las assertions?

Mantenerlas en el test hace explícito el resultado del caso. Un page object puede exponer localizadores o métodos de consulta:

```ts
readonly alerta = this.page.getByRole('alert');
```

Entonces el test afirma:

```ts
await expect(login.alerta).toHaveText('Credenciales inválidas');
```

Una assertion puede vivir dentro del modelo si representa una operación indivisible y el equipo lo acuerda, pero ocultar expectativas dificulta saber qué verifica cada test.

## Page component objects

No toda abstracción representa una página completa. Un header, modal o tabla reutilizable puede tener su propio objeto basado en un Locator raíz.

```ts
class ModalConfirmacion {
  constructor(private readonly root: Locator) {}

  async confirmar() {
    await this.root.getByRole('button', { name: 'Confirmar' }).click();
  }
}
```

## Cuándo no usar POM

Para dos tests pequeños, una clase agrega navegación mental sin reducir mantenimiento. POM aporta cuando una interfaz estable aparece en varios casos y necesita una API compartida.

Señales de un mal POM:

- métodos como `clickButton1` sin intención de negocio;
- herencia profunda entre páginas no relacionadas;
- selectores públicos que cualquier test modifica;
- una instancia compartida con estado mutable.

## Why It Matters

POM concentra el conocimiento de interacción y puede reducir el costo de cambios de interfaz. Su valor no es “tener clases”, sino ofrecer al test un vocabulario cercano al comportamiento.

Si un método se llama `completarCompra`, el test debería poder confiar en esa operación sin conocer cada `div`. Al mismo tiempo, las expectativas del escenario deben seguir visibles para conservar una señal diagnóstica.
