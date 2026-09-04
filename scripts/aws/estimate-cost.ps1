[CmdletBinding()]
param(
    [int]$Hours = 8,
    [decimal]$OperationalLimitUsd = 40,
    [string]$AssumptionsFile = (Join-Path $PSScriptRoot '..\..\infra\aws\cost-assumptions.json'),
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\cost-estimate.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
if ($Hours -lt 1 -or $Hours -gt 720) { throw 'Hours debe estar entre 1 y 720.' }
if ($OperationalLimitUsd -le 0) { throw 'OperationalLimitUsd debe ser positivo.' }
$a = Get-Content -Raw -LiteralPath (Resolve-Path $AssumptionsFile) | ConvertFrom-Json

$fargateApp = $a.fargate.appTaskCount * (($a.fargate.appVcpu * $a.fargate.vcpuHourUsd) + ($a.fargate.appMemoryGb * $a.fargate.memoryGbHourUsd)) * $Hours
$fargateCollector = $a.fargate.collectorTaskCount * (($a.fargate.collectorVcpu * $a.fargate.vcpuHourUsd) + ($a.fargate.collectorMemoryGb * $a.fargate.memoryGbHourUsd)) * $Hours
$rdsInstance = $a.rds.instanceHourUsd * $Hours
$rdsStorage = $a.rds.allocatedStorageGb * $a.rds.storageGbMonthUsd / $a.rds.monthHours * $Hours
$logs = $a.cloudwatch.logsIngestGb * $a.cloudwatch.logsIngestGbUsd
$s3 = $a.s3.cloudTrailStorageGb * $a.s3.storageGbMonthUsd / 1
$total = [decimal]($fargateApp + $fargateCollector + $rdsInstance + $rdsStorage + $logs + $s3 + $a.cloudwatch.customMetricsUsd + $a.securityHub.estimateUsd)
$value = [pscustomobject]@{
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    asOfUtc = $a.asOfUtc
    currency = $a.currency
    regionBasis = $a.regionBasis
    hours = $Hours
    operationalLimitUsd = [math]::Round([double]$OperationalLimitUsd, 2)
    lineItems = [ordered]@{
        fargateApplication = [math]::Round([double]$fargateApp, 4)
        fargateCollector = [math]::Round([double]$fargateCollector, 4)
        rdsInstance = [math]::Round([double]$rdsInstance, 4)
        rdsStorage = [math]::Round([double]$rdsStorage, 4)
        cloudwatchLogs = [math]::Round([double]$logs, 4)
        cloudTrailS3Storage = [math]::Round([double]$s3, 4)
        customMetrics = [math]::Round([double]$a.cloudwatch.customMetricsUsd, 4)
        securityHub = [math]::Round([double]$a.securityHub.estimateUsd, 4)
    }
    estimatedTotalUsd = [math]::Round([double]$total, 4)
    underOperationalLimit = ($total -le $OperationalLimitUsd)
    status = if ($total -le $OperationalLimitUsd) { 'WITHIN_INPUT_LIMIT' } else { 'BLOCKED_OVER_LIMIT' }
    limitations = @($a.source, $a.securityHub.note, 'No es costo observado; no se consulto Cost Explorer y no se desplego AWS.')
}
Write-SafeJson -Value $value -Path $OutputPath
Write-Output "Estimacion guardada en $OutputPath"
