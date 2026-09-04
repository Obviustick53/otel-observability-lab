[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string]$Region,
  [string]$StackPrefix = 'otel-lab-sandbox',
  [switch]$ConfirmCleanup
)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmCleanup) { throw 'Bloqueado: cleanup destructivo requiere -ConfirmCleanup.' }
$env:AWS_REGION = $Region
foreach ($stack in @("$StackPrefix-apps", "$StackPrefix-observability", "$StackPrefix-network")) {
  $exists = aws cloudformation describe-stacks --stack-name $stack --region $Region --query 'Stacks[0].StackName' --output text 2>$null
  if ($LASTEXITCODE -eq 0 -and $exists -eq $stack) {
    aws cloudformation delete-stack --stack-name $stack --region $Region
    aws cloudformation wait stack-delete-complete --stack-name $stack --region $Region
  }
}
aws cloudformation list-stacks --region $Region --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE --query "StackSummaries[?starts_with(StackName, '$StackPrefix')].StackName" --output json | Set-Content 'screenshoot\integrator_project\05_aws_deployment\cleanup-residual-check.json' -Encoding utf8
