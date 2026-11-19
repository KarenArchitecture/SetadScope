[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "rebuild", "status", "logs", "collect", "build", "help")]
    [string]$Command = "help",

    [ValidateRange(1, 2147483647)]
    [int]$StartPage = 1,

    [ValidateRange(1, 2147483647)]
    [int]$EndPage = 3
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Invoke-Compose {
    param([string[]]$ComposeArgs)

    Write-Host ("> docker compose " + ($ComposeArgs -join " ")) -ForegroundColor DarkGray
    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "SetadScope project manager" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\setad.ps1 start                 Start database, backend and frontend"
    Write-Host "  .\setad.ps1 stop                  Stop containers; keep database data"
    Write-Host "  .\setad.ps1 restart               Restart running containers"
    Write-Host "  .\setad.ps1 rebuild               Rebuild images and recreate services"
    Write-Host "  .\setad.ps1 status                Show service status"
    Write-Host "  .\setad.ps1 logs                  Follow service logs (Ctrl+C to stop)"
    Write-Host "  .\setad.ps1 collect               Fetch pages 1-3 and import latest run"
    Write-Host "  .\setad.ps1 collect -StartPage 1 -EndPage 5"
    Write-Host "  .\setad.ps1 build                 Build images without starting services"
    Write-Host ""
}

if ($Command -eq "help") {
    Show-Help
    exit 0
}

Push-Location $ProjectRoot
try {
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            throw "Created .env from .env.example. Set POSTGRES_PASSWORD and the matching password in DATABASE_URL, then run the command again."
        }
        throw ".env is missing and .env.example was not found."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Engine is not available. Start Docker Desktop and try again."
    }

    switch ($Command) {
        "start" {
            New-Item -ItemType Directory -Force -Path "data/raw" | Out-Null
            Invoke-Compose -ComposeArgs @("up", "-d", "--build")
            Write-Host "SetadScope is starting. Frontend: http://localhost:5173" -ForegroundColor Green
            Write-Host "API docs: http://localhost:18080/docs"
        }
        "stop" {
            Invoke-Compose -ComposeArgs @("stop")
            Write-Host "Containers stopped. PostgreSQL volume was preserved." -ForegroundColor Green
        }
        "restart" {
            Invoke-Compose -ComposeArgs @("restart")
        }
        "rebuild" {
            Invoke-Compose -ComposeArgs @("up", "-d", "--build", "--force-recreate")
        }
        "status" {
            Invoke-Compose -ComposeArgs @("ps", "-a")
        }
        "logs" {
            Invoke-Compose -ComposeArgs @("logs", "--tail=100", "--follow")
        }
        "build" {
            Invoke-Compose -ComposeArgs @("build")
        }
        "collect" {
            if ($EndPage -lt $StartPage) {
                throw "EndPage must be greater than or equal to StartPage."
            }
            New-Item -ItemType Directory -Force -Path "data/raw" | Out-Null
            Invoke-Compose -ComposeArgs @("up", "-d", "--build")
            Invoke-Compose -ComposeArgs @(
                "run", "--rm", "collector",
                "--start-page", $StartPage.ToString(),
                "--end-page", $EndPage.ToString()
            )
            Invoke-Compose -ComposeArgs @("run", "--rm", "ingest")
            Write-Host "Collection and database import completed." -ForegroundColor Green
            Write-Host "Refresh http://localhost:5173 to view the current active listings."
        }
    }
}
catch {
    Write-Error $_
    exit 1
}
finally {
    Pop-Location
}
