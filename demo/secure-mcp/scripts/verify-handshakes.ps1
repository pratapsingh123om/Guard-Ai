$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$certRoot = Join-Path $demoRoot 'runtime\certs'

function Invoke-Handshake {
    param(
        [int]$Port,
        [string]$Profile,
        [string]$Group
    )
    $profileRoot = Join-Path $certRoot $Profile
    $output = "GET /health HTTP/1.0`r`nHost: guard-ai.demo`r`n`r`n" | & openssl s_client `
        -connect "127.0.0.1:$Port" `
        -servername guard-ai.demo `
        -CAfile (Join-Path $profileRoot 'ca.crt') `
        -cert (Join-Path $profileRoot 'client.crt') `
        -key (Join-Path $profileRoot 'client.key') `
        -verify_hostname guard-ai.demo `
        -tls1_3 `
        -groups $Group `
        -brief 2>&1 | Out-String
    return $output
}

$interop = Invoke-Handshake -Port 8443 -Profile 'interop' -Group 'X25519MLKEM768'
if ($interop -notmatch 'Protocol version: TLSv1.3' -or
    $interop -notmatch 'Negotiated TLS1.3 group: X25519MLKEM768' -or
    $interop -notmatch 'Verification: OK') {
    throw "Interop hybrid handshake validation failed:`n$interop"
}

$strict = Invoke-Handshake -Port 9443 -Profile 'strict' -Group 'X25519MLKEM768'
if ($strict -notmatch 'Protocol version: TLSv1.3' -or
    $strict -notmatch 'Negotiated TLS1.3 group: X25519MLKEM768' -or
    $strict -notmatch 'Signature type: mldsa65' -or
    $strict -notmatch 'Verification: OK') {
    throw "Strict PQC handshake validation failed:`n$strict"
}

Write-Output 'Interop profile: TLS 1.3 + X25519MLKEM768 + verified ECDSA mTLS'
Write-Output 'Strict profile: TLS 1.3 + X25519MLKEM768 + verified ML-DSA-65 mTLS'
