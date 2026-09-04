[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ParametersFile,
    [string]$Profile = $env:AWS_PROFILE,
    [switch]$CleanupAuthorized,
    [string]$ConfirmedByUser
)
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $CleanupAuthorized -or $ConfirmedByUser -ne 'I_HAVE_REVIEWED_COST_AND_PLAN') { throw 'Cleanup bloqueado hasta autorizacion explicita.' }
$null = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$defs = Get-StackDefinitions -ParametersFile $ParametersFile
$params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
$repositories = @("$($params.ProjectName)-$($params.Environment)-service-a", "$($params.ProjectName)-$($params.Environment)-service-b", "$($params.ProjectName)-$($params.Environment)-data-service", "$($params.ProjectName)-$($params.Environment)-otel-collector")
foreach ($repo in $repositories) {
    try {
        $images = Invoke-AwsJson -CommandArgs @('ecr', 'list-images', '--repository-name', $repo, '--filter', 'tagStatus=ANY', '--output', 'json') -Region $ExpectedRegion -Profile $Profile
        $ids = @($images.imageIds | Where-Object { $_.imageDigest } | ForEach-Object { "imageDigest=$($_.imageDigest)" })
        if ($ids.Count -gt 0 -and $PSCmdlet.ShouldProcess($repo, 'delete exact ECR images')) {
            Invoke-AwsText -CommandArgs (@('ecr', 'batch-delete-image', '--repository-name', $repo, '--image-ids') + $ids + @('--output', 'json')) -Region $ExpectedRegion -Profile $Profile | Out-Null
        }
    } catch { if ($_.Exception.Message -notmatch 'RepositoryNotFoundException') { throw } }
}
$deleteOrder = @('security', 'services', 'cost-guard', 'data', 'platform', 'network')
foreach ($stack in ($deleteOrder | ForEach-Object { $defs | Where-Object Key -eq $_ })) {
    if ($PSCmdlet.ShouldProcess($stack.Name, 'aws cloudformation delete-stack')) {
        Invoke-AwsText -CommandArgs @('cloudformation', 'delete-stack', '--stack-name', $stack.Name) -Region $ExpectedRegion -Profile $Profile | Out-Null
        Invoke-AwsText -CommandArgs @('cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $stack.Name) -Region $ExpectedRegion -Profile $Profile | Out-Null
    }
}
$residual = foreach ($stack in $defs) {
    try { Invoke-AwsJson -CommandArgs @('cloudformation', 'describe-stacks', '--stack-name', $stack.Name, '--output', 'json') -Region $ExpectedRegion -Profile $Profile | ForEach-Object { $stack.Name } }
    catch { if ($_.Exception.Message -notmatch 'does not exist|ValidationError') { throw } }
}
if ($residual) { throw "Cleanup incompleto; stacks residuales: $($residual -join ', ')" }
Write-Output 'Cleanup verificado para los stacks exactos; revisar y borrar snapshots RDS por separado si corresponde.'
