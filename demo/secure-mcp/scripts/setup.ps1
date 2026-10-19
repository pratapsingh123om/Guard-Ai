param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $demoRoot 'compose.yaml'

$pkiArguments = @()
if ($Force) {
    $pkiArguments += '-Force'
}
& (Join-Path $PSScriptRoot 'generate-pki.ps1') @pkiArguments
& (Join-Path $PSScriptRoot 'issue-token.ps1')

docker compose -f $composeFile --profile client build
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose build failed.'
}
docker compose -f $composeFile up -d --wait --wait-timeout 120 guard-ai
if ($LASTEXITCODE -ne 0) {
    throw 'Guard-AI demo startup failed.'
}

Write-Output 'Guard-AI secure MCP demo is starting on ports 8443 and 9443.'
