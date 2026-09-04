[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$evidenceDir = Join-Path $repoRoot "screenshoot\integrator_project\01_architecture_otel"
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [string]$Status, [object]$Observed)
    $checks.Add([ordered]@{ name = $Name; status = $Status; observed = $Observed })
}

function Invoke-SmokeRequest {
    param([string]$Name, [string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 15 -Uri $Url
        $body = $response.Content | ConvertFrom-Json
        Add-Check $Name "PASS" ([ordered]@{
            status_code = $response.StatusCode
            trace_id_present = [bool]$body.trace_id
            trace_id = if ($body.trace_id) { $body.trace_id } else { "unknown" }
        })
    } catch {
        Add-Check $Name "FAIL" $_.Exception.Message
    }
}

function Query-Prometheus {
    param([string]$Name, [string]$Query)
    try {
        $encoded = [Uri]::EscapeDataString($Query)
        $response = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$encoded"
        Add-Check $Name ($(if ($response.status -eq "success") { "PASS" } else { "FAIL" })) ([ordered]@{
            query = $Query
            result_type = $response.data.resultType
            series_count = @($response.data.result).Count
        })
    } catch {
        Add-Check $Name "FAIL" $_.Exception.Message
    }
}

try {
    Invoke-SmokeRequest "service-a request" "http://localhost:8000/order/ord-001"
    Invoke-SmokeRequest "service-b request" "http://localhost:8001/inventory/keyboard"
    Invoke-SmokeRequest "data-service request" "http://localhost:8002/data/ord-001"
    Start-Sleep -Seconds 8

    Query-Prometheus "RED service labels" "count by (service_name) (otel:request_rate_5m)"
    Query-Prometheus "Recording p99" "otel:p99_seconds_5m"
    Query-Prometheus "Dynamic baseline" "otel:error_rate_baseline_mean_30m"
    Query-Prometheus "Security simulated metrics" 'count(local_security_auth_failures_total{telemetry_scope="simulated"})'

    $jaeger = Invoke-RestMethod "http://localhost:16686/api/services"
    Add-Check "Jaeger service index" "PASS" ([ordered]@{ services = @($jaeger.data) })
    $loki = Invoke-RestMethod "http://localhost:3100/loki/api/v1/labels"
    Add-Check "Loki label index" "PASS" ([ordered]@{ labels = @($loki.data) })
    $dashboardFiles = @(Get-ChildItem (Join-Path $repoRoot "grafana\dashboards") -Filter "*.json")
    Add-Check "Grafana dashboard definitions" "PASS" ([ordered]@{ files = @($dashboardFiles.Name) })

    $overall = if (($checks | Where-Object { $_.status -eq "FAIL" }).Count -gt 0) { "PARTIAL" } else { "PASS" }
} catch {
    Add-Check "Smoke test" "FAIL" $_.Exception.Message
    $overall = "PARTIAL"
}

$result = [ordered]@{
    evidence = "Agente C — smoke de señales correlacionadas"
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    environment = "local"
    command = "scripts/local/smoke-observability.ps1"
    result = $overall
    checks = $checks
    limitations = @(
        "Los trace_id observados pertenecen a la respuesta/log y no se convierten en labels permanentes de métricas.",
        "Las métricas de seguridad/red son locales/simuladas.",
        "No se ejecutaron AWS ni experimentos de caos desde este script."
    )
}
$evidencePath = Join-Path $evidenceDir "agent-c-smoke-observability.json"
$result | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $evidencePath
$result | ConvertTo-Json -Depth 10
if ($overall -ne "PASS") { exit 1 }
