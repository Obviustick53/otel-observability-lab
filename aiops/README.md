# AIOps local correlator

`correlator.py` evalúa la condición conjunta exigida por la actividad:

`error_rate > baseline_mean + 2*sigma` **Y** `latency_p99 > SLO`.

Los fixtures de `fixtures/` son sintéticos y no deben presentarse como
telemetría observada. `scripts/aiops/run_aiops.py` usa `--mode live` por
defecto y consulta de forma read-only las recording rules existentes de
Prometheus (`otel:error_rate_5m` y `otel:p99_seconds_5m`). El baseline se
calcula con datos del intervalo anterior y termina cinco minutos antes de la
ventana evaluada; por tanto queda congelado y no aprende durante la ventana.
Si falta un valor finito o no hay muestras suficientes, el resultado es
`BLOCKED`/`PARCIAL`, nunca una simulación silenciosa.

Prometheus no transporta `trace_id` en estas métricas. El evento live usa
`trace_id=unknown` y deja una consulta diagnóstica explícita para resolverlo
desde logs o exemplars. El mapeo a CloudWatch Anomaly Detection o DevOps Guru
es una opción de diseño AWS, no se afirma como ejecutada en esta ruta local.

Reproducción sintética:

```powershell
py aiops\correlator.py `
  --input aiops\fixtures\correlation-windows.json `
  --output screenshoot\integrator_project\02_aiops\correlation-fixture.json
py -m unittest discover -s tests\aiops -p "test_*.py"
```

Ejecución live contra el Prometheus local:

```powershell
py scripts\aiops\run_aiops.py --mode live --prometheus-url http://localhost:9090
```

Para reprocessar artefactos históricos hay que solicitarlo explícitamente:

```powershell
py scripts\aiops\run_aiops.py --mode historical --run-timestamp 2026-09-02T00:00:00Z
```

El modo histórico es contexto local reprocesado, no estado actual ni AWS.
El modo live puede recibir `--evaluation-time` para reproducibilidad si la
retención de Prometheus conserva ese instante.

Los artefactos se escriben exclusivamente en
`screenshoot/integrator_project/02_aiops/`, incluido
`aiops-evidence-manifest.json` con hashes, estados y limitaciones. El esquema
detallado, unidades y mapeo opcional AWS están en `aiops/cloud-mapping.md`.
