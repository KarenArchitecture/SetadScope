[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "rebuild", "status", "logs", "collect", "collect-tenders", "collect-category", "build", "help")]
    [string]$Command = "help",

    [ValidateRange(0, 2147483647)]
    [int]$StartPage = 1,

    [ValidateRange(1, 2147483647)]
    [int]$EndPage = 37,

    [ValidateSet("movable", "immovable", "rental", "minor", "clearance")]
    [string]$Category = "movable",

    [ValidateSet("executive_agencies", "amval_tamliki", "shared")]
    [string]$Group
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
    Write-Host "  .\setad.ps1 collect               Fetch all movable auction pages and import"
    Write-Host "  .\setad.ps1 collect -StartPage 1 -EndPage 5"
    Write-Host "  .\setad.ps1 collect-tenders     Fetch all tender pages and import them"
    Write-Host "  .\setad.ps1 collect-category -Category rental"
    Write-Host "  .\setad.ps1 collect-category -Category movable -Group amval_tamliki"
    Write-Host "  .\setad.ps1 collect-category -Category clearance -Group shared"
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
        "collect-tenders" {
            New-Item -ItemType Directory -Force -Path "data/raw/tenders" | Out-Null
            Invoke-Compose -ComposeArgs @("up", "-d", "--build")
            Invoke-Compose -ComposeArgs @("run", "--rm", "api", "python", "-m", "setad_scope.collectors.fetch_tenders")
            Invoke-Compose -ComposeArgs @("run", "--rm", "api", "python", "-m", "app.tender_jobs")
            Write-Host "Tender collection and database import completed." -ForegroundColor Green
            Write-Host "Refresh http://localhost:5173/tenders to view the tender listings."
        }
        "collect" {
            New-Item -ItemType Directory -Force -Path "data/raw/auctions/movable" | Out-Null
            Invoke-Compose -ComposeArgs @("up", "-d", "--build")
            $FetchArgs = @("run", "--rm", "api", "python", "-m", "setad_scope.collectors.fetch_auction_categories", "--category", "movable")
            if ($PSBoundParameters.ContainsKey("StartPage")) {
                $FetchArgs += @("--start-page", $StartPage.ToString())
            }
            if ($PSBoundParameters.ContainsKey("EndPage")) {
                $FetchArgs += @("--end-page", $EndPage.ToString())
            }
            Invoke-Compose -ComposeArgs $FetchArgs
            Invoke-Compose -ComposeArgs @("run", "--rm", "api", "python", "-m", "app.auction_category_jobs", "--category", "movable")
            Write-Host "Movable auctions collected and imported." -ForegroundColor Green
        }
        "collect-category" {
            if ($PSBoundParameters.ContainsKey("Group")) {
                $EffectiveGroup = $Group
            }
            elseif ($Category -eq "clearance") {
                $EffectiveGroup = "shared"
            }
            else {
                $EffectiveGroup = "executive_agencies"
            }

            if ($EffectiveGroup -eq "executive_agencies") {
                $RawCategoryPath = "data/raw/auctions/" + $Category
            }
            else {
                $RawCategoryPath = "data/raw/auctions/" + $EffectiveGroup + "/" + $Category
            }
            New-Item -ItemType Directory -Force -Path $RawCategoryPath | Out-Null
            Invoke-Compose -ComposeArgs @("up", "-d", "--build")

            $FetchArgs = @(
                "run", "--rm", "api", "python", "-m",
                "setad_scope.collectors.fetch_auction_categories",
                "--group", $EffectiveGroup, "--category", $Category
            )
            if ($PSBoundParameters.ContainsKey("StartPage")) {
                $FetchArgs += @("--start-page", $StartPage.ToString())
            }
            if ($PSBoundParameters.ContainsKey("EndPage")) {
                $FetchArgs += @("--end-page", $EndPage.ToString())
            }
            Invoke-Compose -ComposeArgs $FetchArgs

            $ImportArgs = @(
                "run", "--rm", "api", "python", "-m",
                "app.auction_category_jobs",
                "--group", $EffectiveGroup, "--category", $Category
            )
            Invoke-Compose -ComposeArgs $ImportArgs
            Write-Host ("Finished collecting " + $EffectiveGroup + "/" + $Category + " auctions.") -ForegroundColor Green
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
