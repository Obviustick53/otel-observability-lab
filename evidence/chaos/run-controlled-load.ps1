param(
    [Parameter(Mandatory = $true)] [string] $OutputJson,
    [int] $Vus = 5,
    [int] $DurationSeconds = 45,
    [int] $IntervalMilliseconds = 250,
    [string] $BaseUrl = 'http://localhost:8000'
)

$ErrorActionPreference = 'Stop'
$started = [DateTimeOffset]::UtcNow
$deadline = $started.AddSeconds($DurationSeconds)
$worker = {
    param($WorkerId, $BaseUrl, $Deadline, $IntervalMilliseconds)
    while ([DateTimeOffset]::UtcNow -lt $Deadline) {
            $orderId = 'ord-00' + (($WorkerId % 3) + 1)
            $url = "$BaseUrl/order/$orderId"
            $requestStarted = [System.Diagnostics.Stopwatch]::GetTimestamp()
            $status = 0
            $httpStatusCode = $null
            $outcome = 'transport_error'
            $errorType = $null
            $requestError = $null
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10
                $httpStatusCode = [int]$response.StatusCode
                $status = $httpStatusCode
                if ($httpStatusCode -ge 200 -and $httpStatusCode -lt 300) {
                    $outcome = 'success'
                } else {
                    $outcome = 'http_error'
                    $errorType = 'http_status'
                    $requestError = "HTTP status code: $httpStatusCode"
                }
            } catch {
                $baseException = $_.Exception.GetBaseException()
                $requestError = $baseException.Message

                # Invoke-WebRequest throws for many 4xx/5xx responses. Keep the
                # HTTP code separate from the exception text so a status is not
                # mistaken for a transport/timeout failure.
                $httpResponse = $null
                if ($_.Exception.PSObject.Properties.Name -contains 'Response') {
                    $httpResponse = $_.Exception.Response
                }
                if ($null -eq $httpResponse -and $baseException.PSObject.Properties.Name -contains 'Response') {
                    $httpResponse = $baseException.Response
                }
                if ($null -ne $httpResponse) {
                    try {
                        if ($null -ne $httpResponse.StatusCode) {
                            $httpStatusCode = [int]$httpResponse.StatusCode
                        }
                    } catch {
                        $httpStatusCode = $null
                    }
                }

                if ($null -ne $httpStatusCode) {
                    $status = $httpStatusCode
                    $outcome = 'http_error'
                    $errorType = 'http_status'
                } else {
                    $status = 0
                    $outcome = 'transport_error'
                    $errorType = $baseException.GetType().Name
                }
            }
            $elapsedMs = [Math]::Round((([System.Diagnostics.Stopwatch]::GetTimestamp() - $requestStarted) * 1000.0) / [System.Diagnostics.Stopwatch]::Frequency, 3)
            [pscustomobject]@{
                worker = $WorkerId
                timestamp = [DateTimeOffset]::UtcNow.ToString('o')
                # `status` remains for compatibility with the original JSON.
                status = $status
                http_status_code = $httpStatusCode
                outcome = $outcome
                error_type = $errorType
                latency_ms = $elapsedMs
                error = $requestError
            }
            $sleepUntil = [DateTimeOffset]::UtcNow.AddMilliseconds($IntervalMilliseconds)
            while ([DateTimeOffset]::UtcNow -lt $sleepUntil -and [DateTimeOffset]::UtcNow -lt $Deadline) {
                Start-Sleep -Milliseconds 25
            }
    }
}

$jobs = 1..$Vus | ForEach-Object { Start-ThreadJob -ScriptBlock $worker -ArgumentList $_, $BaseUrl, $deadline, $IntervalMilliseconds }
Wait-Job -Job $jobs | Out-Null
$items = @($jobs | ForEach-Object { Receive-Job -Job $_ })
$jobs | Remove-Job -Force
$latencies = @($items | Where-Object { $_.status -ne 0 } | ForEach-Object { [double]$_.latency_ms } | Sort-Object)
$total = $items.Count
$success = @($items | Where-Object { $_.status -ge 200 -and $_.status -lt 300 }).Count
$failures = $total - $success
$quantile = {
    param([double[]] $Values, [double] $Q)
    if ($Values.Count -eq 0) { return $null }
    $rank = ($Values.Count - 1) * $Q
    $lo = [Math]::Floor($rank)
    $hi = [Math]::Ceiling($rank)
    if ($lo -eq $hi) { return [Math]::Round($Values[$lo], 3) }
    return [Math]::Round($Values[$lo] + (($Values[$hi] - $Values[$lo]) * ($rank - $lo)), 3)
}
$windowSeconds = ($deadline - $started).TotalSeconds
$summary = [ordered]@{
    experiment_window = [ordered]@{
        started_utc = $started.ToString('o'); ended_utc = [DateTimeOffset]::UtcNow.ToString('o'); planned_duration_seconds = $DurationSeconds; actual_window_seconds = [Math]::Round($windowSeconds, 3)
    }
    load = [ordered]@{ vus = $Vus; interval_ms_per_worker = $IntervalMilliseconds; endpoint = "$BaseUrl/order/{ord-001..003}" }
    metrics = [ordered]@{
        requests = $total; successful_2xx = $success; failed_or_non_2xx = $failures; availability_pct = if ($total) { [Math]::Round(($success / $total) * 100, 3) } else { 0 }; error_rate_pct = if ($total) { [Math]::Round(($failures / $total) * 100, 3) } else { 0 }; throughput_rps = if ($windowSeconds) { [Math]::Round($total / $windowSeconds, 3) } else { 0 }; latency_p95_ms = & $quantile $latencies 0.95; latency_p99_ms = & $quantile $latencies 0.99; latency_avg_ms = if ($latencies.Count) { [Math]::Round((($latencies | Measure-Object -Average).Average), 3) } else { $null }
    }
    requests = $items
}
$json = $summary | ConvertTo-Json -Depth 8
$outputDirectory = Split-Path -Parent $OutputJson
if ([string]::IsNullOrWhiteSpace($outputDirectory)) {
    $outputDirectory = (Get-Location).Path
} else {
    $outputDirectory = (Resolve-Path $outputDirectory).Path
}
$outputPath = Join-Path $outputDirectory (Split-Path -Leaf $OutputJson)
[System.IO.File]::WriteAllText($outputPath, $json)
$json
