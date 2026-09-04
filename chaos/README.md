# Chaos Engineering local

Esta carpeta contiene únicamente los dos experimentos exigidos:

- `service-b-latency`: `LAB_SERVICE_B_LATENCY_MS=200`.
- `data-service-errors`: inyección exacta de `LAB_DATA_ERROR_RATE=0.1`.

“Exacta” describe el control aplicado (200 ms o fracción 0.1), no una cifra
inventada en las muestras: el error rate observado se calcula con las
solicitudes realmente completadas y puede variar alrededor del 10% por tamaño
de muestra.

El contrato ejecutable está en `experiment-contract.json`. El runner lo carga y
rechaza cualquier experimento cuyo servicio o valor exacto no coincida con el
contrato. Cada ejecución registra en `lifecycle-events.json` la solicitud de
inyección, el `StartedAt` del contenedor variante, el valor observado en su
entorno, el rollback y la validación de recovery.

El runner exige que el servicio objetivo ya esté saludable, mide una ventana
baseline comparable, registra la solicitud y el `StartedAt` real del contenedor
de inyección, y mantiene un timebox para cada fase. El timebox de inyección
por defecto es de 180 s porque las reglas locales usan `for: 2m`; una ejecución
de 60 s no puede demostrar un firing de esas reglas. Durante la inyección
consulta las APIs reales de Prometheus (`/api/v1/alerts` y PromQL de error rate,
p99, disponibilidad y error budget) y Alertmanager
(`/api/v2/alerts`) cuando responden. Solo una alerta reportada por esas APIs en
estado firing puede producir `firing_timestamp_utc` y MTTD; un 5xx HTTP o una
evaluación local nunca se convierte en alerta por inferencia.

También se registran stop conditions, comandos de rollback, el valor del
control después del rollback y una ventana de recovery. Si un backend no está
disponible, el reporte conserva la consulta, el error y una clasificación como
`BACKEND_UNAVAILABLE`; no se inventan resultados. El cálculo local de p99,
error rate, disponibilidad, throughput y error budget queda separado de la
observación de alertas. Una stop condition por error rate extremo (>80% después
de 20 solicitudes) limita el blast radius además del health check, el límite de
fallos consecutivos y el timebox.

El resultado de recovery solo se considera verificado cuando el control vuelve
a `0`, el health check responde y la ventana de recovery alcanza la
disponibilidad mínima de 99.5%. La clasificación `EXECUTED_ROLLBACK_UNVERIFIED`
o `EXECUTED_RECOVERY_UNVERIFIED` mantiene el bloqueo explícito.

El script es reutilizable por el coordinador. Esta implementación no ejecuta
los experimentos ni genera evidencias nuevas. Para evitar escribir evidencia
final por defecto, los artefactos de una ejecución se guardan en
`chaos/runs/`; el coordinador puede pasar explícitamente otro `-OutputRoot`.

Ejemplos:

```powershell
.\chaos\run-experiment.ps1 -Experiment service-b-latency
.\chaos\run-experiment.ps1 -Experiment data-service-errors
```

Para una validación más corta en un entorno de prueba se pueden ajustar los
timeboxes, pero una ejecución con menos de dos minutos no puede demostrar el
firing de las reglas locales con `for: 2m`. El runner siempre pasa las
duraciones reales de fase al medidor, incluso si una stop condition termina la
fase antes del límite configurado.

El script requiere que el stack ya esté saludable. Si Docker o la alerta local
no están disponibles, la ejecución debe conservar el preflight y clasificarse
como bloqueada/no ejecutada.
