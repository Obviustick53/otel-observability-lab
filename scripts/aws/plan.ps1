[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ParametersFile,
    [string]$Profile = $env:AWS_PROFILE,
    [switch]$CreateChangeSet,
    [switch]$MutationAuthorized,
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\cloudformation-plan.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
if ($CreateChangeSet -and -not $MutationAuthorized) { throw 'Crear un change set requiere -MutationAuthorized; no se ejecuta por defecto.' }
$defs = Get-StackDefinitions -ParametersFile $ParametersFile
$params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
$tagArgs = @("Project=$($params.ProjectName)", "Environment=$($params.Environment)", "Owner=$($params.Owner)", "ExpiresOn=$($params.ExpirationUtc)")
$commands = foreach ($stack in $defs) {
    $overrides = Get-ParameterOverridesForStack -ParametersFile $ParametersFile -StackKey $stack.Key
    $displayArgs = @('cloudformation', 'deploy', '--template-file', $stack.Template, '--stack-name', $stack.Name, '--capabilities', 'CAPABILITY_NAMED_IAM', '--no-fail-on-empty-changeset', '--parameter-overrides') + $overrides + @('--tags') + $tagArgs
    if ($CreateChangeSet) { $displayArgs += '--no-execute-changeset' }
    [pscustomobject]@{ layer = $stack.Key; stackName = $stack.Name; command = 'aws ' + (($displayArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' ') }
}
if ($CreateChangeSet) {
    $null = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
    foreach ($stack in $defs) {
        $overrides = Get-ParameterOverridesForStack -ParametersFile $ParametersFile -StackKey $stack.Key
        $args = @('cloudformation', 'deploy', '--template-file', $stack.Template, '--stack-name', $stack.Name, '--capabilities', 'CAPABILITY_NAMED_IAM', '--no-fail-on-empty-changeset', '--no-execute-changeset', '--parameter-overrides') + $overrides + @('--tags') + $tagArgs
        Invoke-AwsText -CommandArgs $args -Region $ExpectedRegion -Profile $Profile | Out-Null
    }
}
$payload = [pscustomobject]@{
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    mode = if ($CreateChangeSet) { 'change-set-created-no-execute' } else { 'preview-only' }
    region = $ExpectedRegion
    expectedAccountId = $ExpectedAccountId
    stacks = $commands
    note = 'Preview-only no cambia AWS. Un change set es una mutación de control-plane y requiere autorización explícita.'
}
Write-SafeJson -Value $payload -Path $OutputPath
Write-Output "Plan guardado en $OutputPath"
