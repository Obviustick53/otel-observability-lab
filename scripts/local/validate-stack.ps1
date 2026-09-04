[CmdletBinding()]
param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$evidenceDir = Join-Path $repoRoot "screenshoot\integrator_project\01_architecture_otel"
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

$checks = [System.Collections.Generic.List[object]]::new()
function Add-Check {
    param([string]$Name, [string]$Status, [string]$Detail)
    $checks.Add([ordered]@{ name = $Name; status = $Status; detail = $Detail })
}

try {
    $jsonFiles = @(Get-ChildItem (Join-Path $repoRoot "grafana") -Filter "*.json" -Recurse)
    foreach ($file in $jsonFiles) {
        Get-Content -Raw $file.FullName | ConvertFrom-Json | Out-Null
        Add-Check "JSON $($file.Name)" "PASS" "ConvertFrom-Json"
    }

    $rulesText = Get-Content -Raw (Join-Path $repoRoot "prometheus\rules\observability.rules.yml")
    if ($rulesText -notmatch "offset 5m" -or $rulesText -notmatch "baseline_sigma") {
        throw "El baseline no contiene la ventana offset y sigma esperadas."
    }
    if ($rulesText -match "(?im)trace_id\s*:") {
        throw "trace_id aparece como label/clave de regla; debe resolverse por logs o exemplars."
    }
    Add-Check "Baseline dinámico" "PASS" "30m con offset 5m y media/sigma; sin trace_id como label"

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        Add-Check "docker compose config" "NOT_EXECUTED" "Docker no está disponible en PATH"
    } else {
        & docker compose -f (Join-Path $repoRoot "docker-compose.yaml") config --quiet
        if ($LASTEXITCODE -ne 0) { throw "docker compose config falló con código $LASTEXITCODE." }
        Add-Check "docker compose config" "PASS" "Configuración base válida"
        & docker compose -f (Join-Path $repoRoot "docker-compose.yaml") --profile data-service config --quiet
        if ($LASTEXITCODE -ne 0) { throw "docker compose --profile data-service config falló con código $LASTEXITCODE." }
        Add-Check "docker compose --profile data-service config" "PASS" "Configuración compatible; data-service se construye desde ./data-service"

        if ($Start) {
            & docker compose -f (Join-Path $repoRoot "docker-compose.yaml") up -d
            if ($LASTEXITCODE -ne 0) {
                Add-Check "Stack local" "BLOCKED" "Docker daemon rechazó up -d con código $LASTEXITCODE; no se modificaron volúmenes."
            } else {
                $deadline = (Get-Date).AddMinutes(3)
                $healthy = $false
                do {
                    Start-Sleep -Seconds 5
                    $psOutput = & docker compose -f (Join-Path $repoRoot "docker-compose.yaml") ps --format json
                    if ($LASTEXITCODE -eq 0 -and $psOutput) {
                        $rows = @($psOutput | ConvertFrom-Json)
                        $healthy = $true
                        foreach ($row in $rows) {
                            if ($row.State -notmatch "running|restarting" -or ($row.Health -and $row.Health -notmatch "healthy")) {
                                $healthy = $false
                            }
                        }
                    }
                } while (-not $healthy -and (Get-Date) -lt $deadline)
                $statusText = (& docker compose -f (Join-Path $repoRoot "docker-compose.yaml") ps | Out-String)
                $stackStatus = if ($healthy) { "PASS" } else { "PARTIAL" }
                Add-Check "Stack local" $stackStatus ("Se ejecutó up -d sin down ni eliminación de volúmenes." + [Environment]::NewLine + $statusText)
            }
        }
    }

    $overall = if (($checks | Where-Object { $_.status -in @("FAIL", "PARTIAL", "BLOCKED") }).Count -gt 0) { "PARTIAL" } else { "PASS" }
} catch {
    Add-Check "Validación" "FAIL" $_.Exception.Message
    $overall = "FAIL"
}

$result = [ordered]@{
    evidence = "Agente C — validación local de arquitectura OTel"
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    environment = "local"
    command = "scripts/local/validate-stack.ps1$(if ($Start) { ' -Start' })"
    result = $overall
    checks = $checks
    limitations = @(
        "Las métricas de seguridad son locales/simuladas y no representan VPC Flow Logs, CloudTrail ni Security Hub.",
        "data-service se ejecuta desde su Dockerfile local y expone el contrato HTTP de inventario.",
        "No se ejecutó AWS."
    )
}
$evidencePath = Join-Path $evidenceDir "agent-c-validation.json"
$result | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $evidencePath
$result | ConvertTo-Json -Depth 8
if ($overall -in @("FAIL", "PARTIAL")) { exit 1 }
