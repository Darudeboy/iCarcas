# Push main + tags to GitVerse. Run in the same shell where token is set:
#   $env:GITVERSE_TOKEN = "..."
#   .\scripts\push-gitverse.ps1

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($env:GITVERSE_TOKEN)) {
    Write-Host 'Set $env:GITVERSE_TOKEN first (do not commit the token).'
    exit 1
}

$user = if ($env:GITVERSE_USER) { $env:GITVERSE_USER } else { 'klas' }
$authUrl = "https://${user}:$($env:GITVERSE_TOKEN)@gitverse.ru/klas/iCarcas.git"

Write-Host "Pushing main -> gitverse..."
git push $authUrl main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Pushing tags -> gitverse..."
git push $authUrl --tags
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git remote set-url gitverse https://gitverse.ru/klas/iCarcas.git
Write-Host "Done. Remote URL cleaned (token not stored in git remote)."
Write-Host "https://gitverse.ru/klas/iCarcas"
