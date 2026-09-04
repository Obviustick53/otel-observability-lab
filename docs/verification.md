# Verificación documental del reporte de observabilidad

Fecha de esta verificación: 2026-09-03 UTC.

El único criterio normativo usado es `docs/PROMPT_MAESTRO_AGENTES_OBSERVABILIDAD.md`.
Este documento verifica el generador y la trazabilidad del reporte; no ejecuta AWS,
no obtiene secretos y no muta recursos cloud.

## Fuentes y alcance

- Fuente primaria: `screenshoot/integrator_project/evidence-manifest.json`.
- Generador: `report/build_report.py`.
- Contenido de madurez y roadmap: `report/report-data.json`.
- Salida: `report/technical-report.pdf`.
- Las carpetas `evidence/`, `evidence/chaos/` y `screenshots/` se conservan como
  históricas y no se usan como evidencia primaria.

## Estado por criterio

| Criterio | Estado que imprime el generador | Base de trazabilidad |
|---|---|---|
| C1 — Tres microservicios y tres pilares OTel | Derivado del manifiesto; puede combinar EJECUTADO/LOCAL | `01_architecture_otel/` |
| C2 — Correlación AIOps AND y `trace_id` | Derivado del manifiesto; distingue SIMULADO y reproceso local | `02_aiops/` |
| C3 — Red y seguridad | Derivado del manifiesto; separa SIMULADO local de AWS y bloqueos | `03_network_security/` y artefactos AWS declarados |
| C4 — Chaos, SLO, error budget y rollback | Derivado de los dos `report.json` canónicos | `04_chaos/` |
| C5 — AWS, costos y reproducibilidad | Derivado del estado AWS declarado, sin inferir despliegues | `05_aws_deployment/` |

El estado normalizado no reemplaza el estado bruto. Si hay mezcla de entornos,
el PDF muestra ambos para evitar que una simulación o un plan se lea como ejecución.

## Comandos ejecutados para esta entrega

```powershell
py -m py_compile report/build_report.py
py report/build_report.py
```

Estos comandos solo validan/importan el generador, leen el manifiesto y producen
el PDF. No levantan Compose, no ejecutan experimentos de chaos y no llaman AWS CLI.
En este entorno `reportlab` no está instalado y el módulo `numpy` disponible no
carga sus DLL; el generador usó su fallback PDF basado únicamente en la biblioteca
estándar y produjo exactamente 10 páginas.

## Limitaciones y correcciones históricas

- El generador no reejecuta pruebas ni valida que un resultado externo siga vigente;
  reproduce lo que el manifiesto declara.
- La ausencia de artefacto o una dependencia bloqueada se imprime como
  `BLOQUEADO`/`NO EJECUTADO`; no se completa por inferencia.
- El contenido histórico que describía dos servicios o rutas GCP/GKE fue corregido
  dentro de `report/**`; el reporte actual usa tres servicios de aplicación más
  `data-service` y describe únicamente AWS como ruta cloud.
- Las cifras de MTTD, SLO, error budget y costos se leen de JSON canónico. Una
  estimación AWS no se presenta como costo observado.
- No se imprimen access keys, tokens, secretos, ARN completos, correos ni valores
  de credenciales en el reporte.

## Revisión posterior a nueva captura

Después de integrar mejoras o capturar evidencia nueva, actualice el manifiesto,
regenere el PDF y revise que cada fila C1-C5 conserve: timestamp UTC, entorno,
comando/script, resultado, hash, estado y limitación. Si AWS no fue aprobado o
algún paso falló, el estado debe permanecer explícitamente `BLOQUEADO` o
`NO EJECUTADO`.
