[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('service-b-latency', 'data-service-errors')]
  [string]$Experiment,
  [ValidateRange(10, 900)]
  [int]$DurationSeconds = 180,
  [ValidateRange(10, 900)]
  [int]$BaselineDurationSeconds = 60,
  [ValidateRange(10, 300)]
  [int]$RecoveryDurationSeconds = 30,
  [ValidateRange(50, 10000)]
  [int]$IntervalMilliseconds = 250,
  [ValidateRange(1, 60)]
  [int]$AlertPollIntervalSeconds = 5,
  [ValidateRange(1, 100)]
  [int]$MaxConsecutiveFailures = 20,
  [ValidateRange(5, 120)]
  [int]$HealthTimeoutSeconds = 45,
  [ValidateRange(0.1, 1.0)]
  [double]$MaxObservedErrorRate = 0.8,
  [string]$TargetUrl = 'http://localhost:8000/order/ord-001',
  [string]$PrometheusUrl = 'http://localhost:9090',
  [string]$AlertmanagerUrl = 'http://localhost:9093',
  [string[]]$AlertNames = @(
    'OTelAvailabilityBelowSLO',
    'OTelDynamicBaselineAndP99SLO',
    'OTelStaticThresholdAndP99SLO',
    'OTelErrorBudgetNearlyExhausted'
  ),
  [string]$ContractPath = 'chaos\experiment-contract.json',
  [string]$OutputRoot = 'chaos\runs'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$resolvedContractPath = if ([System.IO.Path]::IsPathRooted($ContractPath)) {
  $ContractPath
} else {
  Join-Path $repoRoot $ContractPath
}
if (-not (Test-Path -LiteralPath $resolvedContractPath -PathType Leaf)) {
  throw "Experiment contract not found: $resolvedContractPath"
}
$contract = Get-Content -Raw -LiteralPath $resolvedContractPath | ConvertFrom-Json
$experimentSpec = @($contract.experiments) | Where-Object { $_.name -eq $Experiment } | Select-Object -First 1
if (-not $experimentSpec) {
  throw "Experiment $Experiment is not present in the contract."
}
if ([string]$experimentSpec.control.value -ne $(if ($Experiment -eq 'service-b-latency') { '200' } else { '0.1' })) {
  throw "Contract value for $Experiment does not match the required exact injection."
}
$resolvedOutputRoot = if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
  $OutputRoot
} else {
  Join-Path $repoRoot $OutputRoot
}
$runId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runDir = Join-Path $resolvedOutputRoot "$Experiment-$runId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$metadataPath = Join-Path $runDir 'metadata.json'
$recordsPath = Join-Path $runDir 'request-records.json'
$alertsPath = Join-Path $runDir 'alert-observations.json'
$eventsPath = Join-Path $runDir 'lifecycle-events.json'
$phasesPath = Join-Path $runDir 'phase-summaries.json'
$reportPath = Join-Path $runDir 'report.json'
$measureLogPath = Join-Path $runDir 'measure-command.txt'
$composeService = if ($Experiment -eq 'service-b-latency') { 'service-b' } else { 'data-service' }
$controlName = if ($Experiment -eq 'service-b-latency') { 'LAB_SERVICE_B_LATENCY_MS' } else { 'LAB_DATA_ERROR_RATE' }
$controlValue = if ($Experiment -eq 'service-b-latency') { '200' } else { '0.1' }
$rollbackValue = [string]$experimentSpec.control.rollback_value
$composePort = if ($composeService -eq 'service-b') { 8001 } else { 8002 }
if ([string]$experimentSpec.target_service -ne $composeService) {
  throw "Contract target $($experimentSpec.target_service) does not match runner target $composeService."
}
$variantName = "otel-lab-chaos-$runId"
$chaosEnv = "$controlName=$controlValue"
$variantStarted = $false
$targetStopped = $false
$runError = $null
$rollbackError = $null
$lastAlertPollUtc = [DateTime]::MinValue
$injectionLifecycleStarted = $false
$events = [System.Collections.Generic.List[object]]::new()

function UtcIso([datetime]$Value) {
  $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.ffffffZ')
}

function Write-JsonFile([string]$Path, $Value) {
  $Value | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $Path -Encoding utf8
}

function Record-Event([string]$Name, [string]$Phase, $Details = $null) {
  $event = [ordered]@{
    event = $Name
    phase = $Phase
    observed_at_utc = UtcIso (Get-Date)
    details = if ($null -eq $Details) { [ordered]@{} } else { $Details }
  }
  $events.Add($event)
  Write-JsonFile $eventsPath @($events)
}

function Invoke-NativeToFile([string]$File, [string[]]$Arguments, [string]$Path) {
  $output = @(& $File @Arguments 2>&1)
  $exitCode = $LASTEXITCODE
  $output | Set-Content -LiteralPath $Path -Encoding utf8
  if ($exitCode -ne 0) {
    throw "$File $($Arguments -join ' ') failed with exit code $exitCode. See $Path"
  }
  return ($output -join [Environment]::NewLine)
}

function Get-ContainerId([string]$Service) {
  $output = @(& docker compose ps -q $Service 2>$null)
  if ($LASTEXITCODE -ne 0) { return $null }
  return ($output | Select-Object -First 1).ToString().Trim()
}

function Test-ComposeHealthy([string]$Service) {
  $containerId = Get-ContainerId $Service
  if (-not $containerId) { return $false }
  $health = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $containerId 2>$null).ToString().Trim()
  if ($LASTEXITCODE -ne 0) { return $false }
  return $health -eq 'healthy' -or $health -eq 'running'
}

function Wait-ComposeHealthy([string]$Service, [int]$TimeoutSeconds = $HealthTimeoutSeconds) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if (Test-ComposeHealthy $Service) { return $true }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Test-HttpHealthy([int]$Port) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$Port/health" -TimeoutSec 2
    return [int]$response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Wait-HttpHealthy([int]$Port, [int]$TimeoutSeconds = $HealthTimeoutSeconds) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if (Test-HttpHealthy $Port) { return $true }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Get-ContainerEnvironmentValue([string]$Container, [string]$Name, [string]$OutputPath) {
  $environment = Invoke-NativeToFile 'docker' @('inspect', '--format', '{{range .Config.Env}}{{println .}}{{end}}', $Container) $OutputPath
  $line = $environment -split "`r?`n" | Where-Object { $_ -like "$Name=*" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ([string]$line).Substring($Name.Length + 1)
}

function Select-TargetAlerts($Alerts) {
  $selected = @()
  foreach ($alert in @($Alerts)) {
    $name = [string]$alert.alertname
    $labels = $alert.labels
    $serviceLabel = if ($labels) {
      if ($labels.service_name) { [string]$labels.service_name } elseif ($labels.service) { [string]$labels.service } else { '' }
    } else { '' }
    if ($AlertNames.Count -gt 0 -and $AlertNames -notcontains $name) { continue }
    if ($serviceLabel -and @('service-a', $composeService) -notcontains $serviceLabel) { continue }
    $selected += [ordered]@{
      alert_name = $name
      state = [string]$alert.state
      active_at = if ($alert.activeAt) { [string]$alert.activeAt } else { $null }
      firing_timestamp_utc = $null
      firing_timestamp_source = $null
      target_service_label = $serviceLabel
      labels = $labels
      annotations = $alert.annotations
    }
  }
  return @($selected)
}

function Get-PrometheusSnapshot {
  $observedAt = UtcIso (Get-Date)
  $query = "$($PrometheusUrl.TrimEnd('/'))/api/v1/alerts"
  try {
    $payload = Invoke-RestMethod -UseBasicParsing -Uri $query -Method Get -TimeoutSec 5
    if ([string]$payload.status -ne 'success') { throw 'Prometheus API returned a non-success status.' }
    $alerts = Select-TargetAlerts $payload.data.alerts | Where-Object { $_.state -eq 'firing' }
    $metricExpressions = [ordered]@{
      error_rate_5m = ('otel:error_rate_5m{service_name="' + $composeService + '",telemetry_scope="local"}')
      p99_seconds_5m = ('otel:p99_seconds_5m{service_name="' + $composeService + '",telemetry_scope="local"}')
      availability_5m = ('otel:availability_5m{service_name="' + $composeService + '",telemetry_scope="local"}')
      error_budget_remaining = ('otel:error_budget_remaining_ratio{service_name="' + $composeService + '",telemetry_scope="local"}')
    }
    $metricResults = [ordered]@{}
    foreach ($metricName in $metricExpressions.Keys) {
      $metricQuery = $metricExpressions[$metricName]
      $encodedQuery = [Uri]::EscapeDataString($metricQuery)
      $metricUrl = "$($PrometheusUrl.TrimEnd('/'))/api/v1/query?query=$encodedQuery"
      try {
        $metricPayload = Invoke-RestMethod -UseBasicParsing -Uri $metricUrl -Method Get -TimeoutSec 5
        $metricResults[$metricName] = [ordered]@{
          query = $metricQuery
          available = [string]$metricPayload.status -eq 'success'
          result = if ([string]$metricPayload.status -eq 'success') { @($metricPayload.data.result) } else { @() }
          observed_at_utc = $observedAt
        }
      } catch {
        $metricResults[$metricName] = [ordered]@{
          query = $metricQuery
          available = $false
          result = @()
          observed_at_utc = $observedAt
          error = $_.Exception.Message
        }
      }
    }
    return [ordered]@{
      available = $true
      query = $query
      observed_at_utc = $observedAt
      alerts = @($alerts)
      metrics = $metricResults
    }
  } catch {
    return [ordered]@{
      available = $false
      query = $query
      observed_at_utc = $observedAt
      alerts = @()
      metrics = [ordered]@{}
      error = $_.Exception.Message
    }
  }
}

function Get-AlertmanagerSnapshot {
  $observedAt = UtcIso (Get-Date)
  $query = "$($AlertmanagerUrl.TrimEnd('/'))/api/v2/alerts?active=true&silenced=false&inhibited=false"
  try {
    $payload = Invoke-RestMethod -UseBasicParsing -Uri $query -Method Get -TimeoutSec 5
    $alerts = @()
    foreach ($alert in @($payload)) {
      $name = [string]$alert.labels.alertname
      $serviceLabel = if ($alert.labels.service_name) { [string]$alert.labels.service_name } elseif ($alert.labels.service) { [string]$alert.labels.service } else { '' }
      if ($AlertNames.Count -gt 0 -and $AlertNames -notcontains $name) { continue }
      if ($serviceLabel -and @('service-a', $composeService) -notcontains $serviceLabel) { continue }
      if ([string]$alert.status.state -ne 'active') { continue }
      $alerts += [ordered]@{
        alert_name = $name
        status_state = 'firing'
        starts_at = if ($alert.startsAt) { [string]$alert.startsAt } else { $null }
        firing_timestamp_utc = if ($alert.startsAt) { [string]$alert.startsAt } else { $null }
        firing_timestamp_source = if ($alert.startsAt) { 'alertmanager.startsAt' } else { $null }
        target_service_label = $serviceLabel
        labels = $alert.labels
        annotations = $alert.annotations
      }
    }
    return [ordered]@{
      available = $true
      query = $query
      observed_at_utc = $observedAt
      alerts = @($alerts)
    }
  } catch {
    return [ordered]@{
      available = $false
      query = $query
      observed_at_utc = $observedAt
      alerts = @()
      error = $_.Exception.Message
    }
  }
}

function Collect-AlertSnapshot([string]$Phase, [switch]$Force) {
  $now = Get-Date
  if (-not $Force -and (($now.ToUniversalTime() - $lastAlertPollUtc).TotalSeconds -lt $AlertPollIntervalSeconds)) {
    return
  }
  $script:lastAlertPollUtc = $now.ToUniversalTime()
  $alertObservations.Add([ordered]@{
    phase = $Phase
    observed_at_utc = UtcIso $now
    prometheus = Get-PrometheusSnapshot
    alertmanager = Get-AlertmanagerSnapshot
  })
}

function Invoke-Load([string]$Phase, [int]$Duration, [System.Collections.Generic.List[object]]$Records) {
  $phaseStarted = Get-Date
  $deadline = $phaseStarted.AddSeconds($Duration)
  $sequence = 0
  $consecutiveFailures = 0
  $phaseErrors = 0
  $stopReason = $null
  Record-Event "${Phase}_load_started" $Phase ([ordered]@{
    configured_duration_seconds = $Duration
    target_url = $TargetUrl
    interval_milliseconds = $IntervalMilliseconds
  })
  while ((Get-Date) -lt $deadline) {
    $sequence++
    $started = Get-Date
    $status = 599
    $traceId = 'unknown'
    $error = $null
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $TargetUrl -TimeoutSec 5
      $status = [int]$response.StatusCode
      try {
        $body = $response.Content | ConvertFrom-Json
        if ($body.trace_id) { $traceId = [string]$body.trace_id }
      } catch { }
    } catch {
      $error = $_.Exception.Message
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $status = [int]$_.Exception.Response.StatusCode
      }
    }
    $completed = Get-Date
    if ($status -ge 500) {
      $consecutiveFailures++
      $phaseErrors++
    } else {
      $consecutiveFailures = 0
    }
    $Records.Add([ordered]@{
      sequence = $sequence
      phase = $Phase
      started_utc = UtcIso $started
      completed_utc = UtcIso $completed
      timestamp_utc = UtcIso $completed
      status_code = $status
      duration_seconds = ($completed - $started).TotalSeconds
      trace_id = $traceId
      error = $error
    })
    Collect-AlertSnapshot $Phase
    if (-not (Test-HttpHealthy $composePort)) {
      $stopReason = "stop_condition: $composeService /health failed"
      break
    }
    if ($consecutiveFailures -ge $MaxConsecutiveFailures) {
      $stopReason = "stop_condition: $MaxConsecutiveFailures consecutive target request failures"
      break
    }
    if ($sequence -ge 20 -and (($phaseErrors / $sequence) -gt $MaxObservedErrorRate)) {
      $stopReason = "stop_condition: observed error rate $($phaseErrors / $sequence) exceeded $MaxObservedErrorRate"
      break
    }
    Start-Sleep -Milliseconds $IntervalMilliseconds
  }
  Collect-AlertSnapshot $Phase -Force
  $summary = [ordered]@{
    phase = $Phase
    started_utc = UtcIso $phaseStarted
    ended_utc = UtcIso (Get-Date)
    configured_duration_seconds = $Duration
    stop_reason = $stopReason
    requests = @($Records | Where-Object { $_.phase -eq $Phase }).Count
    errors = $phaseErrors
  }
  Record-Event "${Phase}_load_ended" $Phase $summary
  return $summary
}

$records = [System.Collections.Generic.List[object]]::new()
$alertObservations = [System.Collections.Generic.List[object]]::new()
$phaseSummaries = [System.Collections.Generic.List[object]]::new()
$metadata = [ordered]@{
  experiment = $Experiment
  environment = 'local'
  telemetry_scope = 'local-executed'
  target_service = $composeService
  target_url = $TargetUrl
  contract_path = $resolvedContractPath
  contract_schema_version = $contract.schema_version
  hypothesis = [string]$experimentSpec.hypothesis
  target_route = [string]$experimentSpec.target_route
  blast_radius = [string]$experimentSpec.blast_radius
  injection_control = $controlName
  injection_control_value = $controlValue
  injection_control_observed_value = $null
  chaos_parameter = $chaosEnv
  rollback_control = "$controlName=$rollbackValue"
  rollback_actions = @(
    "docker rm -f $variantName"
    "docker compose up -d $composeService"
    "wait for $composeService health and http /health"
    "verify $controlName=$rollbackValue inside the restored container"
  )
  alert_names_queried = @($AlertNames)
  prometheus_alerts_query = "$($PrometheusUrl.TrimEnd('/'))/api/v1/alerts"
  alertmanager_alerts_query = "$($AlertmanagerUrl.TrimEnd('/'))/api/v2/alerts?active=true&silenced=false&inhibited=false"
  baseline_duration_seconds = $BaselineDurationSeconds
  load_duration_seconds = $DurationSeconds
  recovery_duration_seconds = $RecoveryDurationSeconds
  interval_milliseconds = $IntervalMilliseconds
  load_profile = [ordered]@{
    method = 'sequential HTTP requests'
    interval_milliseconds = $IntervalMilliseconds
    target_url = $TargetUrl
    timeout_seconds = 5
    deterministic_client_schedule = $true
  }
  slo_latency_p99_seconds = 0.5
  slo_error_rate_budget = 0.005
  recovery_min_availability = [double]$experimentSpec.success_criteria.recovery_min_availability
  stop_conditions = @(
    [string]$experimentSpec.stop_conditions[0]
    [string]$experimentSpec.stop_conditions[1]
    "$MaxConsecutiveFailures consecutive target request failures stop the injection load"
    "observed injection error rate > $MaxObservedErrorRate after at least 20 requests stops the load"
  )
  stop_condition_triggered = $null
  injection_requested_utc = $null
  injection_started_utc = $null
  injection_start_source = $null
  injection_ended_utc = $null
  rollback_requested_utc = $null
  rollback_completed_utc = $null
  rollback_verified = $false
  rollback_control_value = $null
  status = 'prepared'
  execution_classification = 'PREPARED'
}
Write-JsonFile $metadataPath $metadata
Record-Event 'run_prepared' 'preflight' ([ordered]@{
  experiment = $Experiment
  target_service = $composeService
  exact_control = $chaosEnv
  rollback_control = "$controlName=$rollbackValue"
})

try {
  Record-Event 'preflight_started' 'preflight' ([ordered]@{
    target_service = $composeService
    target_url = $TargetUrl
    prometheus_url = $PrometheusUrl
    alertmanager_url = $AlertmanagerUrl
  })
  $null = Invoke-NativeToFile 'docker' @('compose', 'ps', $composeService) (Join-Path $runDir 'preflight-compose.txt')
  if (-not (Get-ContainerId $composeService) -or -not (Test-ComposeHealthy $composeService)) {
    throw "Preflight blocked: Compose service $composeService is not running and healthy."
  }
  if (-not (Test-HttpHealthy $composePort)) {
    throw "Preflight blocked: $composeService /health is not responding on port $composePort."
  }
  $metadata.preflight_completed_utc = UtcIso (Get-Date)
  $metadata.preflight_status = 'healthy'
  Write-JsonFile $metadataPath $metadata
  Record-Event 'preflight_completed' 'preflight' ([ordered]@{
    compose_service_healthy = $true
    target_health_http_status = 200
  })

  Collect-AlertSnapshot 'baseline' -Force
  $baselineSummary = Invoke-Load 'baseline' $BaselineDurationSeconds $records
  $phaseSummaries.Add($baselineSummary)
  if ($baselineSummary.stop_reason) {
    $metadata.stop_condition_triggered = $baselineSummary.stop_reason
    throw "Baseline invalidated by $($baselineSummary.stop_reason)."
  }

  $metadata.injection_requested_utc = UtcIso (Get-Date)
  Record-Event 'injection_requested' 'injection' ([ordered]@{
    control_name = $controlName
    control_value = $controlValue
    exact_parameter = $chaosEnv
    target_service = $composeService
  })
  Write-JsonFile $metadataPath $metadata
  $null = Invoke-NativeToFile 'docker' @('compose', 'stop', $composeService) (Join-Path $runDir 'injection-stop.txt')
  $targetStopped = $true
  Record-Event 'target_stopped_for_injection' 'injection' ([ordered]@{ service = $composeService })
  $null = Invoke-NativeToFile 'docker' @('compose', 'run', '-d', '--name', $variantName, '--use-aliases', '--no-deps', '--service-ports', '--env', $chaosEnv, $composeService) (Join-Path $runDir 'injection-start.txt')
  $variantStarted = $true
  Record-Event 'injection_container_requested' 'injection' ([ordered]@{
    container = $variantName
    service = $composeService
    control = $chaosEnv
  })
  $startedRaw = @(& docker inspect --format '{{.State.StartedAt}}' $variantName 2>$null) | Select-Object -First 1
  if (-not $startedRaw -or ([string]$startedRaw).Trim().StartsWith('0001-')) {
    throw 'Injection blocked: Docker did not return a verifiable container StartedAt timestamp.'
  }
  $metadata.injection_started_utc = UtcIso ([DateTime]::Parse(([string]$startedRaw).Trim()).ToUniversalTime())
  $metadata.injection_start_source = 'docker inspect .State.StartedAt'
  $injectionLifecycleStarted = $true
  $metadata.status = 'injection_started'
  $metadata.execution_classification = 'EXECUTING_ROLLBACK_REQUIRED'
  $metadata.injection_control_observed_value = Get-ContainerEnvironmentValue $variantName $controlName (Join-Path $runDir 'injection-control-observed.txt')
  if ($metadata.injection_control_observed_value -ne $controlValue) {
    throw "Injection blocked: container control is $($metadata.injection_control_observed_value), expected $controlValue."
  }
  Record-Event 'injection_container_started' 'injection' ([ordered]@{
    container = $variantName
    started_at_utc = $metadata.injection_started_utc
    start_source = $metadata.injection_start_source
    control_name = $controlName
    control_requested_value = $controlValue
    control_observed_value = $metadata.injection_control_observed_value
  })
  if (-not (Wait-HttpHealthy $composePort)) {
    throw "Injection variant $composeService did not become healthy within the timeout."
  }
  Record-Event 'injection_container_healthy' 'injection' ([ordered]@{ port = $composePort; health_endpoint = "http://localhost:$composePort/health" })
  Write-JsonFile $metadataPath $metadata
  Collect-AlertSnapshot 'injection' -Force
  $injectionSummary = Invoke-Load 'injection' $DurationSeconds $records
  $phaseSummaries.Add($injectionSummary)
  if ($injectionSummary.stop_reason) { $metadata.stop_condition_triggered = $injectionSummary.stop_reason }
  $metadata.injection_ended_utc = UtcIso (Get-Date)
  Record-Event 'injection_ended' 'injection' ([ordered]@{
    reason = if ($injectionSummary.stop_reason) { $injectionSummary.stop_reason } else { 'timebox_completed' }
    requests = $injectionSummary.requests
    errors = $injectionSummary.errors
  })
} catch {
  $runError = $_.Exception.Message
  if ($injectionLifecycleStarted -and -not $metadata.injection_ended_utc) {
    $metadata.injection_ended_utc = UtcIso (Get-Date)
    Record-Event 'injection_aborted' 'injection' ([ordered]@{ reason = $runError })
  }
  if (-not $metadata.stop_condition_triggered -and $runError -match 'stop_condition') {
    $metadata.stop_condition_triggered = $runError
  }
} finally {
  if ($targetStopped) {
    $metadata.rollback_requested_utc = UtcIso (Get-Date)
    Record-Event 'rollback_requested' 'rollback' ([ordered]@{
      control_name = $controlName
      rollback_value = $rollbackValue
      target_service = $composeService
    })
    try {
      if ($variantStarted) {
        $null = Invoke-NativeToFile 'docker' @('rm', '-f', $variantName) (Join-Path $runDir 'rollback-remove.txt')
        Record-Event 'injection_container_removed' 'rollback' ([ordered]@{ container = $variantName })
      }
      $null = Invoke-NativeToFile 'docker' @('compose', 'up', '-d', $composeService) (Join-Path $runDir 'rollback-start.txt')
      Record-Event 'baseline_container_started' 'rollback' ([ordered]@{ service = $composeService })
      if (-not (Wait-ComposeHealthy $composeService) -or -not (Wait-HttpHealthy $composePort)) {
        throw "Rollback did not restore a healthy $composeService."
      }
      $controlOutput = Invoke-NativeToFile 'docker' @('compose', 'exec', '-T', $composeService, 'printenv', $controlName) (Join-Path $runDir 'rollback-control.txt')
      $metadata.rollback_control_value = ($controlOutput.Trim() -split "`r?`n" | Select-Object -Last 1).Trim()
      $metadata.rollback_verified = $metadata.rollback_control_value -eq $rollbackValue
      if (-not $metadata.rollback_verified) { throw "Rollback control is $($metadata.rollback_control_value), expected $rollbackValue." }
      $metadata.rollback_completed_utc = UtcIso (Get-Date)
      Record-Event 'rollback_verified' 'rollback' ([ordered]@{
        control_name = $controlName
        control_value_observed = $metadata.rollback_control_value
        health_verified = $true
      })
      Collect-AlertSnapshot 'recovery' -Force
      $recoverySummary = Invoke-Load 'recovery' $RecoveryDurationSeconds $records
      $phaseSummaries.Add($recoverySummary)
      if ($recoverySummary.stop_reason -and -not $metadata.stop_condition_triggered) {
        $metadata.stop_condition_triggered = $recoverySummary.stop_reason
      }
    } catch {
      $rollbackError = $_.Exception.Message
      $metadata.rollback_verified = $false
      $metadata.rollback_error = $rollbackError
      Record-Event 'rollback_failed' 'rollback' ([ordered]@{ reason = $rollbackError })
      $_.Exception.Message | Set-Content -LiteralPath (Join-Path $runDir 'rollback-error.txt') -Encoding utf8
    }
  }
  if (-not $metadata.injection_started_utc) {
    $metadata.status = 'not_executed'
    $metadata.execution_classification = if ($runError) { 'BLOCKED_NOT_EXECUTED' } else { 'NOT_EXECUTED' }
  } elseif ($metadata.rollback_verified) {
    $metadata.status = 'recovered'
    $metadata.execution_classification = 'EXECUTED_ROLLBACK_VERIFIED'
  } else {
    $metadata.status = 'rollback_failed'
    $metadata.execution_classification = 'EXECUTED_ROLLBACK_UNVERIFIED'
  }
  Record-Event 'run_finished' 'finalization' ([ordered]@{
    status = $metadata.status
    execution_classification = $metadata.execution_classification
    run_error = $runError
    rollback_error = $rollbackError
  })
  Write-JsonFile $metadataPath $metadata
  Write-JsonFile $recordsPath @($records)
  Write-JsonFile $alertsPath @($alertObservations)
  Write-JsonFile $phasesPath @($phaseSummaries)
}

$measureArgs = @(
  '-3',
  (Join-Path $PSScriptRoot 'measure.py'),
  '--records', $recordsPath,
  '--metadata', $metadataPath,
  '--alerts', $alertsPath,
  '--phases', $phasesPath,
  '--output', $reportPath
)
try {
  $measureOutput = @(& py @measureArgs 2>&1)
  $measureExitCode = $LASTEXITCODE
  $measureOutput | Set-Content -LiteralPath $measureLogPath -Encoding utf8
  if ($measureExitCode -ne 0) { throw "measure.py failed with exit code $measureExitCode. See $measureLogPath" }
} catch {
  if (-not $runError) { $runError = $_.Exception.Message }
}

if ($rollbackError) {
  if ($runError) { throw "$runError Rollback failure: $rollbackError" }
  throw "Rollback failure: $rollbackError"
}
if ($runError) { throw $runError }
Write-Host "Chaos run written to $runDir"
