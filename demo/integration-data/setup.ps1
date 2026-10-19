param([switch]$Force)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment was not found: $python"
}

$arguments = @((Join-Path $PSScriptRoot 'create_demo_db.py'))
if ($Force) {
    $arguments += '--force'
}
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw 'SQLite demo database creation failed.'
}
