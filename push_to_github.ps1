# PowerShell script to push project to GitHub
# Run this script after installing Git

Write-Host "=== Medical Lab Report Analyzer - GitHub Push Script ===" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
try {
    $gitVersion = git --version
    Write-Host "✓ Git is installed: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Git is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Git first:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
    Write-Host "2. Or use: winget install Git.Git" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Get current directory
$projectDir = Get-Location
Write-Host "Project directory: $projectDir" -ForegroundColor Cyan
Write-Host ""

# Check if .git exists
if (Test-Path ".git") {
    Write-Host "✓ Git repository already initialized" -ForegroundColor Green
} else {
    Write-Host "Initializing Git repository..." -ForegroundColor Yellow
    git init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to initialize git repository" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Git repository initialized" -ForegroundColor Green
}

# Check if remote exists
$remoteUrl = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Remote 'origin' already exists: $remoteUrl" -ForegroundColor Green
    $updateRemote = Read-Host "Do you want to update the remote URL? (y/n)"
    if ($updateRemote -eq "y" -or $updateRemote -eq "Y") {
        git remote set-url origin https://github.com/haniazahra9706/lab-report-analyzer.git
        Write-Host "✓ Remote URL updated" -ForegroundColor Green
    }
} else {
    Write-Host "Adding remote 'origin'..." -ForegroundColor Yellow
    git remote add origin https://github.com/haniazahra9706/lab-report-analyzer.git
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to add remote" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Remote 'origin' added" -ForegroundColor Green
}

Write-Host ""
Write-Host "Adding all files..." -ForegroundColor Yellow
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to add files" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Files staged" -ForegroundColor Green

Write-Host ""
Write-Host "Checking for changes to commit..." -ForegroundColor Yellow
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "No changes to commit. Repository is up to date." -ForegroundColor Yellow
    $pushAnyway = Read-Host "Do you want to push anyway? (y/n)"
    if ($pushAnyway -ne "y" -and $pushAnyway -ne "Y") {
        exit 0
    }
} else {
    Write-Host "Committing changes..." -ForegroundColor Yellow
    $commitMessage = "Initial commit: Medical Lab Report Analyzer with multilingual support and voice features"
    git commit -m $commitMessage
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Failed to commit changes" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Changes committed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Setting branch to 'main'..." -ForegroundColor Yellow
git branch -M main
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Warning: Failed to rename branch (may already be 'main')" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "Note: You may be prompted for GitHub credentials." -ForegroundColor Cyan
Write-Host "Use a Personal Access Token (PAT) instead of password." -ForegroundColor Cyan
Write-Host "Create PAT at: https://github.com/settings/tokens" -ForegroundColor Cyan
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "Repository: https://github.com/haniazahra9706/lab-report-analyzer" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "✗ Failed to push to GitHub" -ForegroundColor Red
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "1. Authentication failed - use Personal Access Token" -ForegroundColor Yellow
    Write-Host "2. Repository doesn't exist - create it on GitHub first" -ForegroundColor Yellow
    Write-Host "3. Network issues - check your internet connection" -ForegroundColor Yellow
    exit 1
}
