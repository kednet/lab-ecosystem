# scripts/download-fonts.ps1
#
# Downloads cyrillic woff2-fonts from Google Fonts into public/fonts/
# (needed because fonts.googleapis.com and fonts.gstatic.com are blocked in RU).
#
# Source: Google Fonts Helper JSON API. We parse the metadata, pick the
# weights/styles we need, and fetch woff2 directly from gstatic.
#
# Run (PowerShell):
#   powershell -ExecutionPolicy Bypass -File C:\Users\kfigh\lab_site\scripts\download-fonts.ps1
#
# Re-running is safe: existing files are skipped.

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $PSScriptRoot
$out     = Join-Path $root "public\fonts"
$logPath = Join-Path $root "tmp\fonts-download.log"

New-Item -ItemType Directory -Force -Path $out   | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null

function Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $logPath -Value $line -Encoding UTF8
}

$fonts = @(
    @{ FamilyId = "manrope";          FamilyName = "manrope";          Weights = @{ 400 = "n"; 500 = "n"; 600 = "n"; 700 = "n" } }
    @{ FamilyId = "dm-serif-display"; FamilyName = "dm-serif-display"; Weights = @{ 400 = "ni" } }
    @{ FamilyId = "dancing-script";   FamilyName = "dancing-script";   Weights = @{ 400 = "n"; 500 = "n" } }
)

$weightMap = @{
    "thin"       = 100
    "extralight" = 200
    "light"      = 300
    "regular"    = 400
    "italic"     = 400
    "medium"     = 500
    "mediumitalic" = 500
    "semibold"   = 600
    "semibolditalic" = 600
    "bold"       = 700
    "bolditalic" = 700
    "extrabold"  = 800
    "black"      = 900
}

function Get-Woff2([string]$url, [string]$dest) {
    if (Test-Path $dest) {
        $existing = (Get-Item $dest).Length
        Log ("  = already exists, " + [math]::Round($existing/1024, 1) + " KB")
        return $true
    }
    try {
        Log ("  v " + (Split-Path $dest -Leaf))
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 60
        $size = (Get-Item $dest).Length
        Log ("    OK, " + [math]::Round($size/1024, 1) + " KB")
        return $true
    } catch {
        Log ("    ! Error: " + $_.Exception.Message)
        return $false
    }
}

$stats = @{ downloaded = 0; skipped = 0; failed = 0 }

foreach ($f in $fonts) {
    $id   = $f.FamilyId
    $name = $f.FamilyName
    Log ("-> " + $name)

    $apiUrl = "https://gwfh.mranftl.com/api/fonts/" + $id
    $json = ""
    try {
        $json = (Invoke-WebRequest -Uri $apiUrl -UseBasicParsing -TimeoutSec 30).Content
    } catch {
        Log ("  ! Metadata fetch failed: " + $_.Exception.Message)
        $stats.failed++
        continue
    }
    $meta = $json | ConvertFrom-Json

    foreach ($variant in $meta.variants) {
        $wId  = $variant.id
        $wNum = 0
        if ($weightMap.ContainsKey($wId)) { $wNum = $weightMap[$wId] } else { $wNum = [int]$wId }
        $isItalic = $variant.fontStyle -eq "italic"

        if (-not $f.Weights.ContainsKey($wNum)) { continue }
        $slot = $f.Weights[$wNum]
        $needNormal = $slot.Contains("n")
        $needItalic = $slot.Contains("i")
        if ($isItalic -and -not $needItalic) { continue }
        if (-not $isItalic -and -not $needNormal) { continue }

        $woff2Url = $variant.woff2
        if (-not $woff2Url) { continue }

        $suffix = if ($isItalic) { "-" + $wNum + "-italic" } else { "-" + $wNum }
        $filename = $name + $suffix + ".woff2"
        $dest = Join-Path $out $filename

        if (Test-Path $dest) {
            $stats.skipped++
        } else {
            $ok = Get-Woff2 $woff2Url $dest
            if ($ok) { $stats.downloaded++ } else { $stats.failed++ }
        }
    }
}

Log "----- TOTAL -----"
Log ("Downloaded: " + $stats.downloaded)
Log ("Skipped (already exists): " + $stats.skipped)
Log ("Failed: " + $stats.failed)
Log ("Directory: " + $out)
