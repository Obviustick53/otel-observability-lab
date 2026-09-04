[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ProjectName,
    [string]$Environment = 'sandbox',
    [string]$Profile = $env:AWS_PROFILE,
    [string]$BaseUrl,
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\smoke-evidence.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
$context = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$cluster = "$ProjectName-$Environment"
$services = @('service-a', 'service-b', 'data-service', 'otel-collector')
$serviceResults = foreach ($service in $services) {
    try {
        $detail = Invoke-AwsJson -CommandArgs @('ecs', 'describe-services', '--cluster', $cluster, '--services', $service, '--output', 'json') -Region $ExpectedRegion -Profile $Profile
        [pscustomobject]@{ service = $service; status = 'VERIFIED'; detail = $detail.services[0] }
    } catch { [pscustomobject]@{ service = $service; status = 'BLOCKED'; detail = $_.Exception.Message } }
}
$readouts = foreach ($readout in @(
    @{ Name = 'cloudwatch-alarms'; Args = @('cloudwatch', 'describe-alarms', '--alarm-name-prefix', "$ProjectName-$Environment-", '--output', 'json') },
    @{ Name = 'flow-logs'; Args = @('ec2', 'describe-flow-logs', '--filter', "Name=tag:Project,Values=$ProjectName", '--output', 'json') },
    @{ Name = 'securityhub'; Args = @('securityhub', 'get-findings', '--max-results', '1', '--output', 'json') },
    @{ Name = 'cloudtrail'; Args = @('cloudtrail', 'describe-trails', '--trail-name-list', "$ProjectName-$Environment-trail", '--output', 'json') },
    @{ Name = 'xray-service-graph'; Args = @('xray', 'get-service-graph', '--start-time', (Get-Date).ToUniversalTime().AddMinutes(-15).ToString('o'), '--end-time', (Get-Date).ToUniversalTime().ToString('o'), '--output', 'json') }
)) {
    try { [pscustomobject]@{ check = $readout.Name; status = 'VERIFIED'; detail = Invoke-AwsJson -CommandArgs $readout.Args -Region $ExpectedRegion -Profile $Profile } }
    catch { [pscustomobject]@{ check = $readout.Name; status = 'BLOCKED_OR_NOT_ENABLED'; detail = $_.Exception.Message } }
}
$http = if ($BaseUrl) {
    try { $r = Invoke-WebRequest -Uri "$($BaseUrl.TrimEnd('/'))/health" -UseBasicParsing; [pscustomobject]@{ status = 'VERIFIED'; httpStatus = [int]$r.StatusCode; body = $r.Content } }
    catch { [pscustomobject]@{ status = 'FAILED'; detail = $_.Exception.Message } }
} else { [pscustomobject]@{ status = 'NOT_EXECUTED'; detail = 'BaseUrl no provisto; no se inventa una solicitud real.' } }
$business = if ($BaseUrl) {
    try { $r = Invoke-WebRequest -Uri "$($BaseUrl.TrimEnd('/'))/order/ord-1001" -UseBasicParsing; [pscustomobject]@{ status = 'VERIFIED'; httpStatus = [int]$r.StatusCode; body = $r.Content } }
    catch { [pscustomobject]@{ status = 'FAILED'; detail = $_.Exception.Message } }
} else { [pscustomobject]@{ status = 'NOT_EXECUTED'; detail = 'BaseUrl no provisto; no se inventa una solicitud real.' } }
Write-SafeJson -Value ([pscustomobject]@{ generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o'); context = $context; services = $serviceResults; readouts = $readouts; httpSmoke = $http; businessSmoke = $business; limitation = 'Las pruebas HTTP se ejecutan contra BaseUrl cuando se proporciona; los demas readouts consultan AWS.' }) -Path $OutputPath
Write-Output "Smoke/evidencia guardado en $OutputPath"
