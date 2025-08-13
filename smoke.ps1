param(
  [string]$BaseUrl = "http://localhost:8000"
)

# ---------- helpers visuels ----------
function Show-Ok   ($m){ Write-Host ("[OK]   {0}" -f $m) -ForegroundColor Green }
function Show-Warn ($m){ Write-Host ("[WARN] {0}" -f $m) -ForegroundColor Yellow }
function Show-Fail ($m){ Write-Host ("[FAIL] {0}" -f $m) -ForegroundColor Red }
function Show-Skip ($m){ Write-Host ("[SKIP] {0}" -f $m) -ForegroundColor Cyan }

$ErrorActionPreference = "Stop"

# Accumulateurs (scope script)
$script:oks   = @()
$script:warns = @()
$script:fails = @()
$script:skips = @()

function Add-Ok   ($name)      { $script:oks   += $name;                 Show-Ok   $name }
function Add-Warn ($name,$why) { $script:warns += ("{0}: {1}" -f $name,$why); Show-Warn ("{0} -> {1}" -f $name,$why) }
function Add-Fail ($name,$why) { $script:fails += ("{0}: {1}" -f $name,$why); Show-Fail ("{0} -> {1}" -f $name,$why) }
function Add-Skip ($name,$why) { $script:skips += ("{0}: {1}" -f $name,$why); Show-Skip ("{0} -> {1}" -f $name,$why) }

function UrlPathEncode([string]$s){ [System.Uri]::EscapeDataString($s) }

# try/catch générique (404 => SKIP)
function Try-Step([string]$name, [scriptblock]$action){
  try {
    & $action
    Add-Ok $name
  } catch {
    $ex = $_.Exception
    $status = $null
    try { $status = $ex.Response.StatusCode.value__ } catch {}
    if ($status -eq 404 -or $ex.Message -match '404.*Not Found') {
      Add-Skip $name "Not Found (404)"
    } elseif ($status -eq 405 -or $ex.Message -match '405.*Method Not Allowed') {
      Add-Skip $name "Method Not Allowed (405)"
    } elseif ($status -eq 422 -or $ex.Message -match '422') {
      Add-Warn $name "Validation error (422) — peut nécessiter un body spécifique"
    } else {
      Add-Fail $name $ex.Message
    }
  }
}

# ---------- OpenAPI (auto-discovery) ----------
$script:openapi = $null
try {
  $script:openapi = Invoke-RestMethod "$BaseUrl/openapi.json"
} catch {
  Add-Warn "OpenAPI" "impossible de récupérer /openapi.json : $($_.Exception.Message)"
}

function Has-Endpoint([string]$method, [string]$path){
  if (-not $script:openapi) { return $true } # si on ne peut pas lire l'OpenAPI, on ne bloque pas
  $p = $script:openapi.paths.PSObject.Properties | Where-Object { $_.Name -eq $path }
  if (-not $p) { return $false }
  return ($p.Value.PSObject.Properties.Name -contains $method.ToLower())
}

# petit registre de ce qu’on couvre manuellement, pour ne pas le retester en auto
$script:covered = @{}

function Mark-Covered($method,$path){
  $key = ("{0} {1}" -f $method.ToUpper(), $path)
  $script:covered[$key] = $true
}
function Is-Covered($method,$path){
  $key = ("{0} {1}" -f $method.ToUpper(), $path)
  return $script:covered.ContainsKey($key)
}

# ---------- Pickers robustes ----------
function Pick-Domain {
  param([Object[]]$items)
  if ($items){
    $c = $items | ForEach-Object {
      $d = $null
      if ($_.domain)        { $d = $_.domain }
      elseif ($_.site_domain){ $d = $_.site_domain }
      elseif ($_.source_domain){ $d = $_.source_domain }
      elseif ($_.source -and $_.source.domain){ $d = $_.source.domain }
      if ($d -and ($d -match '^[a-z0-9\.\-]+$')) { $d }
    }
    $c = $c | Select-Object -Unique
    if ($c){ return $c[0] }
  }
  return $null
}

function Pick-TopicId {
  param([Object[]]$items)
  if ($items){
    foreach ($it in $items){
      $cand = $null
      if ($it.PSObject.Properties.Name -contains 'id')        { $cand = $it.id }
      elseif ($it.PSObject.Properties.Name -contains 'topic_id'){ $cand = $it.topic_id }
      elseif ($it.PSObject.Properties.Name -contains 'topicId'){ $cand = $it.topicId }
      if ($cand -and ($cand -as [int] -ne $null)){ return [int]$cand }
    }
  }
  return $null
}

# ---------- 1) /health ----------
if (Has-Endpoint 'get' '/health') {
  Mark-Covered 'GET' '/health'
  Try-Step "/health" {
    $health = Invoke-RestMethod "$BaseUrl/health"
    if (-not $health.status) { throw "missing 'status' field" }
  }
} else { Add-Skip "/health" "Not in OpenAPI" }

# ---------- 2) /api/v1/articles ----------
$script:arts = $null
if (Has-Endpoint 'get' '/api/v1/articles') {
  Mark-Covered 'GET' '/api/v1/articles'
  Try-Step "/api/v1/articles" {
    $resp = Invoke-RestMethod "$BaseUrl/api/v1/articles?limit=5"
    $script:arts = if ($resp.items) { $resp.items } else { $resp }
    if (-not $script:arts) { Add-Warn "/api/v1/articles" "no items returned" }
    else { $script:arts | Select-Object id,title,domain,site_domain,source_domain,published_at | Format-Table -AutoSize }
  }
} else { Add-Skip "/api/v1/articles" "Not in OpenAPI" }

# ---------- 3) /api/v1/topics ----------
$script:topics = $null
if (Has-Endpoint 'get' '/api/v1/topics') {
  Mark-Covered 'GET' '/api/v1/topics'
  Try-Step "/api/v1/topics" {
    $resp = Invoke-RestMethod "$BaseUrl/api/v1/topics"
    $script:topics = if ($resp.items) { $resp.items } else { $resp }
    if (-not ($script:topics -is [System.Collections.IEnumerable])) { throw "expected a list" }
  }
} else { Add-Skip "/api/v1/topics" "Not in OpenAPI" }

# ---------- 4) /api/v1/search/semantic ----------
if (Has-Endpoint 'get' '/api/v1/search/semantic') {
  Mark-Covered 'GET' '/api/v1/search/semantic'
  Try-Step "/api/v1/search/semantic" {
    $null = Invoke-RestMethod "$BaseUrl/api/v1/search/semantic?q=demo&k=5"
  }
} else { Add-Skip "/api/v1/search/semantic" "Not in OpenAPI" }

# ---------- 5) /api/v1/sentiment/source/{domain} ----------
if (Has-Endpoint 'get' '/api/v1/sentiment/source/{domain}') {
  Mark-Covered 'GET' '/api/v1/sentiment/source/{domain}'
  Try-Step "/api/v1/sentiment/source/{domain}" {
    $domain = Pick-Domain -items $script:arts
    if (-not $domain) {
      $resp = Invoke-RestMethod "$BaseUrl/api/v1/articles?limit=50"
      $items = if ($resp.items){ $resp.items } else { $resp }
      $domain = Pick-Domain -items $items
    }
    if (-not $domain) { Add-Warn "/api/v1/sentiment/source" "No domain found in articles"; return }
    $enc = UrlPathEncode $domain
    $null = Invoke-RestMethod "$BaseUrl/api/v1/sentiment/source/$enc?days=7"
  }
} else { Add-Skip "/api/v1/sentiment/source/{domain}" "Not in OpenAPI" }

# ---------- 6) /api/v1/sentiment/topic/{topic_id} ----------
if (Has-Endpoint 'get' '/api/v1/sentiment/topic/{topic_id}') {
  Mark-Covered 'GET' '/api/v1/sentiment/topic/{topic_id}'
  Try-Step "/api/v1/sentiment/topic/{topic_id}" {
    $tid = Pick-TopicId -items $script:topics
    if (-not $tid) { Add-Warn "/api/v1/sentiment/topic" "No topic id available"; return }
    $null = Invoke-RestMethod "$BaseUrl/api/v1/sentiment/topic/$tid?days=7"
  }
} else { Add-Skip "/api/v1/sentiment/topic/{topic_id}" "Not in OpenAPI" }

# ---------- 7) /api/v1/relations/sources ----------
if (Has-Endpoint 'get' '/api/v1/relations/sources') {
  Mark-Covered 'GET' '/api/v1/relations/sources'
  Try-Step "/api/v1/relations/sources" {
    $today = (Get-Date).ToString('yyyy-MM-dd')
    $null = Invoke-RestMethod "$BaseUrl/api/v1/relations/sources?date=$today&relation=co_coverage&min_weight=1&limit=10"
  }
}

# ---------- 8) /api/v1/graph/cluster/1 ----------
if (Has-Endpoint 'get' '/api/v1/graph/cluster/{cluster_id}') {
  # certains schémas exposent {cluster_id} dans OpenAPI
  Mark-Covered 'GET' '/api/v1/graph/cluster/{cluster_id}'
  Try-Step "/api/v1/graph/cluster/1" {
    $graph = Invoke-RestMethod "$BaseUrl/api/v1/graph/cluster/1"
    if (-not ($graph.nodes -and $graph.edges)) {
      Add-Warn "/api/v1/graph/cluster/1" "shape not standard (nodes/edges missing)"
    }
  }
} elseif (Has-Endpoint 'get' '/api/v1/graph/cluster/1') {
  Mark-Covered 'GET' '/api/v1/graph/cluster/1'
  Try-Step "/api/v1/graph/cluster/1" {
    $graph = Invoke-RestMethod "$BaseUrl/api/v1/graph/cluster/1"
    if (-not ($graph.nodes -and $graph.edges)) {
      Add-Warn "/api/v1/graph/cluster/1" "shape not standard (nodes/edges missing)"
    }
  }
}

# ---------- 9) /api/v1/sources ----------
if (Has-Endpoint 'get' '/api/v1/sources') {
  Mark-Covered 'GET' '/api/v1/sources'
  Try-Step "/api/v1/sources" {
    $sources = Invoke-RestMethod "$BaseUrl/api/v1/sources"
    $items = if ($sources.items){ $sources.items } else { $sources }
    if ($items){ $items | Select-Object name,feed_url,site_domain,method,enrichment,frequency_minutes,active,id | Select-Object -First 10 | Format-Table -AutoSize }
    else { Add-Warn "/api/v1/sources" "no sources returned" }
  }
}

# ---------- 10) POST /api/v1/sources/refresh ----------
if (Has-Endpoint 'post' '/api/v1/sources/refresh') {
  Mark-Covered 'POST' '/api/v1/sources/refresh'
  Try-Step "POST /api/v1/sources/refresh" {
    $resp = Invoke-RestMethod "$BaseUrl/api/v1/sources/refresh" -Method Post
    if (-not $resp) { Add-Warn "POST /api/v1/sources/refresh" "empty response" }
  }
}

# ---------- 11) /api/v1/synthesis (GET ou POST) ----------
if (Has-Endpoint 'post' '/api/v1/synthesis' -or Has-Endpoint 'get' '/api/v1/synthesis') {
  # ne le marque qu'une fois
  Mark-Covered 'GET' '/api/v1/synthesis'
  Mark-Covered 'POST' '/api/v1/synthesis'
  Try-Step "/api/v1/synthesis" {
    $arts2 = $script:arts
    if (-not $arts2 -or $arts2.Count -lt 1){
      $resp = Invoke-RestMethod "$BaseUrl/api/v1/articles?limit=2"
      $arts2 = if ($resp.items){ $resp.items } else { $resp }
    }
    if (-not $arts2 -or $arts2.Count -lt 1) { Add-Warn "/api/v1/synthesis" "No articles found for synthesis"; return }
    $ids = @($arts2 | Select-Object -ExpandProperty id)
    $syn = $null
    if (Has-Endpoint 'post' '/api/v1/synthesis') {
      try {
        $body = @{ article_ids = $ids } | ConvertTo-Json
        $syn = Invoke-RestMethod "$BaseUrl/api/v1/synthesis" -Method Post -ContentType "application/json" -Body $body
      } catch {
        # on tentera GET si dispo
      }
    }
    if (-not $syn -and (Has-Endpoint 'get' '/api/v1/synthesis')) {
      $idsCsv = ($ids -join ",")
      $syn = Invoke-RestMethod "$BaseUrl/api/v1/synthesis?article_ids=$idsCsv"
    }
    if (-not $syn) { throw "synthesis endpoint present but no response" }
    if (-not ($syn.summary -or $syn.text -or $syn.items)) { Add-Warn "/api/v1/synthesis" "unusual payload" }
  }
}

# =============== AUTO-DISCOVERY pour le reste ===============
if ($script:openapi) {
  foreach ($p in $script:openapi.paths.PSObject.Properties) {
    $path = $p.Name
    if ($path -notmatch '^/api/v\d+/') { continue }  # garder l'API publique v1/v2...
    $ops = $p.Value.PSObject.Properties | Where-Object { $_.Name -in @('get','post') }
    foreach ($op in $ops) {
      $method = $op.Name.ToUpper()
      if (Is-Covered $method $path) { continue }  # déjà testé
      $label = ("{0} {1}" -f $method, $path)
      Try-Step $label {
        # Construire l'URL avec path/query params
        $pathParams = @()
        $queryParams = @()

        # paramètres au niveau path + opération
        $allParams = @()
        if ($p.Value.parameters) { $allParams += @($p.Value.parameters) }
        if ($op.Value.parameters) { $allParams += @($op.Value.parameters) }

        # helper: valeur d'exemple
        function Sample-ForParam([string]$name, $schema, [string]$location){
          $typ = $null
          if ($schema -and $schema.type) { $typ = $schema.type.ToString().ToLower() }
          switch -Regex ($name) {
            '^domain$'        { return 'www.bbc.com' }
            'topic_?id$'      { 
              $tid = Pick-TopicId -items $script:topics
              if ($tid) { return $tid }
              return 1
            }
            '^id$'            { return 1 }
            '^limit$'         { return 5 }
            '^(k|topk)$'      { return 5 }
            '^days$'          { return 7 }
            '^min_weight$'    { return 1 }
            '^relation$'      { return 'co_coverage' }
            '^date$'          { return (Get-Date).ToString('yyyy-MM-dd') }
            '^q$'             { return 'demo' }
            default {
              if ($typ -eq 'integer' -or $typ -eq 'number') { return 1 }
              elseif ($typ -eq 'boolean') { return $true }
              elseif ($location -eq 'path') { return '1' }
              else { return 'demo' }
            }
          }
        }

        $urlPath = $path
        $matches = [regex]::Matches($path, '\{([^}]+)\}')
        foreach ($m in $matches) {
          $n = $m.Groups[1].Value
          $schema = ($allParams | Where-Object { $_.name -eq $n -and $_.in -eq 'path' } | Select-Object -First 1).schema
          $val = Sample-ForParam $n $schema 'path'
          $urlPath = $urlPath -replace [regex]::Escape($m.Value), [System.Uri]::EscapeDataString("$val")
        }

        # query params requis -> valeurs d'exemple
        foreach ($pr in $allParams | Where-Object { $_.in -eq 'query' }) {
          $name = $pr.name
          # si required=true ou pas de default, on met une valeur
          if ($pr.required -or -not $pr.schema.default) {
            $qv = Sample-ForParam $name $pr.schema 'query'
            $queryParams += ("{0}={1}" -f [System.Uri]::EscapeDataString($name), [System.Uri]::EscapeDataString("$qv"))
          }
        }
        $url = "$BaseUrl$urlPath"
        if ($queryParams.Count) { $url = "$url?$(($queryParams -join '&'))" }

        if ($method -eq 'GET') {
          $null = Invoke-RestMethod $url -Method Get
        } elseif ($method -eq 'POST') {
          # si requestBody requis et inconnu -> tenter {} sinon WARN 422
          $hasBody = $false
          try {
            if ($op.Value.requestBody) {
              $hasBody = $true
              $ct = $op.Value.requestBody.content.PSObject.Properties.Name | Select-Object -First 1
              if (-not $ct) { $ct = 'application/json' }
              $null = Invoke-RestMethod $url -Method Post -ContentType $ct -Body '{}'
            } else {
              $null = Invoke-RestMethod $url -Method Post
            }
          } catch {
            throw $_  # géré par Try-Step (SKIP 405 / WARN 422 / FAIL autres)
          }
        }
      }
    }
  }
}

# ---------- summary ----------
"`n==== SUMMARY ===="
"OK   : {0}"   -f $script:oks.Count
"WARN : {0}"   -f $script:warns.Count
"SKIP : {0}"   -f $script:skips.Count
"FAIL : {0}"   -f $script:fails.Count

if ($script:warns.Count) {
  "`nWarnings:"
  $script:warns | ForEach-Object { " - $_" }
}
if ($script:skips.Count) {
  "`nSkipped:"
  $script:skips | ForEach-Object { " - $_" }
}
if ($script:fails.Count) {
  "`nFailures:"
  $script:fails | ForEach-Object { " - $_" }
  exit 1
} else {
  "`nAll endpoint smoke tests finished."
  exit 0
}
