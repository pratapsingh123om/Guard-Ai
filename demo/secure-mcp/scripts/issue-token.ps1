$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $demoRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment was not found: $python"
}

& $python (Join-Path $PSScriptRoot 'issue-demo-token.py') `
    --private-key (Join-Path $demoRoot 'runtime\tokens\issuer-private.pem') `
    --client-cert (Join-Path $demoRoot 'runtime\certs\interop\client.crt') `
    --output (Join-Path $demoRoot 'runtime\tokens\coordinator.jwt')
if ($LASTEXITCODE -ne 0) {
    throw 'Demo token issuance failed.'
}
