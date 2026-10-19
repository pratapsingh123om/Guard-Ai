$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
docker compose -f (Join-Path $demoRoot 'compose.yaml') down
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose shutdown failed.'
}
