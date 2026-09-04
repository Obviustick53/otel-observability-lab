"""Build the single evidence manifest required by the integration activity."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "screenshoot" / "integrator_project" / "evidence-manifest.json"


def file_record(relative: str, status: str, environment: str, limitation: str = ""):
    path = ROOT / relative
    record = {
        "path": relative.replace("\\", "/"),
        "status": status,
        "environment": environment,
        "exists": path.is_file(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
    }
    if limitation:
        record["limitation"] = limitation
    return record


def main():
    latest_chaos = {
        "service_b_latency": "screenshoot/integrator_project/04_chaos/service-b-latency-20260903T005926Z/report.json",
        "data_service_errors": "screenshoot/integrator_project/04_chaos/data-service-errors-20260903T005830Z/report.json",
    }
    artifacts = [
        file_record(
            "screenshoot/integrator_project/01_architecture_otel/local-smoke-20260903T004420Z.json",
            "VERIFICADO",
            "local-executed",
            "Smoke real del flujo de tres servicios; incluye trace_id.",
        ),
        file_record(
            "screenshoot/integrator_project/01_architecture_otel/trace-prometheus-verification-20260903T005000Z.json",
            "VERIFICADO",
            "local-executed",
            "Consulta local de Jaeger y Prometheus.",
        ),
        file_record(
            "screenshoot/integrator_project/02_aiops/synthetic-rule-comparison.json",
            "VERIFICADO",
            "local-synthetic",
            "Ground truth pertenece al fixture; no es telemetría productiva.",
        ),
        file_record(
            "screenshoot/integrator_project/02_aiops/real-local-correlation-event.json",
            "PARCIAL",
            "local-reprocessed",
            "Reproceso offline de evidencia local histórica; no backend vivo.",
        ),
        file_record(
            "screenshoot/integrator_project/03_network_security/validation-results.json",
            "PARCIAL",
            "local-simulated",
            "Las señales de seguridad locales son simuladas; Flow Logs/Security Hub AWS no fueron ejecutados.",
        ),
        file_record(latest_chaos["service_b_latency"], "VERIFICADO", "local-executed", "Escenario exacto: +200 ms en service-b; rollback saludable."),
        file_record(latest_chaos["data_service_errors"], "VERIFICADO", "local-executed", "Escenario exacto: 10% de errores en data-service; MTTD medido en muestras locales."),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/preflight.json",
            "VERIFICADO",
            "aws-read-only",
            "Preflight AWS actual; las respuestas de paginación se almacenan únicamente como [REDACTED].",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/cost-estimate.json",
            "VERIFICADO",
            "aws-design",
            "USD 0.7806/8h estimado por inputs; el presupuesto operativo y el cost-guard son USD 10.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/template-validation-v7.json",
            "PARCIAL",
            "aws-design",
            "Validación AWS ejecutada; cfn-lint no está instalado en el entorno local.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/budget-mcp-verification.json",
            "VERIFICADO",
            "aws-control-plane",
            "Presupuesto mensual de USD 10, email y SNS configurados; Lambda cost-guard desplegado.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/migration-evidence-v5.json",
            "VERIFICADO",
            "aws-executed",
            "Migración idempotente ejecutada como tarea ECS puntual contra RDS privado; exit code 0.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/smoke-evidence-v7.json",
            "VERIFICADO_CON_LIMITACIONES",
            "aws-executed",
            "ECS v5, HTTP, Flow Logs, CloudWatch, X-Ray y CloudTrail consultados; Security Hub requiere suscripción regional.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/collector-logs-evidence-final.json",
            "VERIFICADO",
            "aws-executed",
            "El collector recibió LogsExporter y no registró UNIMPLEMENTED durante la ventana de verificación.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/cloudformation-plan-live.json",
            "VERIFICADO",
            "aws-control-plane",
            "Plan y estado de CloudFormation del despliegue del laboratorio.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/cost-estimate-24h.json",
            "VERIFICADO",
            "aws-design",
            "Estimación reproducible para 24 horas; no es costo observado.",
        ),
        file_record(
            "screenshoot/integrator_project/05_aws_deployment/cost-estimate-30d.json",
            "VERIFICADO",
            "aws-design",
            "Estimación reproducible para 30 días; no es costo observado.",
        ),
    ]
    visual_evidence = [
        file_record(f"screenshoot/integrator_project/visual_evidence/{name}", "VERIFICADO_VISUAL", "local-rendered", "Captura legible generada a partir de la evidencia canónica.")
        for name in ["01-tests-local.png", "02-manifest.png", "03-aiops-json.png", "04-security-json.png", "05-chaos-json.png", "06-aws-smoke-json.png"]
    ] + [
        file_record(f"screenshoot/integrator_project/visual_evidence/{name}", "VERIFICADO_VISUAL", "aws-console-read-only", "Captura de la consola AWS autenticada; no contiene credenciales ni secretos.")
        for name in ["07-aws-console-home.png", "08-aws-console-ecs.png", "09-aws-console-cloudformation.png", "10-aws-console-rds.png", "11-aws-console-cloudwatch.png", "12-aws-console-budgets.png", "13-aws-console-gallery.png"]
    ]
    manifest = {
        "schema_version": "integrator.evidence-manifest.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_prompt": "docs/PROMPT_MAESTRO_AGENTES_OBSERVABILIDAD.md",
        "evidence_root": "screenshoot/integrator_project/",
        "new_evidence_only": True,
        "execution_summary": {
            "local_stack": "VERIFICADO",
            "aiops": "VERIFICADO_SINTETICO_Y_PARCIAL_LOCAL",
            "network_security": "VERIFICADO_AWS_CON_LIMITACIONES",
            "chaos_experiments": 2,
            "aws_deployment": "VERIFICADO_CON_COST_GUARD",
            "aws_mutation_executed": True,
        },
        "criteria": [
            {"id": "C1", "name": "Tres microservicios y tres pilares OTel", "status": "VERIFICADO", "evidence": ["01_architecture_otel/local-smoke-20260903T004420Z.json", "01_architecture_otel/trace-prometheus-verification-20260903T005000Z.json"]},
            {"id": "C2", "name": "Correlación AIOps AND y trace_id", "status": "VERIFICADO_SINTETICO_Y_PARCIAL_LOCAL", "evidence": ["02_aiops/synthetic-rule-comparison.json", "02_aiops/real-local-correlation-event.json"]},
            {"id": "C3", "name": "Red y seguridad", "status": "VERIFICADO_AWS_FLOW_LOGS_CON_LIMITACION_SECURITY_HUB", "evidence": ["03_network_security/validation-results.json", "05_aws_deployment/smoke-evidence-v7.json"]},
            {"id": "C4", "name": "Chaos, SLO, error budget, rollback", "status": "VERIFICADO_LOCAL", "evidence": ["04_chaos/service-b-latency-20260903T005926Z/report.json", "04_chaos/data-service-errors-20260903T005830Z/report.json"]},
            {"id": "C5", "name": "AWS, costos y reproducibilidad", "status": "VERIFICADO_AWS_DESPLEGADO_CON_COST_GUARD", "evidence": ["05_aws_deployment/cost-estimate.json", "05_aws_deployment/template-validation-v7.json", "05_aws_deployment/migration-evidence-v5.json", "05_aws_deployment/smoke-evidence-v7.json", "05_aws_deployment/budget-mcp-verification.json"]},
        ],
        "artifacts": artifacts,
        "visual_evidence": visual_evidence,
        "historical_artifacts_note": "evidence/ y screenshots/ contienen material previo; no se usan como evidencia nueva primaria.",
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
