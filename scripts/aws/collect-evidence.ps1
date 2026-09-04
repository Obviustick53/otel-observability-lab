[CmdletBinding()]
param(
    [string]$EvidenceDirectory = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment'),
    [string[]]$IncludeFile = @('preflight.json', 'cost-estimate.json', 'template-validation.json', 'cloudformation-plan.json', 'smoke-evidence.json'),
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\..\screenshoot\integrator_project\05_aws_deployment\evidence-manifest.aws.json')
)
. (Join-Path $PSScriptRoot 'common.ps1')
$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$files = @(Get-ChildItem -LiteralPath $EvidenceDirectory -File | Where-Object { $_.FullName -ne $outputFullPath -and $_.Name -in $IncludeFile })
$artifacts = foreach ($file in $files) {
    [pscustomobject]@{
        rubricCriterion = 'AWS preflight, IaC, seguridad y veracidad'
        evidenceType = 'artifact'
        environment = 'AWS sandbox (no ejecutado)'
        commandOrScript = 'scripts/aws/collect-evidence.ps1'
        generatedAtUtc = $file.LastWriteTimeUtc.ToString('o')
        observedResult = 'Artefacto de preparación; no prueba despliegue cloud.'
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        file = $file.Name
        status = 'NO EJECUTADO'
        limitations = @('No se desplegaron recursos AWS.', 'No se consultaron secretos plaintext.')
    }
}
Write-SafeJson -Value ([pscustomobject]@{ generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o'); scope = '05_aws_deployment'; artifacts = $artifacts }) -Path $OutputPath
Write-Output "Manifiesto AWS guardado en $OutputPath"
