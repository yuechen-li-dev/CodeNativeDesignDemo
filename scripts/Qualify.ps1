param(
    [string]$AetherisRoot = (Join-Path $PSScriptRoot '../dependencies/aetheris'),
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../artifacts/local/build'),
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$AetherisRoot = (Resolve-Path $AetherisRoot).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
Push-Location $repository
try {
    $pin = (Get-Content aetheris-revision.txt -Raw).Trim()
    $actual = (& git -C $AetherisRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $pin -notmatch '^[0-9a-f]{40}$' -or $actual -ne $pin) { throw 'Aetheris checkout does not match the reviewed revision.' }
    $dirty = & git -C $AetherisRoot status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Aetheris tracked source must be clean.' }
    & dotnet build (Join-Path $AetherisRoot 'Aetheris.CLI') -c Release -m:1 -nr:false -p:UseSharedCompilation=false
    if ($LASTEXITCODE -ne 0) { throw 'CLI build failed.' }
    & dotnet build src/CodeNativeDesignDemo.csproj -c Release -m:1 -nr:false -p:UseSharedCompilation=false "-p:AetherisRoot=$AetherisRoot"
    if ($LASTEXITCODE -ne 0) { throw 'Demo build failed.' }
    & dotnet src/bin/Release/net10.0/CodeNativeDesignDemo.dll $OutputDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Artifact generation failed.' }
    $cli = Join-Path $AetherisRoot 'Aetheris.CLI/bin/Release/net10.0/aetheris.dll'
    foreach ($case in @('nominal', 'variant')) {
        $directory = Join-Path $OutputDirectory $case
        & $Python (Join-Path $AetherisRoot 'fixtures/Regression/ComposeHoleFamilies/reconstruct_bracket_pdf.py') `
            --pdf (Join-Path $directory 'Bracket.pdf') --reference-step (Join-Path $directory 'Bracket.step') `
            --out-dir (Join-Path $directory 'pdf-reconstruction') --cli $cli
        if ($LASTEXITCODE -ne 0) { throw "PDF-only reconstruction failed: $case" }
        $admission = & dotnet $cli validate (Join-Path $directory 'bracket.firmament') --json
        if ($LASTEXITCODE -ne 0) { throw "Validation failed: $case" }
        $admission | Set-Content (Join-Path $directory 'validation.json') -Encoding utf8
    }
    & $Python scripts/package_artifacts.py --input $OutputDirectory --output (Join-Path $OutputDirectory 'deliverables') --aetheris $pin
    if ($LASTEXITCODE -ne 0) { throw 'Deliverable qualification failed.' }
}
finally { Pop-Location }
