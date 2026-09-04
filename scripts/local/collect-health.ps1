[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$evidenceDir = Join-Path $repoRoot "screenshoot\integrator_project\01_architecture_otel"
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
$composeFile = Join-Path $repoRoot "docker-compose.yaml"
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [string]$Status, [string]$Detail)
    $checks.Add([ordered]@{ name = $Name; status = $Status; detail = $Detail })
}

function Check-Http {
    param([string]$Name, [string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri $Url
        Add-Check $Name "PASS" "$($response.StatusCode) $Url"
    } catch {
        Add-Check $Name "FAIL" "$Url :: $($_.Exception.Message)"
    }
}

try {
    Check-Http "Collector health endpoint" "http://localhost:13133/"
    Check-Http "Prometheus API" "http://localhost:9090/api/v1/status/config"
    Check-Http "Grafana API" "http://localhost:3000/api/health"
    Check-Http "Jaeger UI" "http://localhost:16686/"
    Check-Http "Loki readiness" "http://localhost:3100/ready"
    Check-Http "Security simulator" "http://localhost:9464/healthz"
    Check-Http "service-a health" "http://localhost:8000/health"
    Check-Http "service-b health" "http://localhost:8001/health"
    Check-Http "data-service health" "http://localhost:8002/health"

    $targets = Invoke-RestMethod "http://localhost:9090/api/v1/targets"
    $active = @($targets.data.activeTargets)
    $down = @($active | Where-Object { $_.health -ne "up" })
    Add-Check "Prometheus scrape targets" ($(if ($down.Count -eq 0) { "PASS" } else { "PARTIAL" })) "active=$($active.Count); down=$($down.Count)"

    $rules = Invoke-RestMethod "http://localhost:9090/api/v1/rules"
    $groups = @($rules.data.groups)
    $ruleCount = @($groups | ForEach-Object { $_.rules }).Count
    Add-Check "Prometheus recording/alert rules" "PASS" "groups=$($groups.Count); rules=$ruleCount"

    $promConfigOutput = & docker compose -f $composeFile exec -T prometheus promtool check config /etc/prometheus/prometheus.yml 2>&1 | Out-String
    Add-Check "promtool check config" ($(if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" })) $promConfigOutput.Trim()
    $rulesOutput = & docker compose -f $composeFile exec -T prometheus promtool check rules /etc/prometheus/rules/observability.rules.yml /etc/prometheus/rules/alerts.rules.yml 2>&1 | Out-String
    Add-Check "promtool check rules" ($(if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" })) $rulesOutput.Trim()
    $collectorOutput = & docker compose -f $composeFile exec -T otel-collector /otelcol-contrib validate --config=/etc/otelcol-contrib/config.yaml 2>&1 | Out-String
    Add-Check "Collector config validate" ($(if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" })) $collectorOutput.Trim()

    $overall = if (($checks | Where-Object { $_.status -eq "FAIL" }).Count -gt 0) { "PARTIAL" } else { "PASS" }
} catch {
    Add-Check "Runtime evidence" "FAIL" $_.Exception.Message
    $overall = "PARTIAL"
}

$result = [ordered]@{
    evidence = "Agente C — salud y validación runtime local"
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    environment = "local"
    command = "scripts/local/collect-health.ps1"
    result = $overall
    checks = $checks
    limitations = @(
        "La comprobación es local; no demuestra despliegue AWS.",
        "Las señales de seguridad/red son simuladas y están etiquetadas telemetry_scope=simulated.",
        "No se ejecutaron cambios destructivos ni se eliminaron volúmenes."
    )
}
$evidencePath = Join-Path $evidenceDir "agent-c-runtime-health.json"
$result | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $evidencePath
$result | ConvertTo-Json -Depth 8
if ($overall -ne "PASS") { exit 1 }
