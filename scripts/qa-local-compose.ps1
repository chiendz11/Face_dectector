Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
	[ValidateSet("up", "down", "restart", "logs", "ps", "qa")]
	[string]$Action = "qa",
	[switch]$Build,
	[switch]$NoCache,
	[switch]$Follow,
	[switch]$IncludeEdge
)

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$composeFiles = @(
	"docker-compose.yml",
	"docker-compose.dev.yml"
)

if ($IncludeEdge) {
	$composeFiles += "docker-compose.edge.yml"
}

$composePrefix = @("compose")
foreach ($file in $composeFiles) {
	$composePrefix += @("-f", $file)
}

function Invoke-Compose {
	param(
		[Parameter(Mandatory = $true)]
		[string[]]$Args
	)

	& docker @composePrefix @Args
	if ($LASTEXITCODE -ne 0) {
		exit $LASTEXITCODE
	}
}

function Wait-HttpOk {
	param(
		[Parameter(Mandatory = $true)]
		[string]$Url,
		[int]$MaxAttempts = 30,
		[int]$DelaySeconds = 2
	)

	for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
		try {
			$response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 5
			if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
				Write-Host "[ok] $Url -> HTTP $($response.StatusCode)"
				return
			}
		}
		catch {
			# Service may still be starting.
		}

		Write-Host "[wait] $Url (attempt $attempt/$MaxAttempts)"
		Start-Sleep -Seconds $DelaySeconds
	}

	throw "Timed out waiting for $Url"
}

function Run-QaSmoke {
	Write-Host "Running QA local smoke checks..."
	Wait-HttpOk -Url "http://localhost/api/health"
	Wait-HttpOk -Url "http://localhost/admin/"
}

switch ($Action) {
	"up" {
		$args = @("up", "-d")
		if ($Build) {
			if ($NoCache) {
				Invoke-Compose -Args @("build", "--no-cache")
			}
			else {
				Invoke-Compose -Args @("build")
			}
		}
		Invoke-Compose -Args $args
		Invoke-Compose -Args @("ps")
	}

	"down" {
		Invoke-Compose -Args @("down", "--remove-orphans")
	}

	"restart" {
		Invoke-Compose -Args @("down", "--remove-orphans")
		Invoke-Compose -Args @("up", "-d")
		Invoke-Compose -Args @("ps")
	}

	"logs" {
		$args = @("logs")
		if ($Follow) {
			$args += "-f"
		}
		Invoke-Compose -Args $args
	}

	"ps" {
		Invoke-Compose -Args @("ps")
	}

	"qa" {
		Invoke-Compose -Args @("up", "-d")
		Run-QaSmoke
		Invoke-Compose -Args @("ps")
	}
}
