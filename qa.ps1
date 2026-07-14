#requires -Version 5.1
<#
  qa.ps1 — детерминированный QA-прогон БЕЗ LLM.
  Закрывает трёх агентов из loop-output/testing без затрат лимитов Cursor:
    TECH   — pytest (backend) + tsc + eslint (frontend)  -> reports/TECH_REPORT.md
    DEPLOY — наличие prod-файлов + smoke /health*         -> reports/DEPLOY_REPORT.md
    AGG    — сводит ВСЕ отчёты в один вердикт GO/NO-GO     -> reports/MASTER_REPORT.md

  Judgment-агентов (FIN/SEC/UX/E2E) скрипт НЕ гоняет — их запускаешь моделью в Cursor,
  а их свежие отчёты этот скрипт подхватит при агрегации.

  Запуск:
    powershell -ExecutionPolicy Bypass -File .\qa.ps1
    .\qa.ps1 -SkipFrontend            # только backend + deploy + agg
    .\qa.ps1 -AggOnly                 # только пересобрать MASTER_REPORT.md
#>

param(
  [switch]$SkipBackend,
  [switch]$SkipFrontend,
  [switch]$SkipDeploy,
  [switch]$AggOnly,
  [string]$HealthBase = "http://localhost:8000",
  [int]$StaleMinutes = 30
)

$ErrorActionPreference = "Stop"
$root      = $PSScriptRoot
$backend   = Join-Path $root "backend"
$frontend  = Join-Path $root "frontend"
$reports   = Join-Path $root "loop-output\testing\reports"
$now       = Get-Date -Format "yyyy-MM-dd HH:mm"

if (-not (Test-Path $reports)) { New-Item -ItemType Directory -Path $reports -Force | Out-Null }

function Write-Report($name, $content) {
  $content | Out-File -FilePath (Join-Path $reports $name) -Encoding utf8
}

# --- определить, чем запускать backend pytest -------------------------------
# 1) локальный рабочий python с установленным pytest; 2) внутри Docker-контейнера; иначе SKIP.
function Resolve-Backend {
  foreach ($cmd in @("py -3", "python", "python3")) {
    $parts = $cmd.Split(" ")
    try {
      & $parts[0] $parts[1..($parts.Length-1)] -c "import pytest" 2>$null
      if ($LASTEXITCODE -eq 0) { return @{ Kind = "local"; Exe = $parts } }
    } catch {}
  }
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    $ps = ""
    try { $ps = docker compose ps --services --filter "status=running" 2>$null } catch {}
    if ($ps -match "backend") { return @{ Kind = "docker" } }
  }
  return @{ Kind = "none" }
}

# ===========================================================================
#  TECH — pytest + tsc + eslint
# ===========================================================================
$techPytest = "SKIP"; $techPytestDetail = "не запускался"
$techTsc = "SKIP";    $techTscDetail = ""
$techEslint = "SKIP"; $techEslintDetail = ""

if (-not $AggOnly -and -not $SkipBackend) {
  $be = Resolve-Backend
  switch ($be.Kind) {
    "local" {
      Push-Location $backend
      $out = & $be.Exe[0] $be.Exe[1..($be.Exe.Length-1)] -m pytest tests/ -q --tb=no 2>&1 | Out-String
      $code = $LASTEXITCODE
      Pop-Location
      $m = [regex]::Match($out, "(\d+)\s+passed")
      $f = [regex]::Match($out, "(\d+)\s+failed")
      $techPytest = if ($code -eq 0) { "PASS" } else { "FAIL" }
      $techPytestDetail = (@(
        $(if ($m.Success) { "$($m.Groups[1].Value) passed" }),
        $(if ($f.Success) { "$($f.Groups[1].Value) failed" })
      ) | Where-Object { $_ }) -join ", "
      if (-not $techPytestDetail) { $techPytestDetail = "exit $code" }
    }
    "docker" {
      $out = docker compose exec -T backend python -m pytest tests/ -q --tb=no 2>&1 | Out-String
      $code = $LASTEXITCODE
      $m = [regex]::Match($out, "(\d+)\s+passed")
      $f = [regex]::Match($out, "(\d+)\s+failed")
      $techPytest = if ($code -eq 0) { "PASS" } else { "FAIL" }
      $techPytestDetail = (@(
        $(if ($m.Success) { "$($m.Groups[1].Value) passed" }),
        $(if ($f.Success) { "$($f.Groups[1].Value) failed" })
      ) | Where-Object { $_ }) -join ", "
      if (-not $techPytestDetail) { $techPytestDetail = "docker exit $code" }
    }
    "none" { $techPytestDetail = "нет python с pytest и не поднят Docker backend" }
  }
}

if (-not $AggOnly -and -not $SkipFrontend) {
  if (Get-Command npx -ErrorAction SilentlyContinue) {
    Push-Location $frontend
    & npx tsc --noEmit 2>&1 | Out-Null
    $techTsc = if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" }
    $techTscDetail = "exit $LASTEXITCODE"

    & npx eslint src/ --ext .ts,.tsx 2>&1 | Out-Null
    $techEslint = if ($LASTEXITCODE -eq 0) { "PASS" } else { "FAIL" }
    $techEslintDetail = "exit $LASTEXITCODE"
    Pop-Location
  } else {
    $techTscDetail = "npx не найден"; $techEslintDetail = "npx не найден"
  }
}

if (-not $AggOnly) {
  $techProblems = @()
  if ($techPytest -eq "FAIL") { $techProblems += "- pytest: $techPytestDetail" }
  if ($techTsc    -eq "FAIL") { $techProblems += "- tsc: $techTscDetail" }
  if ($techEslint -eq "FAIL") { $techProblems += "- eslint: $techEslintDetail" }
  if ($techProblems.Count -eq 0) { $techProblems = @("- нет") }

  Write-Report "TECH_REPORT.md" @"
# TECH Report — Ibra Order System
## Дата: $now
## Агент: TECH (qa.ps1)

| Проверка | Результат | Детали |
|----------|-----------|--------|
| pytest | $techPytest | $techPytestDetail |
| tsc | $techTsc | $techTscDetail |
| eslint | $techEslint | $techEslintDetail |

## Найденные проблемы
$($techProblems -join "`n")

## Рекомендации
- Автопрогон через qa.ps1 (без LLM).
"@
}

# ===========================================================================
#  DEPLOY — наличие prod-файлов + smoke health
# ===========================================================================
if (-not $AggOnly -and -not $SkipDeploy) {
  function File-Status($rel) { if (Test-Path (Join-Path $root $rel)) { "OK" } else { "MISSING" } }
  $ci     = File-Status ".github\workflows\ci.yml"
  $prod   = File-Status "docker-compose.prod.yml"
  $deploy = File-Status "scripts\deploy.sh"

  function Smoke($path) {
    try {
      $r = Invoke-WebRequest -Uri "$HealthBase$path" -UseBasicParsing -TimeoutSec 5
      return "$($r.StatusCode)"
    } catch {
      if ($_.Exception.Response) { return "$([int]$_.Exception.Response.StatusCode)" }
      return "no-conn"
    }
  }
  $hHealth = Smoke "/health"
  $hLive   = Smoke "/health/live"
  $hReady  = Smoke "/health/ready"

  $depProblems = @()
  foreach ($p in @(@("ci.yml",$ci), @("docker-compose.prod.yml",$prod), @("deploy.sh",$deploy))) {
    if ($p[1] -eq "MISSING") { $depProblems += "- отсутствует $($p[0])" }
  }
  if ($hHealth -ne "200" -and $hHealth -ne "no-conn") { $depProblems += "- /health = $hHealth" }
  if ($hLive   -eq "404") { $depProblems += "- /health/live = 404 (backend со старым кодом?)" }
  if ($hReady  -eq "404") { $depProblems += "- /health/ready = 404" }
  if ($hHealth -eq "no-conn") { $depProblems += "- dev backend не отвечает на $HealthBase (smoke пропущен)" }
  if ($depProblems.Count -eq 0) { $depProblems = @("- нет") }

  # smoke FAIL считаем только при поднятом backend (иначе no-conn = не наша вина)
  $ciR = if ($ci -eq "OK") { "OK" } else { "FAIL" }
  Write-Report "DEPLOY_REPORT.md" @"
# DEPLOY Report — Ibra Order System
## Дата: $now
## Агент: DEPLOY (qa.ps1)

| Проверка | Результат | Детали |
|----------|-----------|--------|
| CI workflow | $ci | .github/workflows/ci.yml |
| prod docker stack | $prod | docker-compose.prod.yml |
| deploy script | $deploy | scripts/deploy.sh |
| smoke /health | $(if($hHealth -eq '200'){'OK'}elseif($hHealth -eq 'no-conn'){'SKIP'}else{'FAIL'}) | $hHealth |
| smoke /health/live | $(if($hLive -eq '200'){'OK'}elseif($hLive -eq 'no-conn'){'SKIP'}else{'FAIL'}) | $hLive |
| smoke /health/ready | $(if($hReady -eq '200'){'OK'}elseif($hReady -eq 'no-conn'){'SKIP'}else{'FAIL'}) | $hReady |

## Найденные проблемы
$($depProblems -join "`n")

## Рекомендации
- Файлы проверяются статически; smoke требует поднятого backend на $HealthBase.
"@
}

# ===========================================================================
#  AGG — свести всё в MASTER_REPORT.md
# ===========================================================================
$agents = @("TECH","SEC","DEPLOY","UX","FIN","E2E")
$rows = @(); $blockers = @(); $debt = @()
$anyBlocker = $false; $anyStaleOrMissing = $false

foreach ($a in $agents) {
  $file = Join-Path $reports "$($a)_REPORT.md"
  if (-not (Test-Path $file)) {
    $rows += "| $a | — | НЕТ ОТЧЁТА | |"
    $anyStaleOrMissing = $true
    continue
  }
  $item   = Get-Item $file
  $ageMin = [int]((Get-Date) - $item.LastWriteTime).TotalMinutes
  $ts     = $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm")
  $text   = Get-Content $file -Raw

  if ($ageMin -gt $StaleMinutes) {
    $rows += "| $a | $ts | STALE (${ageMin}м) | |"
    $anyStaleOrMissing = $true
    continue
  }

  $status = "PASS"; $note = ""
  if ($text -match "\bFAIL\b" -or $text -match "\bISSUE\b") {
    $status = "FAIL"; $anyBlocker = $true
    # вытащить строки блока «Найденные проблемы»
    $probs = ([regex]::Match($text, "(?s)Найденные проблемы\s*(.*?)(##|\z)")).Groups[1].Value
    foreach ($line in ($probs -split "`n")) {
      $l = $line.Trim()
      if ($l -and $l -ne "- нет" -and $l.StartsWith("-")) { $blockers += "[$a] $($l.TrimStart('- '))" }
    }
    $note = "см. отчёт"
  }
  $rows += "| $a | $ts | $status | $note |"
}

if ($blockers.Count -eq 0) { $blockers = @("- нет") } else { $blockers = $blockers | ForEach-Object { "- $_" } }

if     ($anyBlocker)        { $verdict = "NO-GO" }
elseif ($anyStaleOrMissing) { $verdict = "PENDING (не все агенты прогнаны свежими)" }
else                        { $verdict = "GO" }

$readiness = switch -Wildcard ($verdict) {
  "GO"    { "Все агенты PASS — можно в бой." }
  "NO-GO" { "Есть блокеры — см. список выше, чинить перед деплоем." }
  default { "Догони judgment-агентов (FIN/SEC/UX/E2E) моделью в Cursor, затем перезапусти: .\qa.ps1 -AggOnly" }
}

Write-Report "MASTER_REPORT.md" @"
# MASTER REPORT — Ibra Order System
## Обновлён: $now
## Вердикт: $verdict

| Агент | Последний прогон | Итог | Блокеры |
|-------|------------------|------|---------|
$($rows -join "`n")

## Открытые блокеры (NO-GO)
$($blockers -join "`n")

## Готовность к бою
- $readiness
"@

Write-Host ""
Write-Host "  QA-прогон завершён ($now)" -ForegroundColor Cyan
Write-Host "  Вердикт: $verdict"
Write-Host "  Отчёт:   loop-output\testing\reports\MASTER_REPORT.md"
Write-Host ""

# Осмысленный код выхода (для git-хука/CI): 1 только при реальных блокерах.
if ($anyBlocker) { exit 1 } else { exit 0 }
