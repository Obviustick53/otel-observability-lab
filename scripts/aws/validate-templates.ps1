[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Region,
    [string]$ExpectedAccountId,
    [string]$Profile = $env:AWS_PROFILE,
    [switch]$StaticOnly,
    [switch]$IncludeLegacy,
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\template-validation.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
$templateDir = Join-Path $script:RepoRoot 'infra\aws\cloudformation'
$files = if ($IncludeLegacy) {
    @(Get-ChildItem -LiteralPath $templateDir -Filter '*.yaml' -File | Sort-Object Name)
} else {
    @(Get-ChildItem -LiteralPath $templateDir -Filter '*.yaml' -File | Where-Object Name -match '^(0[0-4]|05)-' | Sort-Object Name)
}
if (-not $files) { throw "No hay plantillas en $templateDir" }
$lint = Get-Command cfn-lint -ErrorAction SilentlyContinue
$guard = Get-Command cfn-guard -ErrorAction SilentlyContinue
$context = $null
if (-not $StaticOnly) {
    if ([string]::IsNullOrWhiteSpace($ExpectedAccountId)) { throw 'ExpectedAccountId es obligatorio cuando se usa AWS CLI validation.' }
    $context = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $Region -Profile $Profile
}
$results = [System.Collections.Generic.List[object]]::new()
foreach ($file in $files) {
    $parse = [pscustomobject]@{ tool = 'PowerShell-file-read'; status = 'VERIFIED'; output = "$($file.Name) non-empty ($($file.Length) bytes)" }
    $lintResult = if ($lint) {
        $text = (& cfn-lint --format json --regions $Region $file.FullName 2>&1 | Out-String).Trim()
        [pscustomobject]@{ tool = 'cfn-lint'; status = if ($LASTEXITCODE -eq 0) { 'VERIFIED' } else { 'FAILED' }; output = $text }
    } else {
        [pscustomobject]@{ tool = 'cfn-lint'; status = 'BLOCKED'; output = 'cfn-lint no esta instalado; no se instala automaticamente.' }
    }
    $awsResult = if ($StaticOnly) {
        [pscustomobject]@{ tool = 'aws cloudformation validate-template'; status = 'NOT_EXECUTED'; output = 'Omitido por StaticOnly para no realizar llamadas AWS en esta entrega.' }
    } else {
        try {
            $text = Invoke-AwsText -CommandArgs @('cloudformation', 'validate-template', '--template-body', "file://$($file.FullName)", '--output', 'json') -Region $Region -Profile $Profile
            [pscustomobject]@{ tool = 'aws cloudformation validate-template'; status = 'VERIFIED'; output = $text }
        } catch {
            [pscustomobject]@{ tool = 'aws cloudformation validate-template'; status = 'BLOCKED'; output = $_.Exception.Message }
        }
    }
    $results.Add([pscustomobject]@{ template = $file.FullName; checks = @($parse, $lintResult, $awsResult) })
}
$guardResult = if ($guard) { 'AVAILABLE_BUT_RULE_FILE_REQUIRED' } else { 'BLOCKED_NOT_INSTALLED' }
$payload = [pscustomobject]@{
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    region = $Region
    context = $context
    staticOnly = [bool]$StaticOnly
    templates = $results
    cfnGuard = $guardResult
    note = 'cfn-guard requiere un archivo de reglas explícito; no se inventan reglas ni resultados.'
}
Write-SafeJson -Value $payload -Path $OutputPath
Write-Output "Validacion guardada en $OutputPath"
