# Análisis de overhead: baseline versus OTel

## Condiciones de comparación

Ambas pruebas utilizaron el mismo endpoint, 50 usuarios virtuales, 30 segundos de calentamiento y cinco minutos de carga sostenida. La diferencia fue la instrumentación: el baseline deshabilitó OTel y la segunda ejecución exportó telemetría al Collector.

## Tabla comparativa

| Métrica | Baseline | Con OTel | Delta |
|---|---:|---:|---:|
| Latencia promedio | 538.70 ms | 776.29 ms | +44.11 % |
| Latencia p95 | 938.00 ms | 1 293.08 ms | +37.86 % |
| Latencia p99 | 1 138.14 ms | 1 585.64 ms | +39.32 % |
| Throughput | 53.70 req/s | 42.43 req/s | -20.99 % |
| Tasa de error | 0.00 % | 0.00 % | 0.00 puntos porcentuales |
| CPU promedio service-a + service-b | 0.810 % | 1.969 % | +143.09 % |
| Memoria promedio service-a + service-b | 102.79 MiB | 103.12 MiB | +0.33 MiB |

## Método de cálculo

Para latencia y throughput:

```text
Delta (%) = ((valor OTel - valor baseline) / valor baseline) * 100
```

Para CPU se sumó el promedio de ambos servicios en cada condición:

```text
CPU baseline = 0.244 % + 0.566 % = 0.810 %
CPU OTel = 1.308 % + 0.661 % = 1.969 %
```

Para memoria se sumaron los promedios de los dos servicios:

```text
Memoria baseline = 52.61 MiB + 50.18 MiB = 102.79 MiB
Memoria OTel = 52.80 MiB + 50.32 MiB = 103.12 MiB
```

## Interpretación

La ejecución instrumentada presentó una latencia promedio 44.11 % mayor y un p99 39.32 % mayor que el baseline. La latencia adicional absoluta en p99 fue:

```text
1 585.64 ms - 1 138.14 ms = 447.50 ms
```

El throughput disminuyó 20.99 % con OTel. En ambas ejecuciones la tasa de error fue 0 %, por lo que la instrumentación no provocó fallas funcionales bajo esta carga.

El aumento relativo de CPU parece alto porque el consumo baseline es muy pequeño; una diferencia absoluta de aproximadamente 1.159 puntos porcentuales produce un porcentaje elevado. Además, el baseline presentó un pico aislado de 2.75 % en `service-b`, por lo que el promedio y la máxima deben interpretarse por separado.

El consumo de memoria aumentó únicamente 0.33 MiB en promedio, lo que representa un incremento absoluto pequeño en este entorno local. Las mediciones representan contenedores Docker ejecutados sobre Windows y no deben interpretarse como una proyección exacta de producción en GKE o ECS Fargate.

## Conclusión

El benchmark demuestra el costo observable de habilitar OTel en este laboratorio: mayor latencia y menor throughput, sin incremento de errores y con un aumento de memoria reducido. Este costo debe compararse contra el beneficio operativo de disponer de trazas distribuidas, métricas y logs correlacionados para detectar y resolver incidentes.

## Fuentes de evidencia

- [`baseline.md`](baseline.md)
- [`otel.md`](otel.md)
- [`baseline-resources.txt`](baseline-resources.txt)
- [`otel-resources.txt`](otel-resources.txt)
- [`results_baseline.json`](../../benchmark/raw/results_baseline.json)
- [`results_otel.json`](../../benchmark/raw/results_otel.json)
