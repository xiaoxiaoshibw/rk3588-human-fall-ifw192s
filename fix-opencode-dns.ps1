#Requires -RunAsAdministrator
# Root-fix for opencode connectivity on this network:
#   1) replace hijacked router DNS (61.155.18.30) with 223.5.5.5 / 119.29.29.29
#   2) pin opencode.ai / models.dev in hosts (IPs verified direct-HTTPS 200)
#   3) flush DNS cache and verify with no-proxy curl
#      (any request still exiting via 127.0.0.1 proxy counts as failure)
# Rollback: run elevated   powershell -File D:\Code\ldiar\fix-opencode-dns.ps1 -Rollback
param([switch]$Rollback)

$ErrorActionPreference = 'Stop'
$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$marker    = '# opencode-direct'

if ($Rollback) {
    Set-DnsClientServerAddress -InterfaceAlias 'WLAN' -ResetServerAddresses
    (Get-Content $hostsPath) | Where-Object { $_ -notmatch [regex]::Escape($marker) } |
        Set-Content $hostsPath -Encoding ASCII
    Clear-DnsClientCache
    Write-Host '[rollback] WLAN DNS reset to automatic; hosts pins removed.'
    exit 0
}

Write-Host '[1/4] DNS: 61.155.18.30 (hijacked router) -> 223.5.5.5 / 119.29.29.29'
Set-DnsClientServerAddress -InterfaceAlias 'WLAN' -ServerAddresses ('223.5.5.5','119.29.29.29')

Write-Host '[2/4] hosts: pin opencode.ai x4 (failover) + zen alias + models.dev'
Add-Content $hostsPath -Encoding ASCII @"

$marker 2026-10-05 router-DNS-hijack bypass; retest after changing ISP and remove if stale
$marker zen.opencode.ai is NXDOMAIN upstream; alias to apex is load-bearing
172.65.90.20 opencode.ai $marker
172.65.90.21 opencode.ai $marker
172.65.90.22 opencode.ai $marker
172.65.90.23 opencode.ai $marker
172.65.90.20 zen.opencode.ai $marker
104.26.8.108 models.dev $marker
"@

Write-Host '[3/4] flush DNS cache'
Clear-DnsClientCache
ipconfig /flushdns | Out-Null

Write-Host '[4/4] no-proxy verify (remote_ip must be a real IP; 127.0.0.1 means still proxied = fail)'
$ok = $true
$expect = @{ 'opencode.ai' = '172\.65\.90\.'; 'models.dev' = '104\.26\.|172\.67\.' }
foreach ($d in @('opencode.ai','models.dev')) {
    $r = & curl.exe -sS --noproxy '*' --max-time 20 -o NUL -w "%{http_code} %{remote_ip}" "https://$d/" 2>&1
    Write-Host "  $d -> $r"
    if ($r -notmatch '^200 ' -or $r -match '127\.0\.0\.1' -or $r -notmatch $expect[$d]) {
        Write-Host "    ^ FAIL (want 200 + pinned subnet)"
        $ok = $false
    }
}
if (-not $ok) { Write-Host 'verify FAILED -- paste the output back for diagnosis.'; exit 1 }
Write-Host ''
Write-Host 'ALL PASSED. Bare shells (no proxy env vars) can now run opencode direct.'
Write-Host 'Note: system proxy 127.0.0.1:10808 is still on; new windows that inherit it'
Write-Host 'will keep using the proxy (same result while proxy is alive). To go fully'
Write-Host 'direct, disable system proxy in your proxy client or add direct rules for'
Write-Host 'these two domains.'
