---
objective: "1.1"
title: Propósito del testing, QA y defectos
---

[Ver el resumen en video](/media/playwright/proposito-testing-qa-defectos.mp4)

Automatizar pruebas no empieza con una herramienta. Empieza con una pregunta: ¿qué información necesitamos obtener sobre la calidad del producto? Un test es una investigación controlada sobre un objeto de prueba —un requisito, una API, una pantalla o un sistema completo— para reducir incertidumbre y ayudar a tomar decisiones.

Entre los objetivos habituales del testing se encuentran:

- verificar que se cumplan requisitos y criterios de aceptación;
- provocar fallos que revelen defectos;
- evaluar cobertura sobre comportamientos o riesgos relevantes;
- reducir el riesgo de liberar software inadecuado;
- aportar información comprensible a quienes deciden si continuar, corregir o publicar.

Un test que pasa no demuestra que el sistema esté libre de defectos. Solo aporta evidencia sobre las condiciones que efectivamente se ejercitaron. Por eso una suite con mil tests puede ser menos útil que una suite pequeña si automatiza escenarios triviales y omite los riesgos centrales.

## Testing, QA y debugging

Estos conceptos colaboran, pero no son sinónimos:

| Concepto | Pregunta principal | Ejemplo |
| --- | --- | --- |
| Testing | ¿Qué comportamiento observamos y qué riesgo revela? | Ejecutar un login con una contraseña inválida y verificar el rechazo. |
| Quality Assurance | ¿Qué procesos previenen problemas y mejoran la forma de construir? | Definir revisiones, criterios de aceptación y prácticas de integración. |
| Debugging | ¿Dónde está la causa del comportamiento incorrecto y cómo la eliminamos? | Seguir una traza hasta la condición que acepta una credencial inválida. |

Playwright participa principalmente en testing dinámico: ejecuta el software, reproduce interacciones y observa resultados. Cuando un test falla, el test ofrece evidencia; luego comienza el diagnóstico. Modificar el test hasta que quede verde sin entender el fallo no es debugging y puede ocultar un defecto real.

## De la acción humana al fallo observable

Conviene usar un vocabulario preciso:

- Un **error** es una acción humana equivocada, como interpretar mal una regla de negocio.
- Un **defecto** es la imperfección introducida en un requisito, código, configuración o test.
- Un **fallo** es el comportamiento incorrecto observable cuando una condición activa el defecto.
- Una **causa raíz** es una condición subyacente que favoreció la aparición del problema, por ejemplo una regla ambigua o una validación ausente en el proceso.

Imaginemos que una persona implementa `edad > 18` cuando la regla era “18 o más”. El error humano produce un defecto en la condición. Una persona de 18 años que no puede registrarse observa un fallo. Una causa raíz posible es que el criterio de aceptación no incluyera el valor límite.

El test automatizado no “es” el defecto: es un instrumento que puede revelar el fallo. También puede fallar por una causa propia, como un localizador frágil, datos compartidos o una espera incorrecta. El trabajo profesional consiste en separar esas posibilidades mediante evidencia.

## El rol de QA Automation

Quien automatiza pruebas traduce intenciones de calidad en evidencia repetible. Sus responsabilidades suelen incluir:

1. comprender la base de prueba y los riesgos;
2. seleccionar casos que valga la pena automatizar;
3. crear datos y entornos controlables;
4. implementar tests legibles y aislados;
5. interpretar resultados, distinguir defectos de problemas del test y comunicar hallazgos;
6. mantener la suite cuando cambia el producto.

La demanda del rol no proviene de escribir scripts rápidamente, sino de acortar el ciclo de feedback sin sacrificar la confiabilidad de la señal.

## Why It Matters

Antes de escribir un `page.click()`, formulá el objetivo del test en una oración: “quiero obtener evidencia de que…”. Luego preguntá qué riesgo cubre, cuál es el resultado esperado y qué diagnóstico permitiría un fallo. Esa disciplina evita suites que ejecutan mucho pero informan poco.

Cuando un test falla, conservá tres hipótesis separadas hasta tener evidencia: defecto del producto, defecto del test o problema del entorno. Playwright ayuda a investigar, pero el razonamiento empieza con este vocabulario.
## FAQ
### Ejemplos de riesgos relevantes en testing
<!-- selected: riesgos relevantes -->

Un ejemplo es que el sistema **acepte credenciales inválidas**. Probar un login con una contraseña incorrecta y verificar su rechazo aporta evidencia sobre ese riesgo.

Otro es que **se aplique mal un límite de edad**: si el requisito permite registrarse con “18 o más”, implementar `edad > 18` deja afuera a quienes tienen exactamente 18. Probar ese valor límite permite detectar el fallo.

Estos casos muestran por qué importa elegir pruebas que cubran requisitos y riesgos centrales: tener muchos tests que pasan no garantiza que esos problemas estén cubiertos.

### ¿Qué es el software inadecuado y qué ejemplos hay?
<!-- selected: software inadecuado -->

El **software inadecuado** es aquel que no cumple los requisitos o criterios de aceptación esperados, o presenta comportamientos incorrectos que hacen riesgosa su publicación.

Por ejemplo, un sistema de login que acepta una contraseña inválida, o un registro que rechaza a una persona de 18 años cuando la regla permite registrarse con “18 o más”.

El testing busca obtener evidencia para detectar estos problemas y decidir si corresponde corregir o publicar el producto. Que los tests pasen no garantiza que el software esté libre de defectos: solo informa sobre las condiciones que se probaron.
