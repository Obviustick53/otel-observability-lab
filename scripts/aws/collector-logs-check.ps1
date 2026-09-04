[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ProjectName,
    [string]$Environment = 'sandbox',
    [string]$Profile = $env:AWS_PROFILE,
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\collector-logs-evidence-final.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
$context = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$startTime = [DateTimeOffset]::UtcNow.AddMinutes(-20).ToUnixTimeMilliseconds()
$logGroup = "/aws/ecs/$ProjectName/$Environment/otel-collector"
$errors = Invoke-AwsJson -CommandArgs @('logs', 'filter-log-events', '--log-group-name', $logGroup, '--start-time', [string]$startTime, '--filter-pattern', 'UNIMPLEMENTED', '--output', 'json') -Region $ExpectedRegion -Profile $Profile
$received = Invoke-AwsJson -CommandArgs @('logs', 'filter-log-events', '--log-group-name', $logGroup, '--start-time', [string]$startTime, '--filter-pattern', 'LogsExporter', '--output', 'json') -Region $ExpectedRegion -Profile $Profile
$errorEvents = @($errors.events)
$receivedEvents = @($received.events)
$evidence = [pscustomobject]@{
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    context = $context
    logGroup = $logGroup
    windowMinutes = 20
    status = if ($receivedEvents.Count -gt 0 -and $errorEvents.Count -eq 0) { 'VERIFIED' } else { 'PARTIAL' }
    otlpLogsExporterEvents = $receivedEvents.Count
    unimplementedEvents = $errorEvents.Count
}
Write-SafeJson -Value $evidence -Path $OutputPath
Write-Output "Verificacion de logs del collector guardada en $OutputPath"
