---
objective: "1.2"
title: Niveles, tipos y alcance de las pruebas
---

[Ver el resumen en video](/media/playwright/niveles-tipos-alcance-pruebas.mp4)

Las etiquetas de testing describen dimensiones distintas. Mezclarlas lleva a decisiones pobres: “E2E”, “regresión” y “funcional” no son alternativas equivalentes. Un mismo test puede ser de sistema, funcional, automatizado, de regresión y end-to-end al mismo tiempo.

## Manual y automatizado

La ejecución manual aprovecha observación humana, exploración y adaptación. La automatización aporta repetibilidad, velocidad y una señal frecuente. Ninguna reemplaza por completo a la otra.

Un escenario suele ser buen candidato para automatización cuando:

- se ejecutará muchas veces;
- tiene un resultado observable y estable;
- cubre un riesgo importante;
- sus datos y entorno pueden controlarse;
- el costo de mantenimiento es razonable.

La exploración de una función nueva, una evaluación estética o un comportamiento que cambia cada semana puede necesitar primero trabajo manual.

## Niveles de prueba

Los niveles ubican el objeto y el contexto de la prueba:

| Nivel | Objeto típico | Señal buscada |
| --- | --- | --- |
| Componente | Función, clase o componente aislado | Lógica local correcta. |
| Integración | Comunicación entre partes | Contratos e intercambio de datos correctos. |
| Sistema | Aplicación integrada | Comportamiento completo frente a requisitos. |
| Aceptación | Producto desde la necesidad usuaria o de negocio | Aptitud para el uso y aceptación acordada. |

Playwright se usa con frecuencia en pruebas de sistema y aceptación a través del navegador, pero también puede comprobar APIs o componentes. Elegir E2E para todo suele producir feedback lento y diagnósticos difíciles.

## Tipos y propósitos

El testing **funcional** verifica qué hace el sistema. El testing **no funcional** evalúa cualidades como accesibilidad, seguridad, rendimiento o compatibilidad. Playwright puede colaborar con algunas de ellas, pero no convierte una suite funcional en una evaluación completa de todas las características de calidad.

Otras etiquetas expresan un propósito de ejecución:

- **Smoke:** conjunto pequeño que comprueba que las rutas críticas están disponibles y permite continuar con pruebas más profundas.
- **Confirmation:** vuelve a ejecutar el escenario que exponía un defecto para verificar su corrección.
- **Regression:** busca efectos adversos en comportamientos que antes funcionaban después de un cambio.
- **End-to-end:** recorre un flujo significativo a través de varias capas o subsistemas desde una perspectiva cercana a la persona usuaria.

Un test de confirmación puede incorporarse luego a regresión. Un smoke puede contener algunos E2E, aunque debería seguir siendo rápido y estable.

## Alcance explícito

Para clasificar un caso, describí al menos:

1. objeto bajo prueba;
2. nivel;
3. comportamiento o característica evaluada;
4. propósito de la ejecución;
5. condición de éxito;
6. riesgos que quedan fuera.

Ejemplo: “Prueba automatizada de sistema, funcional y E2E que confirma que una persona registrada puede comprar con tarjeta de prueba; forma parte del smoke de checkout. No evalúa rendimiento ni fraude real”.

## Why It Matters

Una suite equilibrada no nace de acumular E2E. Nace de colocar la evidencia en el nivel más barato que pueda detectar el riesgo con confianza. Reservá Playwright E2E para comportamientos donde la integración y la interfaz aporten información que una prueba más pequeña no puede brindar.

Las etiquetas son herramientas de decisión, no trofeos. Si dos personas llaman “regresión” a cosas distintas, la planificación, los tiempos de pipeline y la interpretación de resultados también divergirán.
