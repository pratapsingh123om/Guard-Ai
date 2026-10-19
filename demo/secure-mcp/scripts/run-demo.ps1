$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $demoRoot 'compose.yaml'

& (Join-Path $PSScriptRoot 'issue-token.ps1')
docker compose -f $composeFile run --rm coordinator
if ($LASTEXITCODE -ne 0) {
    throw 'Coordinator MCP demonstration failed.'
}
