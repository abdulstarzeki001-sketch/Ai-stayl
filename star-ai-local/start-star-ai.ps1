# STAR AI Windows launcher: local-only or remote over PRIVATE Tailscale Serve.
# No inbound Windows firewall ports, public tunnels or Tailscale Funnel.
[CmdletBinding()]
param([switch]$Remote)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Local mode stays strictly on 127.0.0.1, and disables remote trust.
Remove-Item Env:STAR_AI_TAILSCALE_HOST -ErrorAction SilentlyContinue
Remove-Item Env:STAR_AI_TAILSCALE_LOGIN -ErrorAction SilentlyContinue
$tailscaleExe = $null

if ($Remote) {
    $tailscaleCmd = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tailscaleCmd) {
        $tailscaleExe = $tailscaleCmd.Source
    } else {
        $standardExe = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
        if (Test-Path $standardExe) { $tailscaleExe = $standardExe }
    }
    if (-not $tailscaleExe) {
        throw "Tailscale is not installed. Install it on Windows and iPhone and sign into the same tailnet."
    }

    $json = & $tailscaleExe status --json
    if ($LASTEXITCODE -ne 0) { throw "Tailscale is not connected. Open Tailscale and sign in." }
    $ts = $json | ConvertFrom-Json
    if (-not $ts.Self.Online) { throw "This Windows laptop is offline in Tailscale." }

    $tailnetHost = ([string]$ts.Self.DNSName).TrimEnd(".").ToLowerInvariant()
    if (-not $tailnetHost.EndsWith(".ts.net")) {
        throw "Tailscale MagicDNS hostname is unavailable. Enable MagicDNS and HTTPS certificates."
    }

    $userID = [string]$ts.Self.UserID
    $userEntry = @($ts.User.PSObject.Properties | Where-Object { $_.Name -eq $userID } | Select-Object -First 1)
    $tailnetLogin = if ($userEntry.Count) { [string]$userEntry[0].Value.LoginName } else { "" }
    if (-not $tailnetLogin) {
        throw "Cannot identify your Tailscale login. Check the local Tailscale account configuration."
    }
    $env:STAR_AI_TAILSCALE_HOST = $tailnetHost
    $env:STAR_AI_TAILSCALE_LOGIN = $tailnetLogin.ToLowerInvariant()

    Write-Host "Starting private Tailscale Serve (NOT Funnel)..." -ForegroundColor Cyan
    & $tailscaleExe serve --bg 17849
    if ($LASTEXITCODE -ne 0) {
        throw "Could not start Tailscale Serve. Enable HTTPS certificates as prompted by Tailscale."
    }
    Write-Host "Private iPhone URL: https://$tailnetHost/" -ForegroundColor Green
    Write-Host "Allowed Tailscale identity: $tailnetLogin"
}

Write-Host "Local Windows URL: http://127.0.0.1:17849/" -ForegroundColor Green
Write-Host "Do not close this window while you want the laptop to accept requests."
try {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3 -X utf8 (Join-Path $PSScriptRoot "star_ai_web.py")
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "Python not found. Install Python 3, then retry." }
        & $python.Source -X utf8 (Join-Path $PSScriptRoot "star_ai_web.py")
    }
} finally {
    if ($Remote -and $tailscaleExe) {
        # Fail closed: stop sharing after STAR AI exits.
        & $tailscaleExe serve --https=443 off | Out-Null
    }
}
