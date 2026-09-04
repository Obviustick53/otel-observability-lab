[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ProjectName,
    [string]$Environment = 'sandbox',
    [string]$Profile = $env:AWS_PROFILE,
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\migration-evidence.json'),
    [switch]$RunAuthorized,
    [string]$ConfirmedByUser
)
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $RunAuthorized -or $ConfirmedByUser -ne 'I_HAVE_REVIEWED_COST_AND_PLAN') {
    throw 'Migraciones bloqueadas hasta aprobacion explicita.'
}
$context = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$cluster = "$ProjectName-$Environment"
$exports = Invoke-AwsJson -CommandArgs @('cloudformation', 'list-exports', '--output', 'json') -Region $ExpectedRegion -Profile $Profile
function Get-ExportValue([string]$Name) {
    $match = @($exports.Exports | Where-Object { $_.Name -eq $Name }) | Select-Object -First 1
    if (-not $match) { throw "No se encontro el export $Name." }
    return [string]$match.Value
}
$subnets = @((Get-ExportValue "$ProjectName-$Environment-PublicSubnet1Id"), (Get-ExportValue "$ProjectName-$Environment-PublicSubnet2Id"))
$securityGroup = Get-ExportValue "$ProjectName-$Environment-DataServiceSecurityGroupId"
$taskDefinition = Invoke-AwsJson -CommandArgs @('ecs', 'describe-task-definition', '--task-definition', "$ProjectName-$Environment-data-service", '--output', 'json') -Region $ExpectedRegion -Profile $Profile
$taskDefinitionArn = [string]$taskDefinition.taskDefinition.taskDefinitionArn
$network = "awsvpcConfiguration={subnets=[$($subnets -join ',')],securityGroups=[$securityGroup],assignPublicIp=ENABLED}"
$overrides = @{ containerOverrides = @(@{ name = 'data-service'; command = @('python', 'migrate.py') }) } | ConvertTo-Json -Compress -Depth 5
if (-not $PSCmdlet.ShouldProcess($cluster, 'run ECS migration task')) { return }
$run = Invoke-AwsJson -CommandArgs @(
    'ecs', 'run-task', '--cluster', $cluster, '--task-definition', $taskDefinitionArn,
    '--launch-type', 'FARGATE', '--count', '1', '--network-configuration', $network,
    '--overrides', $overrides, '--output', 'json'
) -Region $ExpectedRegion -Profile $Profile
if (-not $run.tasks -or $run.tasks.Count -ne 1) { throw 'ECS no inicio exactamente una tarea de migracion.' }
$taskArn = [string]$run.tasks[0].taskArn
Invoke-AwsText -CommandArgs @('ecs', 'wait', 'tasks-stopped', '--cluster', $cluster, '--tasks', $taskArn) -Region $ExpectedRegion -Profile $Profile | Out-Null
$result = Invoke-AwsJson -CommandArgs @('ecs', 'describe-tasks', '--cluster', $cluster, '--tasks', $taskArn, '--output', 'json') -Region $ExpectedRegion -Profile $Profile
$task = $result.tasks[0]
$container = $task.containers | Where-Object { $_.name -eq 'data-service' } | Select-Object -First 1
$evidence = [pscustomobject]@{
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    context = $context
    taskDefinition = $taskDefinitionArn
    taskArn = $taskArn
    status = if ($container.exitCode -eq 0) { 'VERIFIED' } else { 'FAILED' }
    exitCode = $container.exitCode
    stoppedReason = $task.stoppedReason
    migrationCommand = 'python migrate.py'
}
Write-SafeJson -Value $evidence -Path $OutputPath
if ($container.exitCode -ne 0) { throw "La migracion termino con exit code $($container.exitCode)." }
Write-Output "Migracion verificada; evidencia guardada en $OutputPath"
