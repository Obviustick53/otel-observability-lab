[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Read-only delivery audit. This script intentionally does not invoke AWS, Docker,
# Terraform, package managers, or any Git command that changes repository state.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$excludedScanPaths = @(
    '.git',
    'docs/PROMPT_MAESTRO_AGENTES_OBSERVABILIDAD.md',
    'docs/DELIVERY_INVENTORY.md',
    'scripts/release/audit-delivery.ps1',
    'IMPLEMENTATION_GAME_DAY_CHAOS_ENGINEERING.md',
    'PLAN_GAME_DAY_CHAOS_ENGINEERING.md',
    'tools/create_game_day_pdf.py'
)
$findings = [System.Collections.Generic.List[object]]::new()

function Get-RelativePath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($repoRoot.Length).TrimStart('\', '/').Replace('\', '/')
    }
    return $full.Replace('\', '/')
}

function Add-Finding(
    [string]$Id,
    [ValidateSet('P0','P1','P2','INFO')][string]$Severity,
    [string]$Category,
    [string]$Path,
    [string]$Detail,
    [string]$Action
) {
    $findings.Add([pscustomobject]@{
        id = $Id
        severity = $Severity
        category = $Category
        path = $Path
        detail = $Detail
        action = $Action
    })
}

function Invoke-GitRead([string[]]$Arguments) {
    $output = & git @Arguments 2>&1
    [pscustomobject]@{
        output = @($output | ForEach-Object { $_.ToString() })
        exitCode = $LASTEXITCODE
    }
}

function Get-Classification([string]$Path) {
    if ($Path -eq 'screenshoot/integrator_project' -or $Path.StartsWith('screenshoot/integrator_project/')) {
        return 'EVIDENCIA_CANONICA'
    }
    if ($Path -eq 'evidence' -or $Path.StartsWith('evidence/') -or $Path -eq 'screenshots' -or $Path.StartsWith('screenshots/')) {
        return 'HISTORICO'
    }
    if ($Path -match '(^|/)(__pycache__|\.pytest_cache)(/|$)|\.pyc$|\.pyo$') {
        return 'GITIGNORE_EPHEMERAL'
    }
    if ($Path -match '^report/.*\.pdf$|^docs/guia-interactiva-observabilidad\.html$') {
        return 'GENERADO_ENTREGABLE'
    }
    return 'COMMIT_ACTIVO_CANDIDATO'
}

function Get-ResourceIds([string]$FilePath) {
    $insideResources = $false
    $ids = [System.Collections.Generic.List[string]]::new()
    foreach ($line in (Get-Content -LiteralPath $FilePath)) {
        if ($line -match '^Resources:\s*$') {
            $insideResources = $true
            continue
        }
        if ($insideResources -and $line -match '^[A-Za-z][A-Za-z0-9_-]*:\s*$') {
            $insideResources = $false
        }
        if ($insideResources -and $line -match '^  ([A-Za-z][A-Za-z0-9]+):\s*$') {
            $ids.Add($Matches[1])
        }
    }
    return @($ids | Sort-Object -Unique)
}

$status = Invoke-GitRead @('status', '--short', '--branch')
$branch = if ($status.output.Count -gt 0) { $status.output[0] } else { 'UNKNOWN' }
$statusEntries = @($status.output | Select-Object -Skip 1 | Where-Object { $_.Trim() -ne '' })
$trackedModified = @($statusEntries | Where-Object { $_ -notmatch '^\?\?' }).Count
$untracked = @($statusEntries | Where-Object { $_ -match '^\?\?' }).Count
$classificationCounts = @{}
foreach ($entry in $statusEntries) {
    $pathText = $entry.Substring(3).Trim()
    if ($pathText -match ' -> ') { $pathText = ($pathText -split ' -> ')[-1] }
    $classification = Get-Classification($pathText.Replace('\', '/'))
    if (-not $classificationCounts.ContainsKey($classification)) { $classificationCounts[$classification] = 0 }
    $classificationCounts[$classification]++
}

if ($status.exitCode -ne 0) {
    Add-Finding 'GIT-STATUS' 'P0' 'git' '.git' 'git status no pudo leerse.' 'Resolver el acceso al repositorio antes de preparar la rama.'
}

$diffCheck = Invoke-GitRead @('diff', '--check', '--', '.', ':(exclude)report/technical-report.pdf')
if ($diffCheck.exitCode -ne 0) {
    Add-Finding 'GIT-DIFF-CHECK' 'P1' 'git' 'working-tree' (($diffCheck.output -join ' ') + ' (se excluyó el PDF binario generado)') 'Corregir whitespace de fuentes antes del commit.'
}

$required = @(
    'docs/PROMPT_MAESTRO_AGENTES_OBSERVABILIDAD.md',
    'docker-compose.yaml',
    'infra/aws/cloudformation/00-network.yaml',
    'infra/aws/cloudformation/01-platform.yaml',
    'infra/aws/cloudformation/02-data.yaml',
    'infra/aws/cloudformation/03-services.yaml',
    'infra/aws/cloudformation/04-security-observability.yaml',
    'infra/aws/cloudformation/05-cost-guard.yaml',
    'screenshoot/integrator_project/evidence-manifest.json',
    'tests/chaos/test_measure.py',
    'tests/network_security/test_network_security_contracts.py'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relative))) {
        Add-Finding 'REQUIRED-MISSING' 'P0' 'required-file' $relative 'Falta un archivo exigido por la ruta de entrega.' 'Restaurar o regenerar el archivo desde una fuente verificable.'
    }
}

$manifestPath = Join-Path $repoRoot 'screenshoot/integrator_project/evidence-manifest.json'
if (Test-Path -LiteralPath $manifestPath) {
    try {
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
        $hashMismatches = 0
        foreach ($artifact in @($manifest.artifacts)) {
            $artifactPath = Join-Path $repoRoot ($artifact.path -replace '/', '\')
            if (-not (Test-Path -LiteralPath $artifactPath)) {
                Add-Finding 'EVIDENCE-MISSING' 'P1' 'evidence' $artifact.path 'El manifiesto referencia un artefacto inexistente.' 'Regenerar la evidencia o retirar la referencia del manifiesto.'
                continue
            }
            if ($artifact.sha256) {
                $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifactPath).Hash.ToLowerInvariant()
                if ($actualHash -ne $artifact.sha256.ToLowerInvariant()) {
                    $hashMismatches++
                    Add-Finding 'EVIDENCE-HASH' 'P1' 'evidence' $artifact.path 'El hash SHA-256 no coincide con el manifiesto.' 'No editar el artefacto a mano; regenerar manifiesto y evidencia desde el mismo comando.'
                }
            }
            if ($artifact.path -match '^(evidence|screenshots)[/\\]') {
                Add-Finding 'EVIDENCE-WRONG-ROOT' 'P1' 'evidence' $artifact.path 'La evidencia nueva está fuera de la carpeta canónica.' 'Conservarlo como histórico y enlazar la evidencia nueva desde screenshoot/integrator_project/.'
            }
        }
        $awsArtifacts = @($manifest.artifacts | Where-Object { $_.path -like 'screenshoot/integrator_project/05_aws_deployment/*' })
        $awsRequired = @(
            'screenshoot/integrator_project/05_aws_deployment/preflight.json',
            'screenshoot/integrator_project/05_aws_deployment/cloudformation-plan-live.json',
            'screenshoot/integrator_project/05_aws_deployment/smoke-evidence-final.json',
            'screenshoot/integrator_project/05_aws_deployment/budget-mcp-verification.json'
        )
        $awsMissing = @($awsRequired | Where-Object { -not (Test-Path -LiteralPath (Join-Path $repoRoot ($_ -replace '/', '\'))) })
        $awsContradiction = @($awsArtifacts | Where-Object { "$($_.status) $($_.environment)" -match 'NO EJECUTADO|BLOQUEADO|no ejecutado' })
        if (($manifest.execution_summary.aws_mutation_executed -eq $true -or "$($manifest.criteria | Where-Object id -eq 'C5' | Select-Object -ExpandProperty status)" -match 'DESPLEGADO') -and ($awsMissing.Count -gt 0 -or $awsContradiction.Count -gt 0)) {
            Add-Finding 'AWS-TRUTH-RECONCILE' 'P0' 'evidence-veracity' 'screenshoot/integrator_project/evidence-manifest.json' 'El manifiesto AWS activo no tiene la cadena mínima de evidencia o contiene estados contradictorios.' 'Regenerar preflight, plan, smoke y presupuesto desde el mismo entorno; conservar las limitaciones explícitas y no afirmar ejecución por inferencia.'
        }
    } catch {
        Add-Finding 'MANIFEST-JSON' 'P0' 'evidence' 'screenshoot/integrator_project/evidence-manifest.json' 'El manifiesto no es JSON válido.' 'Regenerar el manifiesto con el script canónico.'
    }
}

$scanExtensions = @('.md','.ps1','.py','.json','.yaml','.yml','.tf','.txt','.html')
$scanFiles = Get-ChildItem -File -Recurse -Force -LiteralPath $repoRoot | Where-Object {
    $relative = Get-RelativePath $_.FullName
    $scanExtensions -contains $_.Extension.ToLowerInvariant() -and
        -not ($excludedScanPaths | Where-Object { $relative -eq $_ -or $relative.StartsWith("$_/") })
}
$refRules = @(
    @{ id='REF-GCP'; severity='P1'; regex='(?i)\b(GCP|GKE|Google Cloud Platform)\b'; category='obsolete-cloud-ref'; action='Retener infra/gcp solo como histórico o excluirlo de la entrega; la ruta cloud normativa es AWS.' },
    @{ id='REF-HIST-EVIDENCE'; severity='P1'; regex='(?i)(?:\]|["''`]|\b)(?:evidence|screenshots)[/\\]'; category='obsolete-evidence-ref'; action='Actualizar enlaces de la entrega nueva a screenshoot/integrator_project/; conservar las rutas antiguas como histórico.' },
    @{ id='REF-LEGACY-IAC'; severity='P1'; regex='(?i)(?<![0-9-])(?:cloudformation[/\\])?(apps|network|observability)\.yaml'; category='legacy-iac-ref'; action='Elegir 00-05 como familia canónica y marcar los tres templates cortos como legacy; actualizar scripts que aún los invocan.' },
    @{ id='REF-PLAINTEXT-SECRET'; severity='P0'; regex='(?im)(POSTGRES_PASSWORD|GF_SECURITY_ADMIN_PASSWORD)\s*:\s*(?!\$\{|\[REDACTED\]|<[^>]+>|\?)(?=\S)["'']?[^$''{\r\n]+|DATABASE_URL\s*[:=]\s*["'']?postgres(?:ql)?://(?![^"''\r\n]*(?:\$\{|<[^>]+>))[^"''\r\n]+|os\.getenv\(["''](?:DB_PASSWORD|PASSWORD)["'']\s*,\s*["''](?!<[^>]+>)[^"'']+["'']|(?:DB_PASSWORD|PASSWORD)\s*=\s*["''](?!<[^>]+>)[^"'']+["'']'; category='plaintext-secret'; action='Eliminar el valor literal del archivo y regenerar el artefacto; usar Secret Manager/SSM o variables de entorno.' },
    @{ id='REF-PERSISTED-TOKEN'; severity='P0'; regex='(?i)"(NextToken|SessionToken|AWS_SESSION_TOKEN)"\s*:\s*"(?!\[REDACTED\])[^"]+"|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY'; category='persisted-token'; action='Redactar el token del artefacto y regenerar su hash; no guardar tokens aunque el valor no sea una access key.' }
)
foreach ($file in $scanFiles) {
    $content = Get-Content -Raw -LiteralPath $file.FullName
    $relativeFile = Get-RelativePath $file.FullName
    $isHistoricalFile = $relativeFile.StartsWith('evidence/') -or $relativeFile.StartsWith('screenshots/')
    $isNarrativeOrHistorical = $relativeFile -eq 'README.md' -or $relativeFile.StartsWith('docs/') -or $relativeFile.StartsWith('report/') -or $relativeFile.StartsWith('infra/gcp/') -or $relativeFile -eq 'infra/README.md' -or $relativeFile.StartsWith('screenshoot/integrator_project/02_aiops/') -or $relativeFile.StartsWith('scripts/evidence/')
    foreach ($rule in $refRules) {
        if ($rule.id -eq 'REF-GCP' -and $isHistoricalFile) { continue }
        if ($rule.id -eq 'REF-HIST-EVIDENCE' -and ($isHistoricalFile -or $relativeFile -eq 'screenshoot/integrator_project/evidence-manifest.json')) { continue }
        if ($isNarrativeOrHistorical -and $rule.id -in @('REF-GCP','REF-HIST-EVIDENCE','REF-LEGACY-IAC')) { continue }
        if ($content -match $rule.regex) {
            Add-Finding $rule.id $rule.severity $rule.category $relativeFile 'Se detectó una referencia o valor candidato; el auditor no imprime el contenido encontrado.' $rule.action
        }
    }
}

$cfDir = Join-Path $repoRoot 'infra/aws/cloudformation'
$cfFiles = @(Get-ChildItem -File -LiteralPath $cfDir -Filter '*.yaml' -ErrorAction SilentlyContinue)
$canonical = @($cfFiles | Where-Object { $_.Name -match '^(00-network|01-platform|02-data|03-services|04-security-observability|05-cost-guard)\.yaml$' })
$legacy = @($cfFiles | Where-Object { $_.Name -in @('network.yaml','observability.yaml','apps.yaml') })
$legacyRefs = @($scanFiles | Where-Object { $_.Extension -in @('.ps1','.py') -and (Get-Content -Raw -LiteralPath $_.FullName) -match '(?i)(?<![0-9-])(?:cloudformation[/\\])?(apps|network|observability)\.yaml' })
if ($legacy.Count -gt 0) {
    Add-Finding 'IAC-LEGACY-FAMILY' 'INFO' 'iac-duplicate' (($legacy | ForEach-Object { Get-RelativePath $_.FullName }) -join ', ') 'Existe una segunda familia CloudFormation documentada como histórica.' 'No usarla para nuevas aplicaciones; la ruta activa es la familia 00-05.'
}
if ($legacyRefs.Count -gt 0) {
    Add-Finding 'IAC-LEGACY-REFS' 'P1' 'legacy-iac-ref' (($legacyRefs | ForEach-Object { Get-RelativePath $_.FullName }) -join ', ') 'Hay scripts o documentación que aún nombran la familia corta network/observability/apps.' 'Apuntar la ejecución solo a 00-network, 01-platform, 02-data, 03-services, 04-security-observability y 05-cost-guard.'
}
$hashGroups = $cfFiles | Group-Object { (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash }
foreach ($group in $hashGroups | Where-Object Count -gt 1) {
    Add-Finding 'IAC-EXACT-DUPLICATE' 'P1' 'iac-duplicate' (($group.Group | ForEach-Object { Get-RelativePath $_.FullName }) -join ', ') 'Hay plantillas CloudFormation con hash idéntico.' 'Conservar una sola como ruta activa y marcar las copias históricas sin borrarlas.'
}
foreach ($legacyFile in $legacy) {
    foreach ($canonicalFile in $canonical) {
        $left = @(Get-ResourceIds $legacyFile.FullName)
        $right = @(Get-ResourceIds $canonicalFile.FullName)
        $intersection = @($left | Where-Object { $right -contains $_ })
        $smaller = [Math]::Max(1, [Math]::Min($left.Count, $right.Count))
        if (($intersection.Count / $smaller) -ge 0.25) {
            Add-Finding 'IAC-OVERLAP' 'INFO' 'iac-duplicate' ((Get-RelativePath $legacyFile.FullName) + ' <> ' + (Get-RelativePath $canonicalFile.FullName)) ("Solapamiento de recursos lógicos histórico: {0}/{1} del conjunto menor." -f $intersection.Count,$smaller) 'No usar la familia histórica; la ruta activa es la familia 00-05.'
        }
    }
}

$ignored = Invoke-GitRead @('ls-files', '--others', '--ignored', '--exclude-standard')
$ignoredCount = @($ignored.output | Where-Object { $_.Trim() -ne '' }).Count
$summary = [ordered]@{
    repo = $repoRoot
    branch = $branch
    tracked_modified = $trackedModified
    untracked_non_ignored = $untracked
    ignored_files = $ignoredCount
    classifications = $classificationCounts
    findings = $findings.Count
    p0 = @($findings | Where-Object severity -eq 'P0').Count
    p1 = @($findings | Where-Object severity -eq 'P1').Count
    p2 = @($findings | Where-Object severity -eq 'P2').Count
    info = @($findings | Where-Object severity -eq 'INFO').Count
    safe_scope = 'No borra, mueve, resetea, commitea, pushea, aplica Terraform, llama AWS ni levanta Docker.'
}

if ($Json) {
    [pscustomobject]@{ summary = $summary; findings = @($findings) } | ConvertTo-Json -Depth 8
    exit 0
}

Write-Output 'DELIVERY AUDIT (read-only)'
Write-Output ('repo: {0}' -f $repoRoot)
Write-Output ('branch: {0}' -f $branch)
Write-Output ('status: tracked-modified={0}; untracked-non-ignored={1}; ignored={2}' -f $trackedModified,$untracked,$ignoredCount)
Write-Output ('findings: total={0}; P0={1}; P1={2}; P2={3}; INFO={4}' -f $summary.findings,$summary.p0,$summary.p1,$summary.p2,$summary.info)
Write-Output ('scope: {0}' -f $summary.safe_scope)
Write-Output ''
Write-Output 'CLASSIFICATIONS'
foreach ($key in ($classificationCounts.Keys | Sort-Object)) { Write-Output ('- {0}: {1}' -f $key,$classificationCounts[$key]) }
Write-Output ''
Write-Output 'FINDINGS'
foreach ($finding in $findings | Sort-Object @{Expression='severity';Descending=$false},id,path) {
    Write-Output ('[{0}] {1} {2} :: {3} :: {4}' -f $finding.severity,$finding.id,$finding.path,$finding.detail,$finding.action)
}

if ($summary.p0 -gt 0) { exit 2 }
if ($summary.p1 -gt 0) { exit 1 }
exit 0
