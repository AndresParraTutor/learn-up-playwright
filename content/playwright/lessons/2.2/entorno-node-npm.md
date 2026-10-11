---
objective: "2.2"
title: Preparación del entorno con Node.js y npm
---

[Ver el resumen en video](/media/playwright/entorno-node-npm.mp4)

Un entorno reproducible permite que la misma suite funcione en una notebook y en CI. Para la instantánea documental usada por este curso, Playwright requiere una versión de Node.js admitida —22.x, 24.x o 26.x— y un sistema operativo compatible. Antes de instalar, verificá:

```powershell
node --version
npm --version
```

Si trabajás en otro momento, consultá los requisitos vigentes en la documentación oficial; los rangos cambian con las versiones.

## Inicializar un proyecto

En un directorio nuevo o existente:

```powershell
npm init playwright@latest
```

El asistente solicita decisiones como:

- TypeScript o JavaScript; elegiremos TypeScript;
- carpeta de tests, normalmente `tests`;
- workflow de GitHub Actions;
- instalación de navegadores.

Una estructura inicial típica es:

```text
playwright.config.ts
package.json
package-lock.json
tests/
  example.spec.ts
```

`package.json` declara dependencias y scripts. `package-lock.json` fija el grafo exacto que luego puede instalarse con `npm ci`. `playwright.config.ts` centraliza navegadores, timeouts, retries, reporter y opciones de uso.

## Instalar paquete y navegadores

Si agregás Playwright manualmente:

```powershell
npm install --save-dev @playwright/test@latest
npx playwright install
```

En Linux o CI suele usarse:

```bash
npx playwright install --with-deps
```

El paquete npm y los binarios de navegador son piezas diferentes. Actualizar solo `@playwright/test` puede dejar binarios incompatibles. Después de una actualización:

```powershell
npm install --save-dev @playwright/test@latest
npx playwright install --with-deps
```

## Leer la configuración inicial

Un archivo mínimo puede verse así:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  reporter: 'html',
  use: {
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

No hace falta memorizar todas las opciones. Primero identificá:

- dónde busca tests;
- en qué proyectos los ejecuta;
- qué opciones se aplican a cada contexto;
- qué evidencia se conserva.

## Verificar la instalación

```powershell
npx playwright --version
npx playwright test
npx playwright show-report
```

El primer comando informa la versión. El segundo descubre y ejecuta tests. El tercero abre el último reporte HTML disponible.

## Problemas frecuentes

- `node` no se reconoce: Node.js no está instalado o no está en `PATH`.
- falta un ejecutable de navegador: ejecutá `npx playwright install` con la misma versión del paquete.
- el proyecto funciona localmente pero no en CI: verificá `package-lock.json`, `npm ci` y dependencias del sistema.
- comandos ejecutados desde una carpeta incorrecta: ubicáte donde están `package.json` y `playwright.config.ts`.

## Why It Matters

La reproducibilidad empieza antes del primer test. Versiones, lockfile, binarios y configuración son parte de la suite; si quedan implícitos, el entorno se vuelve una variable oculta.

Cuando una ejecución falla solo en otra máquina, compará primero versiones y pasos de instalación. Esa evidencia suele ser más útil que agregar esperas al código de prueba.
