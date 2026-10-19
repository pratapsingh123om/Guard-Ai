$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$certRoot = Join-Path $demoRoot 'runtime\certs'

function Invoke-ExpectedFailure {
    param(
        [string]$Name,
        [string[]]$OpenSslArgs,
        [string]$ExpectedPattern
    )
    $output = "GET /health HTTP/1.0`r`nHost: guard-ai.demo`r`n`r`n" |
        & openssl @OpenSslArgs 2>&1 | Out-String
    if ($output -notmatch $ExpectedPattern -or $output -match 'HTTP/1\.[01] 200') {
        throw "Negative test did not produce the expected rejection: $Name`n$output"
    }
    Write-Output "Rejected as expected: $Name"
}

Invoke-ExpectedFailure -Name 'classical-only key exchange' -ExpectedPattern 'alert handshake failure' -OpenSslArgs @(
    's_client', '-connect', '127.0.0.1:8443', '-servername', 'guard-ai.demo',
    '-CAfile', (Join-Path $certRoot 'interop\ca.crt'),
    '-cert', (Join-Path $certRoot 'interop\client.crt'),
    '-key', (Join-Path $certRoot 'interop\client.key'),
    '-tls1_3', '-groups', 'X25519', '-brief'
)

Invoke-ExpectedFailure -Name 'untrusted client certificate' -ExpectedPattern '400 The SSL certificate error' -OpenSslArgs @(
    's_client', '-connect', '127.0.0.1:8443', '-servername', 'guard-ai.demo',
    '-CAfile', (Join-Path $certRoot 'interop\ca.crt'),
    '-cert', (Join-Path $certRoot 'strict\client.crt'),
    '-key', (Join-Path $certRoot 'strict\client.key'),
    '-tls1_3', '-groups', 'X25519MLKEM768', '-brief'
)

Invoke-ExpectedFailure -Name 'missing client certificate' -ExpectedPattern '400 No required SSL certificate was sent' -OpenSslArgs @(
    's_client', '-connect', '127.0.0.1:8443', '-servername', 'guard-ai.demo',
    '-CAfile', (Join-Path $certRoot 'interop\ca.crt'),
    '-tls1_3', '-groups', 'X25519MLKEM768', '-brief'
)
