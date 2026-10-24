param(
    [string]$AetherisRoot = (Join-Path $PSScriptRoot '../dependencies/aetheris'),
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../artifacts/local/build'),
    [string]$Python = 'python',
    [string]$DesignRoot = (Join-Path $PSScriptRoot '..'),
    [switch]$CompilerControl,
    [switch]$PartsOnly
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DesignRoot = (Resolve-Path $DesignRoot).Path
$AetherisRoot = (Resolve-Path $AetherisRoot).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path $OutputDirectory) { throw 'Use a fresh output directory for qualification.' }
Push-Location $DesignRoot
try {
    $pin = (Get-Content aetheris-revision.txt -Raw).Trim()
    $actual = (& git -C $AetherisRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $pin -notmatch '^[0-9a-f]{40}$') { throw 'Invalid compiler revision.' }
    if ($actual -ne $pin -and !$CompilerControl) { throw 'Aetheris checkout does not match the reviewed revision.' }
    if ($CompilerControl -and !$PartsOnly) { throw 'Compiler control must rebuild historical parts only.' }
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
        if (!$PartsOnly) {
            & $Python (Join-Path $repository 'scripts/qualify_assembly.py') --directory $directory --cli $cli --reconstructor (Join-Path $AetherisRoot 'fixtures/Regression/ComposeHoleFamilies/reconstruct_bracket_pdf.py')
            if ($LASTEXITCODE -ne 0) { throw "Assembly qualification failed: $case" }
        }
    }
    $packageArguments = @('--input', $OutputDirectory, '--output', (Join-Path $OutputDirectory 'deliverables'), '--aetheris', $actual, '--design-root', $DesignRoot, '--source-compiler', $pin)
    if ($PartsOnly) { $packageArguments += '--parts-only' }
    & $Python (Join-Path $repository 'scripts/package_artifacts.py') @packageArguments
    if ($LASTEXITCODE -ne 0) { throw 'Deliverable qualification failed.' }
}
finally { Pop-Location }
