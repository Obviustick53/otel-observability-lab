[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [string]$Profile = $env:AWS_PROFILE,
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) '..\screenshoot\integrator_project\05_aws_deployment')
)
. (Join-Path $PSScriptRoot 'common.ps1')

$timestamp = (Get-Date).ToUniversalTime().ToString('o')
$results = [System.Collections.Generic.List[object]]::new()
$context = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile

$version = (& aws --version 2>&1 | Out-String).Trim()
$configureArgs = @('configure', 'list')
if ($Profile) { $configureArgs += @('--profile', $Profile) }
$configure = ConvertTo-RedactedText ((& aws @configureArgs 2>&1 | Out-String).Trim())
$results.Add([pscustomobject]@{ Check = 'aws-version'; Status = 'VERIFIED'; Detail = $version })
$results.Add([pscustomobject]@{ Check = 'identity-region'; Status = 'VERIFIED'; Detail = $context })
$results.Add([pscustomobject]@{ Check = 'aws-configure-list'; Status = 'VERIFIED'; Detail = $configure })

$probes = @(
    @{ Name = 'ecr-read'; Args = @('ecr', 'describe-repositories', '--max-items', '1', '--output', 'json') },
    @{ Name = 'ecs-read'; Args = @('ecs', 'list-clusters', '--max-items', '1', '--output', 'json') },
    @{ Name = 'rds-read'; Args = @('rds', 'describe-db-instances', '--max-records', '20', '--output', 'json') },
    @{ Name = 'cloudwatch-read'; Args = @('cloudwatch', 'list-metrics', '--max-items', '1', '--output', 'json') },
    @{ Name = 'service-quotas-ecs-read'; Args = @('service-quotas', 'list-service-quotas', '--service-code', 'ecs', '--max-items', '5', '--output', 'json') },
    @{ Name = 'service-quotas-rds-read'; Args = @('service-quotas', 'list-service-quotas', '--service-code', 'rds', '--max-items', '5', '--output', 'json') },
    @{ Name = 'budget-read'; Args = @('budgets', 'describe-budgets', '--account-id', $ExpectedAccountId, '--max-results', '1', '--output', 'json') },
    @{ Name = 'region-opt-in-status'; Args = @('ec2', 'describe-regions', '--region-names', $ExpectedRegion, '--all-regions', '--output', 'json') }
)
foreach ($probe in $probes) {
    try {
        $value = Invoke-AwsJson -CommandArgs $probe.Args -Region $ExpectedRegion -Profile $Profile
        $results.Add([pscustomobject]@{ Check = $probe.Name; Status = 'VERIFIED'; Detail = $value })
    } catch {
        $results.Add([pscustomobject]@{ Check = $probe.Name; Status = 'BLOCKED'; Detail = $_.Exception.Message })
    }
}

$payload = [pscustomobject]@{
    generatedAtUtc = $timestamp
    mode = 'read-only-preflight'
    context = $context
    results = $results
    safety = 'No se consulta ningun secreto y no se ejecutan operaciones mutantes.'
}
$out = Join-Path $OutputDirectory 'preflight.json'
Write-SafeJson -Value $payload -Path $out
Write-Output "Preflight guardado en $out"
