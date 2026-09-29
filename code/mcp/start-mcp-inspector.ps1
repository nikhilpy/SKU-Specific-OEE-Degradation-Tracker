# start-mcp-inspector.ps1
# Reads credentials from .env and DYNAMICALLY GENERATES mcp.json at runtime.
# mcp.json is listed in .gitignore — credentials are NEVER committed to git.

$rootFolder = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$envFile    = Join-Path $rootFolder ".env"
$mcpConfig  = Join-Path $PSScriptRoot "mcp.json"

if (-not (Test-Path $envFile)) {
    Write-Error ".env file not found at: $envFile"
    exit 1
}

# --- Step 1: Parse .env into a hashtable ---
$env = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line -split "=", 2
        if ($parts.Length -eq 2) {
            $env[$parts[0].Trim()] = $parts[1].Trim().Trim('"')
        }
    }
}

$token  = $env["SLACK_BOT_TOKEN"]
$teamId = $env["SLACK_TEAM_ID"]

if (-not $token -or -not $teamId) {
    Write-Error "SLACK_BOT_TOKEN or SLACK_TEAM_ID missing from .env"
    exit 1
}

Write-Host "  [.env] SLACK_BOT_TOKEN loaded" -ForegroundColor Green
Write-Host "  [.env] SLACK_TEAM_ID loaded" -ForegroundColor Green

# --- Step 2: Generate mcp.json with credentials injected ---
$mcpJson = @"
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "$token",
        "SLACK_TEAM_ID": "$teamId"
      }
    }
  }
}
"@

[System.IO.File]::WriteAllText($mcpConfig, $mcpJson, [System.Text.UTF8Encoding]::new($false))
Write-Host "  [mcp.json] Generated with credentials from .env" -ForegroundColor Yellow
Write-Host ""

# --- Step 3: Launch MCP Inspector with the generated config ---
Write-Host "Starting MCP Inspector with Slack server..." -ForegroundColor Cyan
npx @modelcontextprotocol/inspector --config "$mcpConfig" --server slack
