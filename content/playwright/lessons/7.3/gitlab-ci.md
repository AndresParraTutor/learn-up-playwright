---
objective: "7.3"
title: Pipeline introductorio con GitLab CI
---

[Ver el resumen en video](/media/playwright/gitlab-ci.mp4)

GitLab CI lee `.gitlab-ci.yml`. Para Playwright puede usarse una imagen oficial que ya incluye navegadores y dependencias del sistema. La versión de la imagen debe coincidir con el paquete npm del proyecto.

```yaml
stages:
  - test

playwright-tests:
  stage: test
  image: mcr.microsoft.com/playwright:v1.62.1-noble
  script:
    - npm ci
    - npx playwright test
  artifacts:
    when: always
    expire_in: 30 days
    paths:
      - playwright-report/
      - test-results/
```

## Lectura de la configuración

- `stages` define el orden de etapas.
- `stage: test` ubica el job.
- `image` proporciona un entorno conocido.
- `script` instala dependencias y ejecuta tests.
- `artifacts.when: always` conserva evidencia también ante fallos.
- `expire_in` limita retención.

La imagen no incluye los paquetes de tu proyecto; `npm ci` sigue siendo necesario. También debe existir `package-lock.json`.

## Coincidencia de versiones

Si `package.json` usa Playwright 1.62.1, la imagen `v1.62.1-noble` evita diferencias entre cliente y navegadores. Cuando actualices el paquete:

1. actualizá y probá localmente;
2. actualizá el lockfile;
3. alineá el tag de la imagen;
4. ejecutá el pipeline y revisá artefactos.

Usar `latest` reduce reproducibilidad y puede introducir cambios sin una modificación visible del repositorio.

## Variables y secretos

GitLab permite variables protegidas y enmascaradas. No deben aparecer en YAML, logs, screenshots ni trazas. Separá datos sintéticos de cualquier acceso sensible.

## Paralelismo introductorio

GitLab puede multiplicar jobs y Playwright puede usar sharding:

```yaml
parallel: 2
script:
  - npm ci
  - npx playwright test --shard=$CI_NODE_INDEX/$CI_NODE_TOTAL
```

Adoptalo después de lograr aislamiento y combinar correctamente reportes. Para un primer pipeline, un job estable es mejor punto de partida.

## Diferencias con GitHub Actions

Los nombres cambian —workflow frente a pipeline, steps frente a script, artifacts con sintaxis distinta— pero la secuencia técnica es la misma:

1. obtener código;
2. instalar de forma reproducible;
3. proveer navegadores compatibles;
4. ejecutar;
5. conservar evidencia.

## Why It Matters

La imagen versionada reduce diferencias entre agentes y hace explícito el entorno del navegador. Sin coincidencia de versiones, un fallo de infraestructura puede parecer un defecto del producto.

Un pipeline portable no copia YAML a ciegas: conserva las mismas invariantes —dependencias fijadas, navegador compatible, datos seguros y artefactos disponibles— dentro de la sintaxis del proveedor.
