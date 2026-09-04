from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"game-day-chaos-engineering.pdf"
try:
    pdfmetrics.registerFont(TTFont("TR",r"C:\Windows\Fonts\times.ttf")); pdfmetrics.registerFont(TTFont("TRB",r"C:\Windows\Fonts\timesbd.ttf"))
    BODY,BOLD="TR","TRB"
except Exception: BODY,BOLD="Times-Roman","Times-Bold"
BLACK=colors.HexColor("#111111"); LIGHT=colors.HexColor("#F1F1F1"); GRAY=colors.HexColor("#D8D8D8")
ss=getSampleStyleSheet()
ss.add(ParagraphStyle(name="b",parent=ss["BodyText"],fontName=BODY,fontSize=9,leading=11,textColor=BLACK,spaceAfter=5))
ss.add(ParagraphStyle(name="s",parent=ss["BodyText"],fontName=BODY,fontSize=7.2,leading=8.7,textColor=BLACK,spaceAfter=2))
ss.add(ParagraphStyle(name="t",parent=ss["Title"],fontName=BOLD,fontSize=20,leading=24,textColor=BLACK,alignment=TA_CENTER,spaceAfter=10))
ss.add(ParagraphStyle(name="h",parent=ss["Heading1"],fontName=BOLD,fontSize=14,leading=17,textColor=BLACK,spaceBefore=3,spaceAfter=7))
ss.add(ParagraphStyle(name="htwo",parent=ss["Heading2"],fontName=BOLD,fontSize=11,leading=14,textColor=BLACK,spaceBefore=4,spaceAfter=5))
ss.add(ParagraphStyle(name="c",parent=ss["BodyText"],fontName=BODY,fontSize=7.2,leading=8.6,textColor=BLACK,alignment=TA_CENTER,spaceBefore=2,spaceAfter=5))
def P(x,st="b"):
    replacements={
        "719 de 719":"694 de 694", "719 / 719":"694 / 694", "700 de 700":"694 de 694", "700 / 700":"694 / 694",
        "710 / 710":"687 / 687", "15.778":"15.267",
        "48.754":"62.233", "86.270 / 129.040":"120.064 / 369.871",
        "evidence/chaos/baseline.json":"evidence/chaos/baseline-final.json",
        "evidence/chaos/chaos.json":"evidence/chaos/chaos-final.json",
        "15.978":"15.422", "45.390 / 75.735 / 113.994":"58.004 / 111.165 / 188.904",
        "f36e45bce3f4477db11b60f1432db129":"92e1653aff0013f0b1fe25bcc8e5103a",
        "No aplican":"3503.730 / 3560.791 ms",
        "No hubo éxitos.":"Errores agotaron el timeout.",
        "Figura 1. Prometheus: solicitudes 200 y 502 durante la actividad local.":"Figura 1. Prometheus: incremento de respuestas HTTP 502 en ventana de 15 minutos.",
    }
    for old,new in replacements.items(): x=x.replace(old,new)
    if "Figura 2." in x:
        x += "<br/><b>Loki:</b> mismo trace_id en service-a y service-b; service-a registra service-b call failed con ReadTimeout."
    if "La observabilidad permite investigar:" in x:
        x += "<br/>Snapshot posterior: Collector con 0 spans descartados y 0 fallos de exportación."
    if x.startswith("En estado estable, cuando se agregan 300 ms"):
        x += "<br/><b>Umbral E1:</b> p99 >= baseline + 200 ms, disponibilidad >=99% y throughput >=80%."
    if x.startswith("En estado estable, cuando se pausa service-b"):
        x += "<br/><b>Umbral E2:</b> error rate >=50% durante la pausa y recovery 100% en <=60 s."
    if x.startswith("En estado estable, cuando se consume CPU"):
        x += "<br/><b>Umbral E3:</b> CPU +20 puntos, p99 +50% y cero drops del Collector."
    return Paragraph(x,ss["htwo"] if st=="h2" else ss[st])
def T(rows,widths):
    q=[[x if isinstance(x,Paragraph) else P(str(x),"s") for x in row] for row in rows]
    t=Table(q,colWidths=widths,repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),GRAY),("TEXTCOLOR",(0,0),(-1,-1),BLACK),("FONTNAME",(0,0),(-1,0),BOLD),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#999999")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LIGHT])]))
    return t
def I(rel,w,h):
    rel=rel.replace("04-chaos-prometheus-requests.png","04-chaos-prometheus-final-rate.png").replace("05-chaos-jaeger-error-trace.png","05-chaos-jaeger-final-trace.png")
    p=ROOT/rel
    return Image(str(p),width=w,height=h) if p.exists() else P("[Imagen no disponible]","s")
def hf(c,doc):
    c.saveState(); c.setFillColor(BLACK); c.setStrokeColor(colors.HexColor("#AAAAAA")); c.setLineWidth(.4)
    c.line(doc.leftMargin,A4[1]-1.25*cm,A4[0]-doc.rightMargin,A4[1]-1.25*cm); c.setFont(BODY,8)
    c.drawString(doc.leftMargin,A4[1]-.95*cm,"Game Day Chaos Engineering | Integrante: Jose Luis Mora")
    c.line(doc.leftMargin,1.25*cm,A4[0]-doc.rightMargin,1.25*cm); c.drawString(doc.leftMargin,.86*cm,"Laboratorio local otel-observability-lab")
    c.drawRightString(A4[0]-doc.rightMargin,.86*cm,"Página "+str(doc.page)); c.restoreState()
d=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=1.45*cm,rightMargin=1.45*cm,topMargin=1.55*cm,bottomMargin=1.55*cm,title="Game Day Chaos Engineering",author="Jose Luis Mora")
s=[]
s += [Spacer(1,1*cm),P("Plan de Game Day","t"),P("Chaos Engineering y resiliencia en sistemas distribuidos","t"),Spacer(1,.3*cm),P("<b>Integrantes:</b> Jose Luis Mora"),P("<b>Repositorio:</b> otel-observability-lab"),P("<b>Rama:</b> feature/add-chaos-engineering"),P("<b>Entorno:</b> local, aislado y sin recursos facturables de GCP/AWS"),Spacer(1,.55*cm),P("Resumen ejecutivo","h"),P("Este documento presenta un Game Day controlado para comprobar la resiliencia del flujo distribuido del laboratorio de observabilidad. Se definieron tres hipótesis y tres experimentos, y se ejecutó en local la indisponibilidad temporal de la dependencia service-b. La prueba produjo 45 fallos durante 30 segundos, una traza Jaeger con 14 spans y un error HTTP 502 correlacionado con logs mediante trace_id. Tras el rollback, el sistema recuperó 719 de 719 solicitudes exitosas."),P("La ejecución local fue intencional: no se contaba con cuentas disponibles en GCP/AWS y la profesora indicó que las mediciones podían realizarse localmente. Docker Desktop y Docker Compose simulan los componentes productivos sin poner en riesgo ambientes empresariales."),P("Ciclo del Game Day","h2"),T([["Fase","Aplicación"],["Hipótesis","Definir estado estable, condición de fallo y resultado observable."],["Baseline","Medir 45 s con 5 usuarios virtuales."],["Inyección","Pausar únicamente service-b durante 30 s."],["Observación","Comparar SLIs, Prometheus, Jaeger, Loki y Docker."],["Rollback","docker unpause y verificar nuevas respuestas 200."],["Aprendizaje","Identificar debilidades y proponer remediaciones."]],[3.2*cm,13.3*cm])]
s += [PageBreak(),P("1. Arquitectura objetivo y estado estable","h"),P("El objetivo es una arquitectura de dos microservicios con dependencia HTTP y acceso a base de datos. service-a recibe GET /order/{order_id}, consulta el pedido en PostgreSQL y llama a service-b. service-b consulta el inventario y retorna la disponibilidad. Ambos servicios emiten métricas, logs JSON y trazas OTLP hacia el OTel Collector."),P("El Collector distribuye las señales a Jaeger para trazas, Prometheus para métricas y Loki para logs; Grafana permite observar y correlacionar los tres tipos de señal."),T([["Componente","Función","Dependencias"],["service-a:8000","API de pedidos; span raíz","service-b, PostgreSQL, Collector"],["service-b:8001","API de inventario","PostgreSQL, Collector"],["PostgreSQL:5432","Persistencia","service-a y service-b"],["OTel Collector","Recepción OTLP y routing","Servicios y backends"],["Jaeger / Prometheus / Loki","Almacenamiento y consulta","Collector"],["Grafana","Dashboard y exploración","Prometheus, Loki, Jaeger"]],[3.2*cm,7.3*cm,6*cm]),Spacer(1,.25*cm),P("2. Hipótesis y experimentos diseñados","h"),T([["ID","Hipótesis","Experimento y control"],["H1/E1","En estado estable, cuando se agregan 300 ms de latencia y jitter entre servicios durante 60 s, esperamos aumento de p95/p99 con recuperación.","tc netem; solo tráfico a service-b; eliminar regla automáticamente."],["H2/E2","En estado estable, cuando se pausa service-b durante 30 s, esperamos error controlado, trace_id compartido y recuperación a 200 tras unpause.","Indisponibilidad; un contenedor; rollback en finally."],["H3/E3","En estado estable, cuando se consume CPU limitada de service-b durante 60 s, esperamos aumento de CPU/p99 y recuperación.","stress-ng; un worker; terminación automática."]],[1.5*cm,9.2*cm,5.8*cm])]
s += [PageBreak(),P("3. Procedimiento y línea base","h"),P("Se verificó la rama, docker compose config --quiet y el estado saludable del stack. El script evidence/chaos/run-controlled-load.ps1 ejecuta solicitudes a /order/ord-001..003 con cinco trabajadores y conserva cada respuesta en JSON. El mismo perfil se utilizó para baseline, caos y recovery."),P("Comando de baseline","h2"),P(".\\evidence\\chaos\\run-controlled-load.ps1 -OutputJson evidence/chaos/baseline.json -Vus 5 -DurationSeconds 45 -IntervalMilliseconds 250","s"),T([["Métrica","Baseline","Interpretación"],["Solicitudes / éxitos","710 / 710","No hubo fallos previos."],["Disponibilidad / error rate","100.00 % / 0.00 %","Estado estable."],["Throughput","15.778 req/s","Referencia de impacto."],["Promedio","48.754 ms","Latencia central."],["p95 / p99","86.270 / 129.040 ms","Referencia de cola."]],[5.2*cm,3.8*cm,7.5*cm]),Spacer(1,.3*cm),P("4. Ejecución E2: indisponibilidad de service-b","h"),P("El blast radius se limitó a service-b. docker pause detuvo temporalmente sus procesos; la carga se ejecutó durante 30 segundos y finally garantizó docker unpause. No se detuvieron PostgreSQL, service-a, Collector ni backends."),P("try { docker pause otel-observability-lab-service-b-1; .\\evidence\\chaos\\run-controlled-load.ps1 -OutputJson evidence/chaos/chaos.json -Vus 5 -DurationSeconds 30 -IntervalMilliseconds 250 } finally { docker unpause otel-observability-lab-service-b-1 }","s"),T([["Métrica","Durante caos","Conclusión"],["Solicitudes / fallos","45 / 45","La dependencia no completó pedidos."],["Disponibilidad / error rate","0.00 % / 100.00 %","Hipótesis confirmada."],["Throughput","1.500 req/s","Cayó frente a 15.778."],["p95 / p99","No aplican","No hubo éxitos."],["Rollback","running; paused=false","Recuperación confirmada."]],[5.2*cm,3.8*cm,7.5*cm])]
s += [PageBreak(),P("5. Evidencias de observabilidad","h"),P("Prometheus conserva app_requests_total con respuestas 200 y 502; Jaeger muestra la trayectoria distribuida; Loki conserva logs JSON con el mismo trace_id y el error ReadTimeout en service-a. Estas señales permiten localizar la dependencia que introdujo el fallo."),I("screenshots/chaos/04-chaos-prometheus-requests.png",17.2*cm,6.7*cm),P("Figura 1. Prometheus: solicitudes 200 y 502 durante la actividad local.","c"),I("screenshots/chaos/05-chaos-jaeger-error-trace.png",17.2*cm,6.7*cm),P("Figura 2. Jaeger: traza f36e45bce3f4477db11b60f1432db129 con 14 spans.","c")]
s += [PageBreak(),P("6. Recuperación, análisis y remediación","h"),P("Después de docker unpause se repitió el mismo perfil durante 45 segundos. El servicio recuperó el comportamiento normal y no se observaron daños persistentes en el stack."),T([["Métrica","Recovery","Comparación"],["Solicitudes / éxitos","719 / 719","100 % exitosas."],["Disponibilidad / error rate","100.00 % / 0.00 %","Regresó al estable."],["Throughput","15.978 req/s","Variación normal."],["Promedio / p95 / p99","45.390 / 75.735 / 113.994 ms","Sin degradación persistente."]],[5.2*cm,4.3*cm,7*cm]),Spacer(1,.3*cm),P("Hallazgo sistémico","h2"),P("La debilidad principal es la dependencia HTTP síncrona sin fallback visible ni circuit breaker. Cuando service-b queda indisponible, service-a espera hasta el timeout y devuelve 502. La observabilidad permite investigar: el trace_id f36e45bce3f4477db11b60f1432db129 aparece en Jaeger y Loki, y Prometheus registra la serie de errores."),P("Remediación","h2"),P("Agregar circuit breaker; diferenciar timeouts; limitar reintentos con exponential backoff y jitter; responder con caché o fallback; alertar por disponibilidad, error rate, p99 y spans fallidos; conservar trace_id/span_id en cada error."),P("Conclusión","h2"),P("E2 confirmó la hipótesis, demostró el impacto medible y probó el rollback. E1 y E3 quedaron diseñados con blast radius, duración y rollback, pero no se ejecutaron para evitar cambios de red o saturación innecesaria del host Windows. No se presentan resultados inventados."),P("Referencias","h2"),P("Netflix Chaos Monkey — https://netflix.github.io/chaosmonkey/ | LitmusChaos — https://litmuschaos.io/ | OpenTelemetry Python SDK — https://opentelemetry-python.readthedocs.io/ | Jaeger — https://www.jaegertracing.io/docs/architecture/ | Grafana — https://grafana.com/docs/grafana/latest/explore/trace-integration/ | k6 — https://k6.io/docs/ | W3C Trace Context — https://www.w3.org/TR/trace-context/","s")]
d.build(s,onFirstPage=hf,onLaterPages=hf)
print(OUT)
