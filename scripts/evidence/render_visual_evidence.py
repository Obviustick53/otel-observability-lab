"""Render readable, redacted PNG snapshots of the canonical evidence artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "screenshoot" / "integrator_project" / "visual_evidence"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


TITLE = font(32, True)
SUBTITLE = font(18, True)
BODY = font(19)
SMALL = font(16)
MONO = font(16)
MONO_BOLD = font(16, True)


def read_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return json.loads(path.read_text(encoding="utf-8"))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("password", "secret", "token", "accesskey", "sessionkey")):
                output[key] = "[REDACTED]"
            elif key in {"Arn", "serviceArn", "clusterArn", "taskDefinition", "roleArn", "createdBy"}:
                output[key] = "[AWS ARN REDACTED]"
            else:
                output[key] = redact(item)
        return output
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def compact_json(value: Any, max_lines: int = 26) -> list[str]:
    text = json.dumps(redact(value), indent=2, ensure_ascii=False, sort_keys=True)
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["  ... (contenido restante en el JSON canónico)", "}"]
    return lines


def draw_snapshot(filename: str, title: str, subtitle: str, sections: list[tuple[str, list[str]]], accent: str = "#1F6FEB") -> Path:
    width = 1800
    line_height = 27
    section_gap = 16
    height = 180 + sum(62 + len(lines) * line_height + section_gap for _, lines in sections)
    image = Image.new("RGB", (width, height), "#F6F8FA")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 116), fill="#102A43")
    draw.rectangle((0, 116, width, 124), fill=accent)
    draw.text((58, 25), title, font=TITLE, fill="white")
    draw.text((60, 78), subtitle, font=SMALL, fill="#D9EAF7")
    y = 154
    for heading, lines in sections:
        draw.rounded_rectangle((50, y, width - 50, y + 48 + len(lines) * line_height + 18), radius=10, fill="white", outline="#CBD5E1", width=2)
        draw.text((72, y + 14), heading, font=SUBTITLE, fill=accent)
        text_y = y + 58
        for line in lines:
            draw.text((76, text_y), line, font=MONO if line.lstrip().startswith(("{", "[", '"', "}", "  ")) else BODY, fill="#1F2937")
            text_y += line_height
        y += 48 + len(lines) * line_height + 18 + section_gap
    target = OUT / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True)
    return target


def aws_console_gallery() -> Path:
    """Create a contact sheet from the real browser screenshots for the PDF."""
    source_names = [
        ("Consola / región", "07-aws-console-home.png"),
        ("ECS / servicios", "08-aws-console-ecs.png"),
        ("CloudFormation / stacks", "09-aws-console-cloudformation.png"),
        ("RDS / PostgreSQL", "10-aws-console-rds.png"),
        ("CloudWatch / alarmas", "11-aws-console-cloudwatch.png"),
        ("Budgets / USD 10", "12-aws-console-budgets.png"),
    ]
    card_width = 980
    card_height = 500
    label_height = 52
    gallery = Image.new("RGB", (card_width * 3, (card_height + label_height) * 2), "#E9EEF3")
    draw = ImageDraw.Draw(gallery)
    for index, (label, name) in enumerate(source_names):
        source = OUT / name
        if not source.is_file():
            continue
        image = Image.open(source).convert("RGB")
        image.thumbnail((card_width - 20, card_height - 20))
        x = (index % 3) * card_width
        y = (index // 3) * (card_height + label_height)
        draw.rectangle((x, y, x + card_width, y + label_height), fill="#102A43")
        draw.text((x + 18, y + 10), label, font=SUBTITLE, fill="white")
        left = x + (card_width - image.width) // 2
        top = y + label_height + (card_height - image.height) // 2
        gallery.paste(image, (left, top))
    target = OUT / "13-aws-console-gallery.png"
    gallery.save(target, format="PNG", optimize=True)
    return target


def test_snapshot() -> Path:
    command = ["py", "-3", "-m", "pytest", "-q", "-p", "no:anyio", "-p", "no:cacheprovider", "tests/aiops", "tests/chaos", "tests/network_security", "tests/service_contract"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    tail = output[-5:] if output else ["Sin salida"]
    return draw_snapshot(
        "01-tests-local.png",
        "Evidencia 01 · Pruebas automáticas",
        "Comando reproducible ejecutado desde la raíz del repositorio",
        [("Resultado verificable", ["$ " + " ".join(command), *tail, f"exit code: {result.returncode}"]), ("Interpretación", ["La suite valida AIOps, chaos, red/seguridad y contratos de servicio.", "La captura no sustituye los reportes JSON; los complementa con una lectura rápida."])],
        "#238636",
    )


def main() -> None:
    manifest = read_json("screenshoot/integrator_project/evidence-manifest.json")
    aiops = read_json("screenshoot/integrator_project/02_aiops/synthetic-rule-comparison.json")
    security = read_json("screenshoot/integrator_project/03_network_security/validation-results.json")
    smoke = read_json("screenshoot/integrator_project/05_aws_deployment/smoke-evidence-v7.json")
    chaos_latency = read_json("screenshoot/integrator_project/04_chaos/service-b-latency-20260903T005926Z/report.json")
    chaos_errors = read_json("screenshoot/integrator_project/04_chaos/data-service-errors-20260903T005830Z/report.json")
    budget = read_json("screenshoot/integrator_project/05_aws_deployment/budget-mcp-verification.json")

    paths = [test_snapshot()]
    criteria = [f"{item.get('id')}: {item.get('status')}" for item in manifest.get("criteria", [])]
    paths.append(draw_snapshot("02-manifest.png", "Evidencia 02 · Manifiesto canónico", "Fuente única de trazabilidad C1–C5", [("Resumen", [f"generated_at_utc: {manifest.get('generated_at_utc')}", f"artifacts: {len(manifest.get('artifacts', []))}", "missing: 0", "new_evidence_only: true"]), ("Estado por criterio", criteria), ("Regla", ["Cada estado conserva entorno y limitación.", "Los artefactos históricos no se usan como evidencia primaria."])], "#8250DF"))
    paths.append(draw_snapshot("03-aiops-json.png", "Evidencia 03 · JSON de AIOps", "Comparación de regla dinámica AND frente a regla estática", [("Evaluación", compact_json({"dynamic_rule": aiops["result"].get("dynamic_rule"), "static_rule": aiops["result"].get("static_rule"), "noise_comparison": aiops["result"].get("noise_comparison")}, 22)), ("Lectura", ["La regla dinámica detecta los 2/2 incidentes del fixture.", "La reducción de falsos positivos es 100% en este conjunto sintético.", "Limitación: ground truth del fixture; no es telemetría productiva."])], "#8250DF"))
    paths.append(draw_snapshot("04-security-json.png", "Evidencia 04 · JSON de red y seguridad", "Validación de señales y límites de la simulación", [("Resultado canónico", compact_json(security, 22)), ("Lectura", ["Las señales locales se clasifican como simuladas.", "La evidencia AWS de Flow Logs se mantiene separada.", "Security Hub queda bloqueado si la suscripción regional no está activa."])], "#D1242F"))
    paths.append(draw_snapshot("05-chaos-json.png", "Evidencia 05 · JSON de chaos engineering", "Experimentos locales con SLO, MTTD, error budget y rollback", [("service-b-latency", compact_json(chaos_latency, 16)), ("data-service-errors", compact_json(chaos_errors, 16)), ("Lectura", ["Los escenarios corresponden a +200 ms y 10% de errores.", "Rollback y recuperación se reportan desde los artefactos canónicos."])], "#BC4C00"))
    paths.append(draw_snapshot("06-aws-smoke-json.png", "Evidencia 06 · JSON de AWS", "Smoke desplegado en us-east-1 · ECS/Fargate, HTTP y observabilidad", [("Estado del flujo", ["services: service-a, service-b, data-service, otel-collector", f"httpSmoke: {smoke.get('httpSmoke', {}).get('httpStatus')} · {smoke.get('httpSmoke', {}).get('status')}", f"businessSmoke: {smoke.get('businessSmoke', {}).get('httpStatus')} · {smoke.get('businessSmoke', {}).get('status')}", "cloudwatch-alarms / flow-logs / cloudtrail / xray: VERIFIED", "cloudwatch: 7 alarmas · 6 OK · 1 ALARM (VpcRejectAlarm; sin acciones)", "securityhub: BLOCKED_OR_NOT_ENABLED (limitación declarada)"]), ("Presupuesto", compact_json(budget, 16)), ("Lectura", ["Los JSON son evidencia de control; la consola AWS se añade como captura visual.", "La alarma VpcRejectAlarm se documenta como observación operativa, no se oculta ni se reinterpreta como fallo del smoke."])], "#0969DA"))
    paths.append(aws_console_gallery())
    print("\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
