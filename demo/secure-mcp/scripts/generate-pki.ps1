param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runtimeRoot = Join-Path $demoRoot 'runtime'
$certRoot = Join-Path $runtimeRoot 'certs'
$tokenRoot = Join-Path $runtimeRoot 'tokens'
$serverExt = Join-Path $demoRoot 'pki\server.ext'
$clientExt = Join-Path $demoRoot 'pki\client.ext'

function Invoke-OpenSSL {
    param(
        [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
        [string[]]$OpenSslArgs
    )
    & openssl @OpenSslArgs
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL failed: openssl $($OpenSslArgs -join ' ')"
    }
}

if ((Test-Path -LiteralPath $certRoot) -or (Test-Path -LiteralPath $tokenRoot)) {
    if (-not $Force) {
        throw 'Runtime certificates or tokens already exist. Re-run with -Force to replace demo-only material.'
    }
    $expectedRuntime = Join-Path $demoRoot 'runtime'
    if ([IO.Path]::GetFullPath($runtimeRoot) -ne [IO.Path]::GetFullPath($expectedRuntime)) {
        throw "Unexpected runtime cleanup target: $runtimeRoot"
    }
    foreach ($target in @($certRoot, $tokenRoot)) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

New-Item -ItemType Directory -Path $certRoot, $tokenRoot -Force | Out-Null

function New-Profile {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][ValidateSet('ecdsa', 'mldsa')][string]$Kind
    )

    $profile = Join-Path $certRoot $Name
    New-Item -ItemType Directory -Path $profile -Force | Out-Null
    $caKey = Join-Path $profile 'ca.key'
    $caCert = Join-Path $profile 'ca.crt'
    $serverKey = Join-Path $profile 'server.key'
    $serverCsr = Join-Path $profile 'server.csr'
    $serverCert = Join-Path $profile 'server.crt'
    $clientKey = Join-Path $profile 'client.key'
    $clientCsr = Join-Path $profile 'client.csr'
    $clientCert = Join-Path $profile 'client.crt'

    if ($Kind -eq 'ecdsa') {
        Invoke-OpenSSL @('ecparam', '-genkey', '-name', 'secp384r1', '-out', $caKey)
        Invoke-OpenSSL @('req', '-x509', '-new', '-key', $caKey, '-sha384', '-days', '1', '-out', $caCert,
            '-subj', '/CN=Guard-AI Demo Interop CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        Invoke-OpenSSL @('ecparam', '-genkey', '-name', 'secp384r1', '-out', $serverKey)
        Invoke-OpenSSL @('req', '-new', '-key', $serverKey, '-sha384', '-out', $serverCsr,
            '-subj', '/CN=guard-ai.demo')
        Invoke-OpenSSL @('x509', '-req', '-in', $serverCsr, '-CA', $caCert, '-CAkey', $caKey,
            '-CAcreateserial', '-days', '1', '-sha384', '-extfile', $serverExt, '-out', $serverCert)
        Invoke-OpenSSL @('ecparam', '-genkey', '-name', 'secp384r1', '-out', $clientKey)
        Invoke-OpenSSL @('req', '-new', '-key', $clientKey, '-sha384', '-out', $clientCsr,
            '-subj', '/CN=coordinator-agent')
        Invoke-OpenSSL @('x509', '-req', '-in', $clientCsr, '-CA', $caCert, '-CAkey', $caKey,
            '-CAcreateserial', '-days', '1', '-sha384', '-extfile', $clientExt, '-out', $clientCert)
    }
    else {
        Invoke-OpenSSL @('genpkey', '-algorithm', 'ML-DSA-65', '-out', $caKey)
        Invoke-OpenSSL @('req', '-x509', '-new', '-key', $caKey, '-days', '1', '-out', $caCert,
            '-subj', '/CN=Guard-AI Demo Strict PQC CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
        Invoke-OpenSSL @('genpkey', '-algorithm', 'ML-DSA-65', '-out', $serverKey)
        Invoke-OpenSSL @('req', '-new', '-key', $serverKey, '-out', $serverCsr,
            '-subj', '/CN=guard-ai.demo')
        Invoke-OpenSSL @('x509', '-req', '-in', $serverCsr, '-CA', $caCert, '-CAkey', $caKey,
            '-CAcreateserial', '-days', '1', '-extfile', $serverExt, '-out', $serverCert)
        Invoke-OpenSSL @('genpkey', '-algorithm', 'ML-DSA-65', '-out', $clientKey)
        Invoke-OpenSSL @('req', '-new', '-key', $clientKey, '-out', $clientCsr,
            '-subj', '/CN=coordinator-agent')
        Invoke-OpenSSL @('x509', '-req', '-in', $clientCsr, '-CA', $caCert, '-CAkey', $caKey,
            '-CAcreateserial', '-days', '1', '-extfile', $clientExt, '-out', $clientCert)
    }

    Remove-Item -LiteralPath $serverCsr, $clientCsr -Force
}

New-Profile -Name 'interop' -Kind 'ecdsa'
New-Profile -Name 'strict' -Kind 'mldsa'

$issuerPrivate = Join-Path $tokenRoot 'issuer-private.pem'
$issuerPublic = Join-Path $tokenRoot 'issuer-public.pem'
Invoke-OpenSSL @('ecparam', '-genkey', '-name', 'prime256v1', '-out', $issuerPrivate)
Invoke-OpenSSL @('pkey', '-in', $issuerPrivate, '-pubout', '-out', $issuerPublic)

Write-Output "Generated demo-only PKI under $runtimeRoot"
