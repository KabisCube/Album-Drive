# Publishes a new release: checks the repo, runs the tests, sets APP_VERSION, opens Notepad for the
# release notes, then commits, tags vX.Y.Z and pushes. GitHub Actions builds Windows, Linux and Android
# and publishes them under Releases.
param([string]$Version)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Stop-Release([string]$reason) {
	Write-Host $reason -ForegroundColor Red
	exit 1
}

function Invoke-Git {
	$ErrorActionPreference = 'Continue'
	$output = & git @args 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { Stop-Release "git $($args -join ' ') failed:`n$($output -join "`n")" }
	return $output
}

$identityFile = Join-Path $root 'src\app_identity.py'
$identity = [IO.File]::ReadAllText($identityFile)
$versionPattern = "(?m)^APP_VERSION = '([^']*)'"
$releasedVersions = @(& git tag --list) + [regex]::Match($identity, $versionPattern).Groups[1].Value |
	ForEach-Object { if ($_ -match '^v?\.?(\d+\.\d+\.\d+)$') { [version]$Matches[1] } }
$latestVersion = $releasedVersions | Sort-Object -Descending | Select-Object -First 1
if (-not $latestVersion) { $latestVersion = [version]'0.0.0' }
$suggested = "$($latestVersion.Major).$($latestVersion.Minor).$($latestVersion.Build + 1)"

Write-Host "Latest release: $latestVersion"
if (-not $Version) {
	$Version = Read-Host "New version (Enter for $suggested)"
	if (-not $Version) { $Version = $suggested }
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { Stop-Release "Version must look like 1.2.3, got '$Version'." }
if ([version]$Version -le $latestVersion) { Stop-Release "Version $Version must be newer than $latestVersion." }
$tag = "v$Version"

if (Invoke-Git status --porcelain) { Stop-Release 'You have uncommitted changes. Commit or stash them first.' }
$branch = (Invoke-Git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne 'main') { Stop-Release "Releases are made from main, but you are on '$branch'." }
Invoke-Git fetch origin main --tags | Out-Null
if ((Invoke-Git rev-list --count 'HEAD..origin/main').Trim() -ne '0') { Stop-Release 'GitHub has commits you do not have. Pull first.' }
if (Invoke-Git tag --list $tag) { Stop-Release "Tag $tag already exists." }

Write-Host 'Running tests...'
$python = Join-Path $root '.venv-windows\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python (Join-Path $root 'scripts\test.py')
if ($LASTEXITCODE -ne 0) { Stop-Release 'Tests failed. Nothing was released.' }

$notesFolder = Join-Path $root 'docs\release-notes'
$notesFile = Join-Path $notesFolder "$Version.md"
New-Item -ItemType Directory -Force $notesFolder | Out-Null
if (-not (Test-Path -LiteralPath $notesFile)) { [IO.File]::WriteAllText($notesFile, '') }
Write-Host "Write what changed in $Version, then save and close Notepad."
Start-Process notepad.exe -ArgumentList "`"$notesFile`"" -Wait
if (-not [IO.File]::ReadAllText($notesFile).Trim()) {
	Remove-Item -LiteralPath $notesFile
	Stop-Release 'The release notes are empty. Nothing was released.'
}

$identity = [regex]::Replace($identity, $versionPattern, "APP_VERSION = '$Version'")
[IO.File]::WriteAllText($identityFile, $identity)

Write-Host "Releasing $tag..."
Invoke-Git add -- $identityFile $notesFile | Out-Null
Invoke-Git commit -m "Release $Version" | Out-Null
Invoke-Git tag -a $tag -m "Album Drive $Version" | Out-Null
Invoke-Git push --atomic origin main $tag | Out-Null
Write-Host "Done. GitHub is now building $tag; the release appears under Releases when all builds pass." -ForegroundColor Green
