[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedAccountId,
    [Parameter(Mandatory)][string]$ExpectedRegion,
    [Parameter(Mandatory)][string]$ParametersFile,
    [string]$Profile = $env:AWS_PROFILE,
    [string]$ImageTag = 'v1',
    [switch]$PublishAuthorized,
    [string]$ConfirmedByUser
)
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $PublishAuthorized -or $ConfirmedByUser -ne 'I_HAVE_REVIEWED_COST_AND_PLAN') { throw 'Publicacion bloqueada hasta aprobacion explicita.' }
$null = Assert-AwsContext -ExpectedAccountId $ExpectedAccountId -ExpectedRegion $ExpectedRegion -Profile $Profile
$params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
if ($ImageTag -notmatch '^v[0-9][A-Za-z0-9._-]{0,31}$') { throw 'ImageTag debe ser inmutable y comenzar por v.' }
$root = $script:RepoRoot
if (-not (Test-Path -LiteralPath (Join-Path $root 'data-service\Dockerfile'))) {
    throw 'Bloqueo real: falta data-service/Dockerfile; no se puede construir ni publicar data-service.'
}
$registry = "$ExpectedAccountId.dkr.ecr.$ExpectedRegion.amazonaws.com"
$loginArgs = @('--no-cli-pager', '--region', $ExpectedRegion)
if ($Profile) { $loginArgs += @('--profile', $Profile) }
$password = & aws @loginArgs ecr get-login-password 2>&1
if ($LASTEXITCODE -ne 0) { throw 'No se pudo obtener el token temporal de ECR.' }
try { $password | & docker login --username AWS --password-stdin $registry | Out-Null } finally { $password = $null }
$images = @(
    @{ Name = 'service-a'; Context = 'service-a'; Dockerfile = 'service-a\Dockerfile'; Repository = "$($params.ProjectName)-$($params.Environment)-service-a" },
    @{ Name = 'service-b'; Context = 'service-b'; Dockerfile = 'service-b\Dockerfile'; Repository = "$($params.ProjectName)-$($params.Environment)-service-b" },
    @{ Name = 'data-service'; Context = 'data-service'; Dockerfile = 'data-service\Dockerfile'; Repository = "$($params.ProjectName)-$($params.Environment)-data-service" },
    @{ Name = 'otel-collector'; Context = 'infra\aws\collector-image'; Dockerfile = 'infra\aws\collector-image\Dockerfile'; Repository = "$($params.ProjectName)-$($params.Environment)-otel-collector" }
)
foreach ($image in $images) {
    $full = "$registry/$($image.Repository):$ImageTag"
    if (-not $PSCmdlet.ShouldProcess($full, 'docker build and push to ECR')) { continue }
    & docker build --tag "$($image.Repository):$ImageTag" --file (Join-Path $root $image.Dockerfile) (Join-Path $root $image.Context)
    if ($LASTEXITCODE -ne 0) { throw "docker build fallo para $($image.Name)." }
    & docker tag "$($image.Repository):$ImageTag" $full
    & docker push $full | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker push fallo para $($image.Name)." }
    Invoke-AwsText -CommandArgs @('ecr', 'describe-images', '--repository-name', $image.Repository, '--image-ids', "imageTag=$ImageTag", '--output', 'json') -Region $ExpectedRegion -Profile $Profile
}
