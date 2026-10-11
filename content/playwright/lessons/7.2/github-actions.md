---
objective: "7.2"
title: Pipeline introductorio con GitHub Actions
---

[Ver el resumen en video](/media/playwright/github-actions.mp4)

GitHub Actions define workflows YAML bajo `.github/workflows/`. Un pipeline introductorio ejecuta Playwright en pushes y pull requests, y publica el reporte incluso cuando hay fallos.

```yaml
name: Playwright Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    timeout-minutes: 60
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-node@v6
        with:
          node-version: lts/*
          cache: npm

      - name: Instalar dependencias
        run: npm ci

      - name: Instalar navegadores
        run: npx playwright install --with-deps

      - name: Ejecutar tests
        run: npx playwright test

      - name: Publicar reporte
        if: ${{ !cancelled() }}
        uses: actions/upload-artifact@v5
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

## Lectura del workflow

- `on` define eventos y ramas.
- `jobs.test` agrupa el trabajo de pruebas.
- `runs-on` elige el agente.
- `checkout` obtiene el repositorio.
- `setup-node` prepara Node y puede cachear descargas npm.
- `npm ci` respeta el lockfile.
- `playwright install --with-deps` instala navegadores y bibliotecas del sistema.
- `playwright test` ejecuta la suite.
- `upload-artifact` conserva el reporte.

## Publicar aun cuando hay fallos

`if: ${{ !cancelled() }}` permite subir el reporte si la ejecución terminó con tests fallidos, pero evita hacerlo si el workflow fue cancelado. Sin esa condición, un paso anterior fallido puede impedir acceder a la evidencia que explica el problema.

## Versiones y seguridad

Las versiones de actions cambian con el tiempo; este curso refleja las vigentes en la fuente versionada. Revisá notas oficiales al actualizar.

No imprimas secrets en logs ni los guardes en archivos. GitHub Actions puede inyectarlos mediante `secrets`, pero una suite de aprendizaje debería preferir datos sintéticos y un entorno local o efímero.

Los workflows de pull requests provenientes de forks requieren cuidado adicional: no expongas credenciales a código no confiable.

## Artefactos

El reporte HTML puede contener trazas, capturas y datos de prueba. Configurá:

- nombre inequívoco;
- ruta existente;
- retención limitada;
- acceso acorde a la sensibilidad.

## Diagnóstico básico

Si el job falla antes de los tests:

1. revisá versión de Node y lockfile;
2. comprobá instalación de navegadores;
3. verificá directorio de trabajo;
4. compará comandos con la ejecución local limpia.

Si fallan tests, descargá el reporte y la traza antes de modificar timeouts.

## Why It Matters

Un workflow explícito convierte los pasos locales en un contrato reproducible. Cada pull request recibe la misma secuencia y conserva evidencia para revisión.

La calidad del pipeline se mide tanto por detectar un problema como por permitir diagnosticarlo. Por eso la publicación condicional del reporte es parte funcional del diseño, no decoración.
