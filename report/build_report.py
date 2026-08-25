from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "report" / "technical-report.pdf"


def img(path: str, width=17.2 * cm, height=None):
    image_path = ROOT / path
    image = Image(str(image_path), width=width, height=height)
    image.hAlign = "CENTER"
    return image


def p(text, style):
    return Paragraph(text, style)


def build():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            parent=styles["Normal"],
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#404040"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1Blue",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=4,
            spaceAfter=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2Blue",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=7,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyEs",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#505050"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
            spaceBefore=3,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeSmall",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7.2,
            leading=9,
            leftIndent=5,
            rightIndent=5,
            backColor=colors.HexColor("#F2F4F7"),
            borderColor=colors.HexColor("#D9E1F2"),
            borderWidth=0.5,
            borderPadding=5,
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title="Reporte técnico - Pipeline de observabilidad OTel",
        author="otel-observability-lab",
    )

    story = []

    # Cover
    story.append(Spacer(1, 2.0 * cm))
    story.append(p("Reporte técnico", styles["CoverSub"]))
    story.append(p("Pipeline de observabilidad end-to-end con OpenTelemetry", styles["CoverTitle"]))
    story.append(p("Microservicios en Python, OTel Collector, Jaeger, Prometheus, Loki y Grafana", styles["CoverSub"]))
    story.append(Spacer(1, 1.0 * cm))
    cover_data = [
        [p("Alcance", styles["Small"]), p("Laboratorio local reproducible con Docker Desktop", styles["BodyEs"])],
        [p("Flujo", styles["Small"]), p("k6 -> service-a -> service-b -> PostgreSQL", styles["BodyEs"])],
        [p("Señales", styles["Small"]), p("Trazas, métricas y logs estructurados correlacionados por trace_id", styles["BodyEs"])],
        [p("Evidencia", styles["Small"]), p("Ejecución local sin costos de GCP ni AWS", styles["BodyEs"])],
    ]
    cover_table = Table(cover_data, colWidths=[3.0 * cm, 13.5 * cm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#D9EAF7")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#9FBAD0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C7D7E6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 1.3 * cm))
    story.append(p("Resultado ejecutivo", styles["H1Blue"]))
    story.append(p("El laboratorio demuestra la propagación W3C del contexto desde service-a hacia service-b y PostgreSQL. El OTel Collector recibe las tres señales y las exporta a backends locales especializados. Las evidencias muestran 14 spans en una traza completa, métricas consultables en Prometheus, un dashboard operativo de seis paneles y logs JSON correlacionados mediante trace_id.", styles["BodyEs"]))
    story.append(p("En el benchmark de 50 usuarios virtuales y cinco minutos de carga sostenida, ambas condiciones terminaron con 0 % de errores. Con OTel, el p99 aumentó 39.32 % y el throughput disminuyó 20.99 %, mientras que la memoria promedio aumentó solo 0.33 MiB en los dos servicios.", styles["BodyEs"]))
    story.append(PageBreak())

    # Architecture
    story.append(p("1. Objetivo y arquitectura", styles["H1Blue"]))
    story.append(p("El objetivo es implementar un pipeline de observabilidad para dos microservicios con dependencia HTTP y acceso a base de datos. La solución prioriza la detección y resolución de problemas mediante correlación cross-signal.", styles["BodyEs"]))
    story.append(p("Flujo de una solicitud", styles["H2Blue"]))
    story.append(Preformatted("""k6 / navegador
      |
      v
service-a:8000 -- W3C traceparent --> service-b:8001
      |                                  |
      +------------ PostgreSQL ---------+
                         |
                         v
                  OTLP hacia Collector
                  /        |          \\
                 v         v           v
              Jaeger   Prometheus     Loki
                 \\        |           /
                  \\       v          /
                       Grafana""", styles["CodeSmall"]))
    story.append(p("Componentes principales", styles["H2Blue"]))
    components = [
        [p("Componente", styles["Small"]), p("Responsabilidad", styles["Small"])],
        [p("service-a / service-b", styles["BodyEs"]), p("API FastAPI, lógica de negocio, cliente HTTP, PostgreSQL y SDK OTel.", styles["BodyEs"])],
        [p("OTel Collector", styles["BodyEs"]), p("Receiver OTLP gRPC/HTTP, processors memory_limiter/resource/batch y exporters de trazas, métricas y logs.", styles["BodyEs"])],
        [p("Jaeger", styles["BodyEs"]), p("Almacenamiento y visualización local de trazas distribuidas.", styles["BodyEs"])],
        [p("Prometheus", styles["BodyEs"]), p("Consulta y almacenamiento de métricas expuestas por el Collector.", styles["BodyEs"])],
        [p("Loki / Grafana", styles["BodyEs"]), p("Almacenamiento, consulta y visualización de logs y métricas con enlaces hacia Jaeger.", styles["BodyEs"])],
    ]
    t = Table(components, colWidths=[5.0 * cm, 11.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(p("Decisiones de diseño", styles["H2Blue"]))
    story.append(p("El Collector desacopla los servicios de los backends, permitiendo cambiar Jaeger, Prometheus o Loki sin modificar la instrumentación. Jaeger usa almacenamiento en memoria para mantener el laboratorio local sin problemas de permisos ni costos. Las métricas de latencia usan buckets explícitos para que los percentiles sean interpretables. La infraestructura GKE y ECS Fargate está parametrizada como IaC, pero no se aplica durante esta entrega local.", styles["BodyEs"]))
    story.append(PageBreak())

    # Instrumentation and collector
    story.append(p("2. Instrumentación y Collector", styles["H1Blue"]))
    story.append(p("Los servicios utilizan el SDK de OpenTelemetry para emitir las tres señales. La instrumentación HTTP cubre las entradas FastAPI y las llamadas entre servicios; la instrumentación de PostgreSQL registra las consultas SQL. Además, se definieron spans de negocio para identificar validaciones, llamadas al servicio dependiente y accesos a datos.", styles["BodyEs"]))
    story.append(p("Spans personalizados relevantes", styles["H2Blue"]))
    story.append(Preformatted("""order.business.validate
order.db.fetch
order.service_b.call
inventory.business.validate
inventory.db.fetch
SELECT""", styles["CodeSmall"]))
    story.append(p("Los logs se emiten como JSON y contienen el contexto de la operación. En Loki, la serialización OTLP muestra los campos como traceid y spanid, conservando los identificadores W3C de 32 y 16 caracteres respectivamente. Grafana tiene un derived field que reconoce ambas variantes y permite abrir la traza en Jaeger.", styles["BodyEs"]))
    story.append(p("Configuración del Collector", styles["H2Blue"]))
    story.append(Preformatted("""receivers: otlp (gRPC :4317, HTTP :4318)
processors: memory_limiter -> resource -> batch
exporters: jaeger, prometheus, loki, debug
metrics endpoint: :8889
health endpoint: :13133""", styles["CodeSmall"]))
    story.append(p("La evidencia collector-healthy confirma que el Collector procesa periódicamente spans y métricas. En la ejecución observada se registraron resource spans, 14 métricas y 22 puntos de datos por ciclo de exportación, sin errores recientes.", styles["BodyEs"]))
    story.append(p("Evidencia de Jaeger", styles["H2Blue"]))
    story.append(img("screenshots/jaeger-traza-completa.png", width=17.2 * cm, height=8.1 * cm))
    story.append(p("Figura 1. Traza distribuida con service-a, service-b, PostgreSQL y 14 spans.", styles["Caption"]))
    story.append(PageBreak())

    # Metrics and dashboard
    story.append(p("3. Métricas y visualización", styles["H1Blue"]))
    story.append(p("Prometheus consulta el endpoint de métricas del Collector y permite comprobar las series emitidas por cada servicio. La evidencia directa muestra 15 solicitudes para cada microservicio y valores de p95 numéricos para ambos.", styles["BodyEs"]))
    story.append(p("Resultados Prometheus", styles["H2Blue"]))
    metrics_table = Table([
        [p("Métrica", styles["Small"]), p("service-a", styles["Small"]), p("service-b", styles["Small"])],
        [p("Solicitudes", styles["BodyEs"]), p("15", styles["BodyEs"]), p("15", styles["BodyEs"])],
        [p("p95", styles["BodyEs"]), p("75 ms", styles["BodyEs"]), p("24.25 ms", styles["BodyEs"])],
    ], colWidths=[6.0 * cm, 5.25 * cm, 5.25 * cm], repeatRows=1)
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.25 * cm))
    story.append(img("screenshots/prometheus/prometheus-latency.png", width=17.2 * cm, height=8.2 * cm))
    story.append(p("Figura 2. Consulta directa del p95 en Prometheus para ambos servicios.", styles["Caption"]))
    story.append(PageBreak())

    story.append(p("Dashboard Grafana", styles["H2Blue"]))
    story.append(p("El dashboard reúne cuatro SLIs - latencia p99, tasa de error, throughput y disponibilidad - y dos indicadores operativos del Collector - CPU y errores o datos descartados. La ejecución observada presentó 100 % de disponibilidad, 0 % de errores y cero spans descartados.", styles["BodyEs"]))
    story.append(img("screenshots/dashboards_grafana/grafana-dashboard-6-paneles.png", width=17.2 * cm, height=9.2 * cm))
    story.append(p("Figura 3. Dashboard Grafana con seis paneles y datos locales.", styles["Caption"]))
    story.append(PageBreak())

    # Logs correlation
    story.append(p("4. Logs estructurados y correlación cross-signal", styles["H1Blue"]))
    story.append(p("Loki recibe los logs JSON a través del Collector. La consulta por etiquetas permite localizar ambos servicios y la consulta de contenido permite filtrar una única traza. El mismo traceid aparece en las tres operaciones: procesamiento del pedido, llamada HTTP a service-b y respuesta de inventario.", styles["BodyEs"]))
    story.append(Preformatted('''{service_name=~"otel-lab/service-a|otel-lab/service-b"}

{service_name=~"otel-lab/service-a|otel-lab/service-b"} |= "a4427e712044eff393ec7a28b7f10216"''', styles["CodeSmall"]))
    story.append(img("screenshots/logs_grafana/logs-json-trace-id.png", width=17.2 * cm, height=8.1 * cm))
    story.append(p("Figura 4. Logs JSON consultados en Grafana Explore con traceid y spanid.", styles["Caption"]))
    story.append(PageBreak())
    story.append(p("Correlación por trace_id", styles["H2Blue"]))
    story.append(p("La siguiente evidencia filtra los logs por el traceid a4427e712044eff393ec7a28b7f10216. El identificador coincide con la traza abierta en Jaeger, permitiendo navegar desde una línea de log hasta el timeline distribuido.", styles["BodyEs"]))
    story.append(img("screenshots/logs_grafana/correlacion-cross-signal-trace-id.png", width=17.2 * cm, height=8.6 * cm))
    story.append(p("Figura 5. Consulta Loki filtrada por una traza específica.", styles["Caption"]))
    story.append(p("Los archivos JSON descargados desde Loki se conservan en evidence/loki/. Esto permite auditar el contenido fuera de la interfaz gráfica y reproducir la consulta durante la evaluación.", styles["BodyEs"]))
    story.append(PageBreak())

    # Benchmark
    story.append(p("5. Benchmark y análisis de overhead", styles["H1Blue"]))
    story.append(p("Se ejecutaron dos pruebas comparables con 50 usuarios virtuales, 30 segundos de calentamiento y cinco minutos de carga sostenida. El baseline deshabilitó el SDK OTel; la segunda ejecución habilitó trazas, métricas y logs hacia el Collector.", styles["BodyEs"]))
    bench = Table([
        [p("Métrica", styles["Small"]), p("Baseline", styles["Small"]), p("Con OTel", styles["Small"]), p("Delta", styles["Small"])],
        [p("Latencia promedio", styles["BodyEs"]), p("538.70 ms", styles["BodyEs"]), p("776.29 ms", styles["BodyEs"]), p("+44.11 %", styles["BodyEs"])],
        [p("p95", styles["BodyEs"]), p("938.00 ms", styles["BodyEs"]), p("1 293.08 ms", styles["BodyEs"]), p("+37.86 %", styles["BodyEs"])],
        [p("p99", styles["BodyEs"]), p("1 138.14 ms", styles["BodyEs"]), p("1 585.64 ms", styles["BodyEs"]), p("+39.32 %", styles["BodyEs"])],
        [p("Throughput", styles["BodyEs"]), p("53.70 req/s", styles["BodyEs"]), p("42.43 req/s", styles["BodyEs"]), p("-20.99 %", styles["BodyEs"])],
        [p("Tasa de error", styles["BodyEs"]), p("0.00 %", styles["BodyEs"]), p("0.00 %", styles["BodyEs"]), p("0 puntos", styles["BodyEs"])],
        [p("CPU promedio total", styles["BodyEs"]), p("0.810 %", styles["BodyEs"]), p("1.969 %", styles["BodyEs"]), p("+143.09 %", styles["BodyEs"])],
        [p("Memoria promedio total", styles["BodyEs"]), p("102.79 MiB", styles["BodyEs"]), p("103.12 MiB", styles["BodyEs"]), p("+0.33 MiB", styles["BodyEs"])],
    ], colWidths=[5.1 * cm, 3.5 * cm, 3.5 * cm, 3.9 * cm], repeatRows=1)
    bench.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(bench)
    story.append(Spacer(1, 0.3 * cm))
    story.append(p("Interpretación", styles["H2Blue"]))
    story.append(p("Con OTel, el p99 aumentó 447.50 ms y el throughput disminuyó 20.99 %, pero no se observaron errores funcionales. El aumento relativo de CPU debe interpretarse con cautela porque el baseline consume muy poco y presentó un pico aislado de 2.75 % en service-b. La memoria aumentó solo 0.33 MiB en promedio para los dos servicios.", styles["BodyEs"]))
    story.append(p("Las mediciones fueron tomadas en contenedores Docker sobre Windows y sirven como evidencia del laboratorio, no como una proyección exacta de producción en GKE o ECS Fargate.", styles["BodyEs"]))
    story.append(PageBreak())

    # Conclusions and reproducibility
    story.append(p("6. Conclusiones, limitaciones y reproducción", styles["H1Blue"]))
    story.append(p("El objetivo se cumplió: la aplicación emite las tres señales, el Collector centraliza su procesamiento, Jaeger permite analizar la traza completa, Prometheus alimenta el dashboard y Loki conserva logs JSON correlacionables. El trace_id se mantiene entre service-a, service-b, PostgreSQL y los logs asociados.", styles["BodyEs"]))
    story.append(p("La evidencia local evita costos de GCP y AWS. El diseño cloud queda representado en infra/gcp y infra/aws para una eventual migración a GKE y ECS Fargate, pero no se aplicó infraestructura durante esta entrega.", styles["BodyEs"]))
    story.append(p("Limitaciones", styles["H2Blue"]))
    story.append(p("Jaeger utiliza memoria y no representa alta disponibilidad ni retención productiva. El benchmark se ejecutó sobre Docker Desktop y la medición de CPU depende del host Windows. Para producción se requerirían TLS, autenticación OTLP, gestión de secretos, retención, alertas, escalamiento y pruebas con una infraestructura representativa.", styles["BodyEs"]))
    story.append(p("Comandos principales de reproducción", styles["H2Blue"]))
    story.append(Preformatted("""docker compose up -d --build
Invoke-RestMethod http://localhost:8000/order/ord-001
docker compose ps
docker compose logs --since=5m --no-color otel-collector
py benchmark/analyze_overhead.py""", styles["CodeSmall"]))
    story.append(p("Artefactos incluidos", styles["H2Blue"]))
    artifacts = [
        "docker-compose.yaml y docker-compose.baseline.yaml",
        "service-a/, service-b/ y scripts/init-db.sql",
        "otel-collector/collector-config.yaml",
        "prometheus/, grafana/ y loki/",
        "evidence/ con JSON, transcripciones y explicaciones Markdown",
        "screenshots/ con trazas, dashboard, logs y Prometheus",
        "benchmark/raw/ con los resultados JSON",
        "infra/gcp/ e infra/aws/ con parametrización Terraform",
    ]
    for artifact in artifacts:
        story.append(p("- " + artifact, styles["BodyEs"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(p("Conclusión final", styles["H2Blue"]))
    story.append(p("OpenTelemetry aporta visibilidad integral y correlación entre señales a cambio de un overhead medible. En este laboratorio el costo principal se refleja en latencia y throughput, mientras que la memoria adicional es reducida y la tasa de errores se mantiene en cero. La capacidad de recorrer una incidencia desde Grafana o un log hasta una traza completa mejora la resiliencia y la capacidad de diagnóstico del sistema.", styles["BodyEs"]))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E1F2"))
        canvas.line(1.7 * cm, 1.15 * cm, A4[0] - 1.7 * cm, 1.15 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.7 * cm, 0.75 * cm, "otel-observability-lab - reporte técnico")
        canvas.drawRightString(A4[0] - 1.7 * cm, 0.75 * cm, f"Página {doc_obj.page}")
        canvas.restoreState()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
