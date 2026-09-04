Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script:AwsEvidenceRoot = Join-Path $script:RepoRoot 'screenshoot\integrator_project\05_aws_deployment'

function ConvertTo-RedactedText {
    param([AllowEmptyString()][string]$Text)
    if ($null -eq $Text) { return '' }
    $Text -replace '(?im)^(\s*(access_key|secret_key|session_token)\s*[:=]\s*).+$', '$1[REDACTED]' `
         -replace '(?i)(AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|AWS_ACCESS_KEY_ID)=([^\s&]+)', '$1=[REDACTED]' `
         -replace '(?i)("?NextToken"?\s*:\s*)("[^"]*"|null)', '$1"[REDACTED]"' `
         -replace '(?i)("?SessionToken"?\s*:\s*)("[^"]*"|null)', '$1"[REDACTED]"'
}

function Invoke-AwsText {
    param(
        [Parameter(Mandatory)][string[]]$CommandArgs,
        [Parameter(Mandatory)][string]$Region,
        [string]$Profile
    )
    $args = @('--no-cli-pager', '--region', $Region)
    if ($Profile) { $args += @('--profile', $Profile) }
    $args += $CommandArgs
    $raw = (& aws @args 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $safe = ConvertTo-RedactedText $raw
    if ($exitCode -ne 0) {
        throw "AWS CLI fallo ($exitCode): $safe"
    }
    return $safe.Trim()
}

function Invoke-AwsJson {
    param(
        [Parameter(Mandatory)][string[]]$CommandArgs,
        [Parameter(Mandatory)][string]$Region,
        [string]$Profile
    )
    $text = Invoke-AwsText -CommandArgs $CommandArgs -Region $Region -Profile $Profile
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    return $text | ConvertFrom-Json
}

function Assert-AwsContext {
    param(
        [Parameter(Mandatory)][string]$ExpectedAccountId,
        [Parameter(Mandatory)][string]$ExpectedRegion,
        [string]$Profile
    )
    if ($ExpectedAccountId -notmatch '^\d{12}$') { throw 'ExpectedAccountId debe ser un account ID AWS de 12 digitos.' }
    if ($ExpectedRegion -notmatch '^[a-z]{2}(-gov)?-[a-z]+-\d$') { throw 'ExpectedRegion no parece una region AWS valida.' }
    $envRegion = if ($env:AWS_REGION) { $env:AWS_REGION } elseif ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { $null }
    if ($envRegion -and $envRegion -ne $ExpectedRegion) {
        throw "AWS_REGION/AWS_DEFAULT_REGION ($envRegion) no coincide con ExpectedRegion ($ExpectedRegion)."
    }
    $identity = Invoke-AwsJson -CommandArgs @('sts', 'get-caller-identity', '--output', 'json') -Region $ExpectedRegion -Profile $Profile
    if ($identity.Account -ne $ExpectedAccountId) {
        throw "Cuenta inesperada: se esperaba $ExpectedAccountId y AWS devolvio $($identity.Account)."
    }
    [pscustomobject]@{
        AccountId = $identity.Account
        Arn = $identity.Arn
        Region = $ExpectedRegion
        Profile = if ($Profile) { $Profile } elseif ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { 'default-chain' }
    }
}

function Write-SafeJson {
    param([Parameter(Mandatory)]$Value, [Parameter(Mandatory)][string]$Path)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
}

function Get-ParameterOverrides {
    param([Parameter(Mandatory)][string]$ParametersFile)
    $params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
    @($params.PSObject.Properties | ForEach-Object {
        if ($null -eq $_.Value -or [string]::IsNullOrWhiteSpace([string]$_.Value)) {
            throw "Parametro vacio en $ParametersFile`: $($_.Name)"
        }
        "$($_.Name)=$($_.Value)"
    })
}

function Get-ParameterOverridesForStack {
    param([Parameter(Mandatory)][string]$ParametersFile, [Parameter(Mandatory)][string]$StackKey)
    $params = Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json
    $names = switch ($StackKey) {
        'network' { @('ProjectName','Environment','Owner','ExpirationUtc','VpcCidr','PublicSubnet1Cidr','PublicSubnet2Cidr','PrivateDbSubnet1Cidr','PrivateDbSubnet2Cidr','AllowedIngressCidr','AllowLegacyDirectDbAccess') }
        'platform' { @('ProjectName','Environment','Owner','ExpirationUtc','LogRetentionDays') }
        'data' { @('ProjectName','Environment','Owner','ExpirationUtc','DbInstanceClass','AllocatedStorage','BackupRetentionDays') }
        'cost-guard' { @('ProjectName','Environment','Owner','ExpirationUtc','LogRetentionDays') }
        'services' { @('ProjectName','Environment','Owner','ExpirationUtc','ImageTag','AssignPublicIp','AppTaskSize','CollectorTaskSize','DesiredCount','ServiceBLatencyMs','DataServiceErrorRate') }
        'security' { @('ProjectName','Environment','Owner','ExpirationUtc','LogRetentionDays','EnableCloudTrail','EnableSecurityHub') }
        default { throw "StackKey no soportada: $StackKey" }
    }
    @($names | Where-Object { $null -ne $params.PSObject.Properties[$_] } | ForEach-Object { "$_=$($params.PSObject.Properties[$_].Value)" })
}

function Get-StackDefinitions {
    param([Parameter(Mandatory)][string]$ParametersFile)
    $cfDir = Join-Path $script:RepoRoot 'infra\aws\cloudformation'
    $project = (Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json).ProjectName
    $environment = (Get-Content -Raw -LiteralPath $ParametersFile | ConvertFrom-Json).Environment
    @(
        [pscustomobject]@{ Key = 'network'; Template = Join-Path $cfDir '00-network.yaml'; Name = "$project-$environment-00-network" }
        [pscustomobject]@{ Key = 'platform'; Template = Join-Path $cfDir '01-platform.yaml'; Name = "$project-$environment-01-platform" }
        [pscustomobject]@{ Key = 'data'; Template = Join-Path $cfDir '02-data.yaml'; Name = "$project-$environment-02-data" }
        [pscustomobject]@{ Key = 'cost-guard'; Template = Join-Path $cfDir '05-cost-guard.yaml'; Name = "$project-$environment-05-cost-guard" }
        [pscustomobject]@{ Key = 'services'; Template = Join-Path $cfDir '03-services.yaml'; Name = "$project-$environment-03-services" }
        [pscustomobject]@{ Key = 'security'; Template = Join-Path $cfDir '04-security-observability.yaml'; Name = "$project-$environment-04-security" }
    )
}
