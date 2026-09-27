<#
update.ps1 — 一鍵更新所有路線的時刻表資料

用法：
    .\update.cmd                          # 更新所有已啟用路線
    .\update.cmd -Only tra hsr             # 只更新指定路線（用 -ListRoutes 查代號）
    .\update.cmd -ListRoutes               # 列出所有路線代號
    .\update.cmd -IncludeTopology          # 連同拓樸（車站/里程）一起重新爬取（平常不需要）
    .\update.cmd -NoLog                    # 不寫入 log 檔，只輸出到終端機

各路線爬蟲的日期區間預設值可用環境變數覆寫（PowerShell 範例）：
    $env:TRA_FORECAST_DAYS = "30"; .\update.cmd -Only tra

JR西日本 (JR_West) 沒有自動爬蟲（原始資料 data_new.json 需手動取得），本腳本不處理，
會在執行時提醒。

執行過程與結果預設會完整寫入 logs/update_YYYYMMDD_HHMMSS.log（終端機捲軸洗掉的內容都能回去查）。
只記錄各 Python 腳本的標準輸出（本專案所有腳本的關鍵訊息、統計、警告都是用 print 寫到標準輸出）；
tqdm 進度條等寫到標準錯誤的內容只會顯示在畫面上，不會進 log，避免 PowerShell 5.1 合併
標準錯誤時產生的雜訊（NativeCommandError 包裝）。
#>

param(
    [string[]]$Only,
    [switch]$IncludeTopology,
    [switch]$ListRoutes,
    [switch]$NoLog
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# 本專案所有 Python 腳本都以 UTF-8 寫 stdout，統一設定主控台編碼以求保險
# （實測發現真正的亂碼元凶是 Tee-Object 預設寫 UTF-16LE，見下方 Invoke-Logged）。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$LogFile = $null
if (-not $NoLog) {
    $LogDir = Join-Path $RepoRoot "logs"
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    $LogFile = Join-Path $LogDir ("update_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    New-Item -ItemType File -Path $LogFile -Force | Out-Null
}

function Log {
    param([string]$Message = "", [string]$Color)
    if ($Color) { Write-Host $Message -ForegroundColor $Color } else { Write-Host $Message }
    if ($LogFile) { Add-Content -Path $LogFile -Value $Message -Encoding UTF8 }
}

function Invoke-Logged {
    param([string]$ScriptPath, [string[]]$StepArgs = @())
    # 不用 Tee-Object：Windows PowerShell 5.1 的 Tee-Object 沒有 -Encoding 參數，預設寫
    # UTF-16LE，混進本檔案其餘用 UTF-8 寫的內容裡會整份亂碼。改成逐行手動寫，編碼跟 Log() 一致。
    if ($LogFile) {
        py $ScriptPath @StepArgs | ForEach-Object {
            Write-Host $_
            Add-Content -Path $LogFile -Value $_ -Encoding UTF8
        }
    } else {
        py $ScriptPath @StepArgs | Out-Host
    }
    return $LASTEXITCODE
}

$routes = @(
    @{ Key = "tra";      Name = "台鐵 TRA";
       Steps = @("data/Taiwan/TRA/script/timetable.py", "data/Taiwan/TRA/script/available_date.py", "tools/validate_system.py data/Taiwan/TRA") }
    @{ Key = "hsr";      Name = "高鐵 HSR";
       Steps = @("data/Taiwan/HSR/script/fetch_and_transform_hsr.py", "tools/validate_system.py data/Taiwan/HSR") }
    @{ Key = "tokaido-shinkansen"; Name = "東海道・山陽・九州・西九州新幹線";
       Topology = "data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/build_topology.py"
       Steps = @("data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/timetable.py --days 7", "data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/convert_timetable.py", "tools/validate_system.py data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen --timetable-sample 0") }
    @{ Key = "tohoku-shinkansen"; Name = "東北・北海道・上越・北陸新幹線";
       Steps = @("data/Japan/Tohoku_Hokkaido_Joetsu_Hokuriku_Shinkansen/script/timetable.py", "tools/validate_system.py data/Japan/Tohoku_Hokkaido_Joetsu_Hokuriku_Shinkansen --timetable-sample 0") }
    @{ Key = "jreast";   Name = "JR東日本 (JR East)";
       Topology = "data/Japan/JR_East/script/build_topology.py"
       Steps = @("data/Japan/JR_East/script/timetable.py", "data/Japan/JR_East/script/convert_timetable.py", "data/Japan/JR_East/script/build_setting.py", "tools/validate_system.py data/Japan/JR_East --timetable-sample 0") }
    @{ Key = "hankyu";   Name = "阪急電鐵";
       Topology = "data/Japan/Hankyu/script/build_topology.py"
       Steps = @("data/Japan/Hankyu/script/timetable.py", "data/Japan/Hankyu/script/convert_timetable.py", "tools/validate_system.py data/Japan/Hankyu --timetable-sample 0") }
    @{ Key = "hanshin";  Name = "阪神電氣鐵道";
       Topology = "data/Japan/Hanshin/script/build_topology.py"
       Steps = @("data/Japan/Hanshin/script/timetable.py", "data/Japan/Hanshin/script/convert_timetable.py", "tools/validate_system.py data/Japan/Hanshin --timetable-sample 0") }
    @{ Key = "keihan";   Name = "京阪電氣鐵道";
       Topology = "data/Japan/Keihan/script/build_topology.py"
       Steps = @("data/Japan/Keihan/script/timetable.py", "data/Japan/Keihan/script/convert_timetable.py", "tools/validate_system.py data/Japan/Keihan --timetable-sample 0") }
    @{ Key = "kintetsu"; Name = "近畿日本鐵道";
       Steps = @("data/Japan/Kintetsu/script/timetable.py", "tools/validate_system.py data/Japan/Kintetsu --timetable-sample 0") }
    @{ Key = "nankai";   Name = "南海電鐵";
       Steps = @("data/Japan/Nankai/script/timetable.py", "tools/validate_system.py data/Japan/Nankai --timetable-sample 0") }
    @{ Key = "eizan";    Name = "叡山電鐵";
       Topology = "data/Japan/Eizan/script/build_topology.py"
       Steps = @("data/Japan/Eizan/script/timetable.py", "data/Japan/Eizan/script/convert_timetable.py", "tools/validate_system.py data/Japan/Eizan --timetable-sample 0") }
    @{ Key = "keifuku";  Name = "京福電氣鐵道";
       Topology = "data/Japan/Keifuku/script/build_topology.py"
       Steps = @("data/Japan/Keifuku/script/timetable.py", "data/Japan/Keifuku/script/convert_timetable.py", "tools/validate_system.py data/Japan/Keifuku --timetable-sample 0") }
    @{ Key = "sagano";   Name = "嵯峨野觀光鐵道";
       Topology = "data/Japan/Sagano/script/build_topology.py"
       Steps = @("data/Japan/Sagano/script/timetable.py", "data/Japan/Sagano/script/convert_timetable.py", "data/Japan/Sagano/script/available_date.py", "tools/validate_system.py data/Japan/Sagano --timetable-sample 0") }
    @{ Key = "tango";    Name = "京都丹後鐵道";
       Topology = "data/Japan/Tango/script/build_topology.py"
       Steps = @("data/Japan/Tango/script/timetable.py", "data/Japan/Tango/script/convert_timetable.py", "tools/validate_system.py data/Japan/Tango --timetable-sample 0") }
    @{ Key = "chizu";    Name = "智頭急行";
       Topology = "data/Japan/Chizu_Express/script/build_topology.py"
       Steps = @("data/Japan/Chizu_Express/script/timetable.py", "data/Japan/Chizu_Express/script/convert_timetable.py", "tools/validate_system.py data/Japan/Chizu_Express --timetable-sample 0") }
    @{ Key = "sanyo";    Name = "山陽電氣鐵道";
       Topology = "data/Japan/Sanyo/script/build_topology.py"
       Steps = @("data/Japan/Sanyo/script/timetable.py", "data/Japan/Sanyo/script/convert_timetable.py", "tools/validate_system.py data/Japan/Sanyo --timetable-sample 0") }
)

if ($ListRoutes) {
    foreach ($r in $routes) { Log ("{0,-20} {1}" -f $r.Key, $r.Name) }
    exit 0
}

$selected = if ($Only -and $Only.Count -gt 0) {
    $routes | Where-Object { $Only -contains $_.Key }
} else {
    $routes
}

if (-not $selected -or $selected.Count -eq 0) {
    Log "找不到符合的路線代號，可用 -ListRoutes 查看清單。" "Red"
    exit 2
}

Log "============================================"
Log " TRA_Visualization 時刻表全路線更新"
Log " 共 $($selected.Count) 條路線"
Log "============================================"
Log ""

$dow = (Get-Date).DayOfWeek
if ($dow -eq [DayOfWeek]::Monday -or $dow -eq [DayOfWeek]::Tuesday) {
    Log "[警告] 今天是 $dow，navitime 系日本私鐵（阪急/阪神/京阪/叡山/京福/嵯峨野/丹後/智頭急行/山陽）的自然日期池可能抓不到假日班次，建議週三～週日執行。" "Yellow"
    Log ""
}

if (-not $Only -or $Only -contains "jrwest") {
    Log "[提醒] JR西日本 (JR_West) 沒有自動爬蟲，原始資料 json/data_new.json 需手動取得後再執行 convert_jrwest.py，本腳本不會處理。" "Yellow"
    Log ""
}

$results = @()

foreach ($route in $selected) {
    Log ">>> $($route.Name) [$($route.Key)]" "Cyan"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $ok = $true
    $validateWarn = $false

    if ($IncludeTopology -and $route.Topology) {
        Log "    py $($route.Topology)"
        $code = Invoke-Logged -ScriptPath $route.Topology
        if ($code -ne 0) {
            $ok = $false
            Log "    [失敗] build_topology.py 結束碼 $code" "Red"
        }
    }

    foreach ($step in $route.Steps) {
        if (-not $ok) { break }
        $parts = $step -split ' '
        $script = $parts[0]
        $stepArgs = @()
        if ($parts.Length -gt 1) { $stepArgs = $parts[1..($parts.Length - 1)] }
        Log "    py $step"
        $code = Invoke-Logged -ScriptPath $script -StepArgs $stepArgs
        if ($code -ne 0) {
            if ($script -match "validate_system") {
                $validateWarn = $true
                Log "    [警告] 資料驗證回報 ERROR，結束碼 $code（時刻表可能已更新，請檢查上方輸出）" "Yellow"
            } else {
                $ok = $false
                Log "    [失敗] $script 結束碼 $code" "Red"
            }
        }
    }

    $sw.Stop()
    $status = if (-not $ok) { "FAILED" } elseif ($validateWarn) { "VALIDATE WARN" } else { "OK" }
    $results += [PSCustomObject]@{ Route = $route.Name; Key = $route.Key; Status = $status; Seconds = [int]$sw.Elapsed.TotalSeconds }
    Log "    -> $status（$([int]$sw.Elapsed.TotalSeconds) 秒）"
    Log ""
}

Log "============================================"
Log " 執行結果總覽"
Log "============================================"
Log ($results | Format-Table -AutoSize | Out-String)

if ($LogFile) {
    Log "完整記錄已存至：$LogFile"
    Log ""
}

$failed = $results | Where-Object { $_.Status -eq "FAILED" }
if ($failed) {
    Log "有 $($failed.Count) 條路線更新失敗，請檢查上方訊息。" "Red"
    exit 1
} else {
    Log "全部完成！" "Green"
    exit 0
}
