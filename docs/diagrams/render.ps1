# Regenerate SVGs from *.mmd using Mermaid CLI (requires Node/npm).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Get-ChildItem -Filter *.mmd | ForEach-Object {
    $out = $_.BaseName + ".svg"
    Write-Host "Rendering $($_.Name) -> $out"
    npx --yes @mermaid-js/mermaid-cli -i $_.Name -o $out
}
