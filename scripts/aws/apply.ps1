[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ParametersFile,
    [string]$Profile = $env:AWS_PROFILE,
    [switch]$ApplyAuthorized,
    [string]$ConfirmedByUser,
    [string]$PlanFile = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\cloudformation-plan.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $ApplyAuthorized -or $ConfirmedByUser -ne 'I_HAVE_REVIEWED_COST_AND_PLAN') {
    throw 'Apply bloqueado. Requiere -ApplyAuthorized y ConfirmedByUser=I_HAVE_REVIEWED_COST_AND_PLAN.'
}
if (-not (Test-Path -LiteralPath $PlanFile)) { throw "Falta el plan revisado: $PlanFile" }
$null = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$defs = Get-StackDefinitions -ParametersFile $ParametersFile
$params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
$tagArgs = @("Project=$($params.ProjectName)", "Environment=$($params.Environment)", "Owner=$($params.Owner)", "ExpiresOn=$($params.ExpirationUtc)")
foreach ($stack in $defs) {
    if ($PSCmdlet.ShouldProcess($stack.Name, 'aws cloudformation deploy')) {
        $overrides = Get-ParameterOverridesForStack -ParametersFile $ParametersFile -StackKey $stack.Key
        $args = @('cloudformation', 'deploy', '--template-file', $stack.Template, '--stack-name', $stack.Name, '--capabilities', 'CAPABILITY_NAMED_IAM', '--no-fail-on-empty-changeset', '--parameter-overrides') + $overrides + @('--tags') + $tagArgs
        Invoke-AwsText -CommandArgs $args -Region $ExpectedRegion -Profile $Profile | Out-Null
    }
}
