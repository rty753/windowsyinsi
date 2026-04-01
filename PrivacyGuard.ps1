#Requires -RunAsAdministrator
# Windows 隐私卫士 - Privacy Guard
# 双击运行即可，无需安装任何依赖

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ══════════════════════════════════════════════════════════════════════
#  日志
# ══════════════════════════════════════════════════════════════════════
$script:LogDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $script:LogDir)) { New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null }
$script:LogFile = Join-Path $script:LogDir ("privacy_guard_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-Log {
    param([string]$Message)
    $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $script:LogFile -Value $line -Encoding UTF8
    if ($script:LogBox) {
        $script:LogBox.Invoke([Action]{
            $script:LogBox.AppendText("$line`r`n")
            $script:LogBox.ScrollToCaret()
        })
    }
}

# ══════════════════════════════════════════════════════════════════════
#  检测函数
# ══════════════════════════════════════════════════════════════════════
function Get-AllStatus {
    $items = [System.Collections.ArrayList]::new()

    # ── 1. 摄像头 ──
    $cam = [PSCustomObject]@{ Name="摄像头"; Key="camera"; Icon="CAM"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $devs = Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue
        if (-not $devs) { $devs = Get-PnpDevice -Class Image -ErrorAction SilentlyContinue }
        if ($devs) {
            $ok = @($devs | Where-Object { $_.Status -eq 'OK' })
            if ($ok.Count -gt 0) {
                $cam.Enabled = $true; $cam.Status = "warning"
                $cam.Desc = "摄像头已启用 ($($ok.Count) 个)"
                # 检查占用
                $using = Get-DeviceUsage "webcam"
                if ($using.Count -gt 0) {
                    $cam.Status = "active"
                    $cam.Desc = "摄像头正被使用: " + (($using | Select-Object -First 3) -join ", ")
                }
                $cam.Details = @($ok | ForEach-Object { "[已启用] $($_.FriendlyName)" })
            } else {
                $cam.Desc = "摄像头已禁用"
                $cam.Details = @($devs | ForEach-Object { "[已禁用] $($_.FriendlyName)" })
            }
        } else { $cam.Desc = "未检测到摄像头" }
    } catch { $cam.Desc = "检测出错"; $cam.Status = "warning" }
    [void]$items.Add($cam)

    # ── 2. 麦克风 ──
    $mic = [PSCustomObject]@{ Name="麦克风"; Key="microphone"; Icon="MIC"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $devs = Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue |
            Where-Object { $_.FriendlyName -match 'Mic|麦克风' }
        if (-not $devs) {
            $devs = Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue
        }
        if ($devs) {
            $ok = @($devs | Where-Object { $_.Status -eq 'OK' })
            if ($ok.Count -gt 0) {
                $mic.Enabled = $true; $mic.Status = "warning"
                $mic.Desc = "麦克风已启用 ($($ok.Count) 个)"
                $using = Get-DeviceUsage "microphone"
                if ($using.Count -gt 0) {
                    $mic.Status = "active"
                    $mic.Desc = "麦克风正被使用: " + (($using | Select-Object -First 3) -join ", ")
                }
                $mic.Details = @($ok | ForEach-Object { "[已启用] $($_.FriendlyName)" })
            } else {
                $mic.Desc = "麦克风已禁用"
                $mic.Details = @($devs | ForEach-Object { "[已禁用] $($_.FriendlyName)" })
            }
        } else { $mic.Desc = "未检测到麦克风" }
    } catch { $mic.Desc = "检测出错"; $mic.Status = "warning" }
    [void]$items.Add($mic)

    # ── 3. 定位服务 ──
    $loc = [PSCustomObject]@{ Name="定位服务"; Key="location"; Icon="LOC"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $svc = Get-Service lfsvc -ErrorAction SilentlyContinue
        $regVal = "Deny"
        try { $regVal = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -ErrorAction SilentlyContinue).Value } catch {}
        if ($regVal -eq "Allow" -or ($svc -and $svc.Status -eq 'Running')) {
            $loc.Enabled = $true; $loc.Status = "warning"
            $loc.Desc = "定位服务已开启"
        } else {
            $loc.Desc = "定位服务已关闭"
        }
        $loc.Details = @("权限: $regVal", "lfsvc: $(if($svc){$svc.Status}else{'未找到'})")
    } catch { $loc.Desc = "检测出错" }
    [void]$items.Add($loc)

    # ── 4. 蓝牙 ──
    $bt = [PSCustomObject]@{ Name="蓝牙"; Key="bluetooth"; Icon="BT"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $devs = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue
        if ($devs) {
            $ok = @($devs | Where-Object { $_.Status -eq 'OK' })
            if ($ok.Count -gt 0) {
                $bt.Enabled = $true; $bt.Status = "warning"
                $bt.Desc = "蓝牙已开启 ($($ok.Count) 个设备)"
                $bt.Details = @($ok | ForEach-Object { "[已启用] $($_.FriendlyName)" })
            } else { $bt.Desc = "蓝牙已禁用" }
        } else { $bt.Desc = "未检测到蓝牙" }
    } catch { $bt.Desc = "检测出错" }
    [void]$items.Add($bt)

    # ── 5. WiFi ──
    $wifi = [PSCustomObject]@{ Name="WiFi"; Key="wifi"; Icon="NET"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $iface = netsh interface show interface 2>$null | Where-Object { $_ -match 'Wi-Fi|WiFi|Wireless|WLAN' }
        if ($iface) {
            if ($iface -match 'Connected|已连接') {
                $wifi.Enabled = $true; $wifi.Status = "active"
                $ssidLine = netsh wlan show interfaces 2>$null | Where-Object { $_ -match '^\s+SSID\s+:' -and $_ -notmatch 'BSSID' }
                $ssid = if ($ssidLine) { ($ssidLine -split ':\s*',2)[1].Trim() } else { "未知" }
                $wifi.Desc = "WiFi 已连接: $ssid"
                $wifi.Details = @("SSID: $ssid")
            } elseif ($iface -match 'Disconnected|已断开') {
                $wifi.Enabled = $true; $wifi.Status = "warning"
                $wifi.Desc = "WiFi 已开启, 未连接"
            } else {
                $wifi.Desc = "WiFi 已禁用"
            }
        } else { $wifi.Desc = "未检测到 WiFi 适配器" }
    } catch { $wifi.Desc = "检测出错" }
    [void]$items.Add($wifi)

    # ── 6. USB 摄像头 ──
    $usb = [PSCustomObject]@{ Name="USB摄像头"; Key="usb_camera"; Icon="USB"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $devs = Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB*' }
        if (-not $devs) { $devs = Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB*' } }
        if ($devs) {
            $ok = @($devs | Where-Object { $_.Status -eq 'OK' })
            if ($ok.Count -gt 0) {
                $usb.Enabled = $true; $usb.Status = "warning"
                $usb.Desc = "$($ok.Count) 个 USB 摄像头已启用"
            } else { $usb.Desc = "USB 摄像头已禁用" }
        } else { $usb.Desc = "未检测到 USB 摄像头" }
    } catch { $usb.Desc = "检测出错" }
    [void]$items.Add($usb)

    # ── 7. 传感器服务 ──
    $sensor = [PSCustomObject]@{ Name="传感器服务"; Key="sensor"; Icon="SNS"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $running = $false
        foreach ($sn in @("SensorService","SensorDataService","SensrSvc")) {
            $s = Get-Service $sn -ErrorAction SilentlyContinue
            if ($s -and $s.Status -eq 'Running') { $running = $true; $sensor.Details += "$sn : Running" }
            else { $sensor.Details += "$sn : Stopped" }
        }
        if ($running) { $sensor.Enabled = $true; $sensor.Status = "warning"; $sensor.Desc = "传感器服务运行中" }
        else { $sensor.Desc = "传感器服务已停止" }
    } catch { $sensor.Desc = "检测出错" }
    [void]$items.Add($sensor)

    # ── 8. 远程桌面 ──
    $rdp = [PSCustomObject]@{ Name="远程桌面(RDP)"; Key="rdp"; Icon="RDP"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $deny = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections
        if ($deny -eq 0) {
            $rdp.Enabled = $true; $rdp.Status = "active"
            $rdp.Desc = "远程桌面已启用 (可被远程连接!)"
        } else { $rdp.Desc = "远程桌面已禁用" }
    } catch { $rdp.Desc = "检测出错" }
    [void]$items.Add($rdp)

    # ── 9. 诊断数据 ──
    $tel = [PSCustomObject]@{ Name="诊断数据"; Key="telemetry"; Icon="TEL"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $level = $null
        try { $level = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name AllowTelemetry -ErrorAction SilentlyContinue).AllowTelemetry } catch {}
        if ($null -eq $level) {
            try { $level = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection" -Name AllowTelemetry -ErrorAction SilentlyContinue).AllowTelemetry } catch {}
        }
        if ($null -eq $level) { $level = 3 }
        $labels = @{ 0="Security(最低)"; 1="Basic(基本)"; 2="Enhanced(增强)"; 3="Full(完整-最高)" }
        $lbl = $labels[[int]$level]
        if ($level -gt 0) { $tel.Enabled = $true; $tel.Status = if($level -le 1){"warning"}else{"active"} }
        $tel.Desc = "遥测级别: $lbl"
        $tel.Details = @("AllowTelemetry = $level")
    } catch { $tel.Desc = "检测出错" }
    [void]$items.Add($tel)

    # ── 10. Cortana ──
    $cor = [PSCustomObject]@{ Name="Cortana"; Key="cortana"; Icon="COR"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $allow = $null
        try { $allow = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search" -Name AllowCortana -ErrorAction SilentlyContinue).AllowCortana } catch {}
        if ($null -eq $allow) {
            try { $allow = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name CortanaConsent -ErrorAction SilentlyContinue).CortanaConsent } catch {}
        }
        if ($null -eq $allow -or $allow -ne 0) {
            $cor.Enabled = $true; $cor.Status = "warning"; $cor.Desc = "Cortana 已启用"
        } else { $cor.Desc = "Cortana 已禁用" }
    } catch { $cor.Desc = "检测出错" }
    [void]$items.Add($cor)

    # ── 11. 广告 ID ──
    $ad = [PSCustomObject]@{ Name="广告 ID"; Key="ad_id"; Icon="AD"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $en = 1
        try { $en = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo" -Name Enabled -ErrorAction SilentlyContinue).Enabled } catch {}
        if ($en -and $en -ne 0) {
            $ad.Enabled = $true; $ad.Status = "warning"; $ad.Desc = "广告 ID 追踪已启用"
        } else { $ad.Desc = "广告 ID 追踪已禁用" }
    } catch { $ad.Desc = "检测出错" }
    [void]$items.Add($ad)

    # ── 12. 后台应用 ──
    $bg = [PSCustomObject]@{ Name="后台应用"; Key="bg_apps"; Icon="BG"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $dis = 0
        try { $dis = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name GlobalUserDisabled -ErrorAction SilentlyContinue).GlobalUserDisabled } catch {}
        if (-not $dis) {
            $bg.Enabled = $true; $bg.Status = "warning"; $bg.Desc = "后台应用运行已开启"
        } else { $bg.Desc = "后台应用运行已全局禁用" }
    } catch { $bg.Desc = "检测出错" }
    [void]$items.Add($bg)

    # ── 13. 剪贴板 ──
    $clip = [PSCustomObject]@{ Name="剪贴板历史"; Key="clipboard"; Icon="CLB"; Status="safe"; Desc=""; Enabled=$false; Details=@() }
    try {
        $hist = 0; $cloud = 0
        try { $hist = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Clipboard" -Name EnableClipboardHistory -ErrorAction SilentlyContinue).EnableClipboardHistory } catch {}
        try { $cloud = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Clipboard" -Name EnableCloudClipboard -ErrorAction SilentlyContinue).EnableCloudClipboard } catch {}
        $issues = @()
        if ($hist) { $issues += "历史已启用" }
        if ($cloud) { $issues += "云同步已启用" }
        if ($issues.Count -gt 0) {
            $clip.Enabled = $true; $clip.Status = if($cloud){"active"}else{"warning"}
            $clip.Desc = $issues -join ", "
        } else { $clip.Desc = "剪贴板历史和云同步已关闭" }
    } catch { $clip.Desc = "检测出错" }
    [void]$items.Add($clip)

    return $items
}

function Get-DeviceUsage {
    param([string]$DeviceType)
    $apps = @()
    $basePath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\$DeviceType"
    try {
        $keys = Get-ChildItem -Path $basePath -ErrorAction SilentlyContinue
        foreach ($k in $keys) {
            if ($k.PSChildName -eq "NonPackaged") {
                $sub = Get-ChildItem -Path $k.PSPath -ErrorAction SilentlyContinue
                foreach ($s in $sub) {
                    $start = try { (Get-ItemProperty $s.PSPath -Name LastUsedTimeStart -ErrorAction SilentlyContinue).LastUsedTimeStart } catch { 0 }
                    $stop  = try { (Get-ItemProperty $s.PSPath -Name LastUsedTimeStop  -ErrorAction SilentlyContinue).LastUsedTimeStop  } catch { 0 }
                    if ($start -ne 0 -and ($stop -eq 0 -or $start -gt $stop)) {
                        $name = $s.PSChildName -replace '#','\'
                        $apps += [System.IO.Path]::GetFileName($name)
                    }
                }
            } else {
                $start = try { (Get-ItemProperty $k.PSPath -Name LastUsedTimeStart -ErrorAction SilentlyContinue).LastUsedTimeStart } catch { 0 }
                $stop  = try { (Get-ItemProperty $k.PSPath -Name LastUsedTimeStop  -ErrorAction SilentlyContinue).LastUsedTimeStop  } catch { 0 }
                if ($start -ne 0 -and ($stop -eq 0 -or $start -gt $stop)) {
                    $apps += $k.PSChildName
                }
            }
        }
    } catch {}
    return $apps
}

# ══════════════════════════════════════════════════════════════════════
#  控制函数
# ══════════════════════════════════════════════════════════════════════
function Set-DeviceState {
    param([string]$Key, [bool]$Enable)
    $action = if($Enable){"启用"}else{"禁用"}
    Write-Log "操作: $action $Key"
    $ok = $true; $msg = ""
    try {
        switch ($Key) {
            "camera" {
                $devs = Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue
                $devs2 = Get-PnpDevice -Class Image -ErrorAction SilentlyContinue
                $all = @($devs) + @($devs2) | Where-Object { $_ }
                foreach ($d in $all) {
                    if ($Enable) { Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                    else { Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                }
                $msg = "摄像头已$action"
            }
            "microphone" {
                $devs = Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'Mic|麦克风' }
                foreach ($d in $devs) {
                    if ($Enable) { Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                    else { Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                }
                $msg = "麦克风已$action"
            }
            "location" {
                if ($Enable) {
                    Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -Value "Allow" -ErrorAction SilentlyContinue
                    sc.exe config lfsvc start= auto >$null 2>&1; sc.exe start lfsvc >$null 2>&1
                } else {
                    Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -Value "Deny" -ErrorAction SilentlyContinue
                    sc.exe stop lfsvc >$null 2>&1; sc.exe config lfsvc start= disabled >$null 2>&1
                }
                $msg = "定位服务已$action"
            }
            "bluetooth" {
                $devs = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue
                foreach ($d in $devs) {
                    if ($Enable) { Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                    else { Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                }
                $msg = "蓝牙已$action"
            }
            "wifi" {
                $names = @("Wi-Fi","WiFi","Wireless","WLAN")
                $done = $false
                foreach ($n in $names) {
                    $r = if($Enable){ netsh interface set interface $n enable 2>&1 } else { netsh interface set interface $n disable 2>&1 }
                    if ($LASTEXITCODE -eq 0) { $done = $true; break }
                }
                $msg = if($done){ "WiFi 已$action" } else { "WiFi ${action}失败" }
            }
            "usb_camera" {
                $devs = Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB*' }
                $devs2 = Get-PnpDevice -Class Image -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB*' }
                $all = @($devs) + @($devs2) | Where-Object { $_ }
                foreach ($d in $all) {
                    if ($Enable) { Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                    else { Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue }
                }
                $msg = "USB摄像头已$action"
            }
            "sensor" {
                foreach ($sn in @("SensorService","SensorDataService","SensrSvc")) {
                    if ($Enable) { sc.exe config $sn start= auto >$null 2>&1; sc.exe start $sn >$null 2>&1 }
                    else { sc.exe stop $sn >$null 2>&1; sc.exe config $sn start= disabled >$null 2>&1 }
                }
                $msg = "传感器服务已$action"
            }
            "rdp" {
                $val = if($Enable){0}else{1}
                Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections -Value $val
                $msg = "远程桌面已$action"
            }
            "telemetry" {
                $val = if($Enable){1}else{0}
                $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name AllowTelemetry -Value $val
                if (-not $Enable) {
                    sc.exe stop DiagTrack >$null 2>&1; sc.exe config DiagTrack start= disabled >$null 2>&1
                } else {
                    sc.exe config DiagTrack start= auto >$null 2>&1; sc.exe start DiagTrack >$null 2>&1
                }
                $msg = "诊断数据已设为$(if($Enable){'基本'}else{'最低级别'})"
            }
            "cortana" {
                $val = if($Enable){1}else{0}
                $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name AllowCortana -Value $val
                New-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name CortanaConsent -Value $val -PropertyType DWord -Force | Out-Null
                New-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name BingSearchEnabled -Value $val -PropertyType DWord -Force | Out-Null
                $msg = "Cortana 已$action"
            }
            "ad_id" {
                $val = if($Enable){1}else{0}
                $path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name Enabled -Value $val
                $msg = "广告 ID 已$action"
            }
            "bg_apps" {
                $val = if($Enable){0}else{1}
                Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name GlobalUserDisabled -Value $val
                $msg = "后台应用已$action"
            }
            "clipboard" {
                $val = if($Enable){1}else{0}
                $path = "HKCU:\SOFTWARE\Microsoft\Clipboard"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name EnableClipboardHistory -Value $val
                Set-ItemProperty -Path $path -Name EnableCloudClipboard -Value $val
                $msg = "剪贴板历史已$action"
            }
        }
    } catch {
        $ok = $false; $msg = "${action}失败: $_"
    }
    Write-Log "结果: $msg"
    return [PSCustomObject]@{ OK=$ok; Message=$msg }
}

# ══════════════════════════════════════════════════════════════════════
#  构建 GUI
# ══════════════════════════════════════════════════════════════════════
$form = New-Object System.Windows.Forms.Form
$form.Text = "Windows 隐私卫士"
$form.Size = New-Object System.Drawing.Size(820, 900)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1a2332")
$form.ForeColor = [System.Drawing.Color]::White
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false

# ── 顶部面板 ──
$headerPanel = New-Object System.Windows.Forms.Panel
$headerPanel.Dock = "Top"
$headerPanel.Height = 80
$headerPanel.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0f1923")
$form.Controls.Add($headerPanel)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Windows 隐私卫士"
$titleLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 16, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::White
$titleLabel.Location = New-Object System.Drawing.Point(20, 10)
$titleLabel.AutoSize = $true
$headerPanel.Controls.Add($titleLabel)

$script:statusLabel = New-Object System.Windows.Forms.Label
$script:statusLabel.Text = "正在扫描..."
$script:statusLabel.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9)
$script:statusLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#8899aa")
$script:statusLabel.Location = New-Object System.Drawing.Point(20, 48)
$script:statusLabel.AutoSize = $true
$headerPanel.Controls.Add($script:statusLabel)

$disableAllBtn = New-Object System.Windows.Forms.Button
$disableAllBtn.Text = "一键禁用所有隐私设备"
$disableAllBtn.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Bold)
$disableAllBtn.Size = New-Object System.Drawing.Size(260, 45)
$disableAllBtn.Location = New-Object System.Drawing.Point(530, 18)
$disableAllBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#d32f2f")
$disableAllBtn.ForeColor = [System.Drawing.Color]::White
$disableAllBtn.FlatStyle = "Flat"
$disableAllBtn.FlatAppearance.BorderSize = 0
$disableAllBtn.Cursor = "Hand"
$headerPanel.Controls.Add($disableAllBtn)

# ── Tabs ──
$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Location = New-Object System.Drawing.Point(10, 90)
$tabControl.Size = New-Object System.Drawing.Size(790, 760)
$tabControl.Anchor = "Top,Left,Right,Bottom"
$form.Controls.Add($tabControl)

$tabDash = New-Object System.Windows.Forms.TabPage
$tabDash.Text = "设备总览"
$tabDash.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1a2332")
$tabControl.TabPages.Add($tabDash)

$tabProc = New-Object System.Windows.Forms.TabPage
$tabProc.Text = "进程占用"
$tabProc.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1a2332")
$tabControl.TabPages.Add($tabProc)

$tabLog = New-Object System.Windows.Forms.TabPage
$tabLog.Text = "操作日志"
$tabLog.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1a2332")
$tabControl.TabPages.Add($tabLog)

# ── 设备总览 - 滚动面板 ──
$dashScroll = New-Object System.Windows.Forms.Panel
$dashScroll.AutoScroll = $true
$dashScroll.Dock = "Fill"
$dashScroll.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1a2332")
$tabDash.Controls.Add($dashScroll)

# 刷新按钮 + 监控按钮
$refreshBtn = New-Object System.Windows.Forms.Button
$refreshBtn.Text = "刷新"
$refreshBtn.Size = New-Object System.Drawing.Size(80, 32)
$refreshBtn.Location = New-Object System.Drawing.Point(10, 5)
$refreshBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1e88e5")
$refreshBtn.ForeColor = [System.Drawing.Color]::White
$refreshBtn.FlatStyle = "Flat"
$refreshBtn.FlatAppearance.BorderSize = 0
$refreshBtn.Cursor = "Hand"
$dashScroll.Controls.Add($refreshBtn)

$script:monitorBtn = New-Object System.Windows.Forms.Button
$script:monitorBtn.Text = "开启实时监控"
$script:monitorBtn.Size = New-Object System.Drawing.Size(130, 32)
$script:monitorBtn.Location = New-Object System.Drawing.Point(100, 5)
$script:monitorBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#2e7d32")
$script:monitorBtn.ForeColor = [System.Drawing.Color]::White
$script:monitorBtn.FlatStyle = "Flat"
$script:monitorBtn.FlatAppearance.BorderSize = 0
$script:monitorBtn.Cursor = "Hand"
$dashScroll.Controls.Add($script:monitorBtn)

$script:monitorLabel = New-Object System.Windows.Forms.Label
$script:monitorLabel.Text = "监控: 关闭"
$script:monitorLabel.Location = New-Object System.Drawing.Point(240, 12)
$script:monitorLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#556677")
$script:monitorLabel.AutoSize = $true
$dashScroll.Controls.Add($script:monitorLabel)

# ── 设备行容器 ──
$script:DeviceRows = @{}
$script:RowPanels = @()

function Build-DeviceRow {
    param($item, [int]$yPos)

    $panel = New-Object System.Windows.Forms.Panel
    $panel.Size = New-Object System.Drawing.Size(750, 55)
    $panel.Location = New-Object System.Drawing.Point(10, $yPos)
    $panel.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#243447")
    $panel.Tag = $item.Key

    # 状态灯
    $light = New-Object System.Windows.Forms.Panel
    $light.Size = New-Object System.Drawing.Size(16, 16)
    $light.Location = New-Object System.Drawing.Point(12, 20)
    $colorMap = @{ "safe"="#00c853"; "active"="#ff1744"; "warning"="#ffc107" }
    $light.BackColor = [System.Drawing.ColorTranslator]::FromHtml($colorMap[$item.Status])
    $panel.Controls.Add($light)

    # 图标标签
    $iconLbl = New-Object System.Windows.Forms.Label
    $iconLbl.Text = "[$($item.Icon)]"
    $iconLbl.Font = New-Object System.Drawing.Font("Consolas", 9, [System.Drawing.FontStyle]::Bold)
    $iconLbl.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#8899aa")
    $iconLbl.Location = New-Object System.Drawing.Point(38, 8)
    $iconLbl.AutoSize = $true
    $panel.Controls.Add($iconLbl)

    # 名称
    $nameLbl = New-Object System.Windows.Forms.Label
    $nameLbl.Text = $item.Name
    $nameLbl.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10, [System.Drawing.FontStyle]::Bold)
    $nameLbl.ForeColor = [System.Drawing.Color]::White
    $nameLbl.Location = New-Object System.Drawing.Point(95, 6)
    $nameLbl.AutoSize = $true
    $panel.Controls.Add($nameLbl)

    # 描述
    $descLbl = New-Object System.Windows.Forms.Label
    $descLbl.Text = $item.Desc
    $descLbl.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 8.5)
    $descLbl.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#8899aa")
    $descLbl.Location = New-Object System.Drawing.Point(95, 30)
    $descLbl.Size = New-Object System.Drawing.Size(420, 20)
    $panel.Controls.Add($descLbl)

    # 详情按钮
    $detailBtn = New-Object System.Windows.Forms.Button
    $detailBtn.Text = "详情"
    $detailBtn.Size = New-Object System.Drawing.Size(55, 30)
    $detailBtn.Location = New-Object System.Drawing.Point(590, 12)
    $detailBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#2d4159")
    $detailBtn.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#8899aa")
    $detailBtn.FlatStyle = "Flat"
    $detailBtn.FlatAppearance.BorderSize = 0
    $detailBtn.Cursor = "Hand"
    $detailBtn.Tag = $item.Key
    $detailBtn.Add_Click({
        $key = $this.Tag
        $info = $script:CurrentData | Where-Object { $_.Key -eq $key }
        if ($info) {
            $details = if($info.Details.Count -gt 0){ $info.Details -join "`r`n" } else { "暂无详细信息" }
            [System.Windows.Forms.MessageBox]::Show("$($info.Name)`r`n$($info.Desc)`r`n`r`n$details", "详细信息")
        }
    })
    $panel.Controls.Add($detailBtn)

    # 禁用/启用按钮
    $toggleBtn = New-Object System.Windows.Forms.Button
    $toggleText = if($item.Enabled){"禁用"}else{"启用"}
    $toggleColor = if($item.Enabled){"#d32f2f"}else{"#1e88e5"}
    $toggleBtn.Text = $toggleText
    $toggleBtn.Size = New-Object System.Drawing.Size(65, 30)
    $toggleBtn.Location = New-Object System.Drawing.Point(655, 12)
    $toggleBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml($toggleColor)
    $toggleBtn.ForeColor = [System.Drawing.Color]::White
    $toggleBtn.FlatStyle = "Flat"
    $toggleBtn.FlatAppearance.BorderSize = 0
    $toggleBtn.Cursor = "Hand"
    $toggleBtn.Tag = @{ Key=$item.Key; Enabled=$item.Enabled }
    $toggleBtn.Add_Click({
        $info = $this.Tag
        $enable = -not $info.Enabled
        $this.Enabled = $false; $this.Text = "..."
        $result = Set-DeviceState -Key $info.Key -Enable $enable
        [System.Windows.Forms.MessageBox]::Show($result.Message, "操作结果")
        $this.Enabled = $true
        Refresh-Dashboard
    })
    $panel.Controls.Add($toggleBtn)

    # 保存引用
    $script:DeviceRows[$item.Key] = @{ Panel=$panel; Light=$light; Desc=$descLbl; Toggle=$toggleBtn; Name=$nameLbl }

    return $panel
}

$script:CurrentData = @()

function Refresh-Dashboard {
    $script:statusLabel.Text = "正在扫描..."
    $form.Cursor = "WaitCursor"
    [System.Windows.Forms.Application]::DoEvents()

    $data = Get-AllStatus
    $script:CurrentData = $data

    # 清除旧行
    foreach ($p in $script:RowPanels) { $dashScroll.Controls.Remove($p); $p.Dispose() }
    $script:RowPanels = @()
    $script:DeviceRows = @{}

    $y = 45
    foreach ($item in $data) {
        $panel = Build-DeviceRow $item $y
        $dashScroll.Controls.Add($panel)
        $script:RowPanels += $panel
        $y += 60
    }

    $activeCount = @($data | Where-Object { $_.Enabled -and ($_.Status -eq 'active' -or $_.Status -eq 'warning') }).Count
    if ($activeCount -eq 0) {
        $script:statusLabel.Text = "所有隐私设备已关闭 - 系统安全"
        $script:statusLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#00c853")
    } else {
        $script:statusLabel.Text = "当前共 $activeCount 个设备/功能处于活跃状态"
        $script:statusLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($(if($activeCount -gt 3){"#ff1744"}else{"#ffc107"}))
    }

    $form.Cursor = "Default"
    Write-Log "扫描完成: $activeCount 个设备活跃"
}

# ── 进程占用 Tab ──
$procRefreshBtn = New-Object System.Windows.Forms.Button
$procRefreshBtn.Text = "刷新进程"
$procRefreshBtn.Size = New-Object System.Drawing.Size(100, 32)
$procRefreshBtn.Location = New-Object System.Drawing.Point(10, 10)
$procRefreshBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#1e88e5")
$procRefreshBtn.ForeColor = [System.Drawing.Color]::White
$procRefreshBtn.FlatStyle = "Flat"
$procRefreshBtn.FlatAppearance.BorderSize = 0
$procRefreshBtn.Cursor = "Hand"
$tabProc.Controls.Add($procRefreshBtn)

# Kill PID
$pidLabel = New-Object System.Windows.Forms.Label
$pidLabel.Text = "结束进程 PID:"
$pidLabel.Location = New-Object System.Drawing.Point(130, 16)
$pidLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#8899aa")
$pidLabel.AutoSize = $true
$tabProc.Controls.Add($pidLabel)

$pidBox = New-Object System.Windows.Forms.TextBox
$pidBox.Size = New-Object System.Drawing.Size(80, 25)
$pidBox.Location = New-Object System.Drawing.Point(240, 13)
$pidBox.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#243447")
$pidBox.ForeColor = [System.Drawing.Color]::White
$pidBox.BorderStyle = "FixedSingle"
$tabProc.Controls.Add($pidBox)

$killBtn = New-Object System.Windows.Forms.Button
$killBtn.Text = "结束进程"
$killBtn.Size = New-Object System.Drawing.Size(80, 30)
$killBtn.Location = New-Object System.Drawing.Point(330, 11)
$killBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#d32f2f")
$killBtn.ForeColor = [System.Drawing.Color]::White
$killBtn.FlatStyle = "Flat"
$killBtn.FlatAppearance.BorderSize = 0
$tabProc.Controls.Add($killBtn)

$script:procText = New-Object System.Windows.Forms.RichTextBox
$script:procText.Location = New-Object System.Drawing.Point(10, 50)
$script:procText.Size = New-Object System.Drawing.Size(760, 670)
$script:procText.Anchor = "Top,Left,Right,Bottom"
$script:procText.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#243447")
$script:procText.ForeColor = [System.Drawing.Color]::White
$script:procText.Font = New-Object System.Drawing.Font("Consolas", 10)
$script:procText.ReadOnly = $true
$script:procText.BorderStyle = "None"
$script:procText.Text = "点击「刷新进程」查看摄像头/麦克风占用..."
$tabProc.Controls.Add($script:procText)

$procRefreshBtn.Add_Click({
    $script:procText.Text = "正在扫描...`r`n"
    [System.Windows.Forms.Application]::DoEvents()
    $text = "============ 摄像头进程占用 ============`r`n`r`n"
    $camApps = Get-DeviceUsage "webcam"
    if ($camApps.Count -gt 0) {
        foreach ($a in $camApps) { $text += "  [使用中] $a`r`n" }
    } else { $text += "  当前无进程占用摄像头`r`n" }
    $text += "`r`n============ 麦克风进程占用 ============`r`n`r`n"
    $micApps = Get-DeviceUsage "microphone"
    if ($micApps.Count -gt 0) {
        foreach ($a in $micApps) { $text += "  [使用中] $a`r`n" }
    } else { $text += "  当前无进程占用麦克风`r`n" }
    $text += "`r`n扫描时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`r`n"
    $script:procText.Text = $text
})

$killBtn.Add_Click({
    $pidStr = $pidBox.Text.Trim()
    if (-not $pidStr) { [System.Windows.Forms.MessageBox]::Show("请输入 PID"); return }
    try {
        $pid = [int]$pidStr
        $proc = Get-Process -Id $pid -ErrorAction Stop
        $r = [System.Windows.Forms.MessageBox]::Show("确定结束进程 $($proc.ProcessName) (PID: $pid)?", "确认", "YesNo", "Warning")
        if ($r -eq "Yes") {
            Stop-Process -Id $pid -Force
            Write-Log "已结束进程 $($proc.ProcessName) PID=$pid"
            [System.Windows.Forms.MessageBox]::Show("已结束进程 $($proc.ProcessName)")
            $pidBox.Text = ""
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show("操作失败: $_", "错误")
    }
})

# ── 日志 Tab ──
$script:LogBox = New-Object System.Windows.Forms.TextBox
$script:LogBox.Multiline = $true
$script:LogBox.ScrollBars = "Vertical"
$script:LogBox.Location = New-Object System.Drawing.Point(10, 10)
$script:LogBox.Size = New-Object System.Drawing.Size(760, 710)
$script:LogBox.Anchor = "Top,Left,Right,Bottom"
$script:LogBox.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#243447")
$script:LogBox.ForeColor = [System.Drawing.Color]::White
$script:LogBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$script:LogBox.ReadOnly = $true
$script:LogBox.BorderStyle = "None"
$tabLog.Controls.Add($script:LogBox)

# ── 事件绑定 ──
$refreshBtn.Add_Click({ Refresh-Dashboard })

$script:Monitoring = $false
$script:MonitorTimer = New-Object System.Windows.Forms.Timer
$script:MonitorTimer.Interval = 30000
$script:MonitorTimer.Add_Tick({ Refresh-Dashboard })

$script:monitorBtn.Add_Click({
    if ($script:Monitoring) {
        $script:Monitoring = $false
        $script:MonitorTimer.Stop()
        $script:monitorBtn.Text = "开启实时监控"
        $script:monitorBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#2e7d32")
        $script:monitorLabel.Text = "监控: 关闭"
        Write-Log "实时监控已关闭"
    } else {
        $script:Monitoring = $true
        $script:MonitorTimer.Start()
        $script:monitorBtn.Text = "停止监控"
        $script:monitorBtn.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#d32f2f")
        $script:monitorLabel.Text = "监控: 运行中 (每30秒)"
        $script:monitorLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#00c853")
        Write-Log "实时监控已开启"
    }
})

$disableAllBtn.Add_Click({
    $r = [System.Windows.Forms.MessageBox]::Show(
        "确定要一键禁用所有隐私相关设备和功能吗?`r`n`r`n将禁用:`r`n- 摄像头、麦克风`r`n- 定位服务`r`n- 蓝牙、WiFi`r`n- 传感器服务`r`n- 远程桌面`r`n- 诊断数据`r`n- 广告 ID、Cortana`r`n- 剪贴板云同步`r`n- 后台应用",
        "确认操作", "YesNo", "Warning")
    if ($r -ne "Yes") { return }

    Write-Log "===== 一键禁用所有 ====="
    $disableAllBtn.Enabled = $false; $disableAllBtn.Text = "正在禁用..."
    $form.Cursor = "WaitCursor"
    [System.Windows.Forms.Application]::DoEvents()

    $keys = @("camera","microphone","location","bluetooth","wifi","sensor","rdp","telemetry","cortana","ad_id","bg_apps","clipboard")
    $report = ""
    $success = 0
    foreach ($k in $keys) {
        $result = Set-DeviceState -Key $k -Enable $false
        $icon = if($result.OK){"OK"}else{"FAIL"}
        $report += "[$icon] $($result.Message)`r`n"
        if ($result.OK) { $success++ }
    }

    $form.Cursor = "Default"
    $disableAllBtn.Enabled = $true; $disableAllBtn.Text = "一键禁用所有隐私设备"
    Write-Log "一键禁用完成: $success/$($keys.Count) 成功"
    [System.Windows.Forms.MessageBox]::Show("操作完成 ($success/$($keys.Count) 成功)`r`n`r`n$report", "一键禁用结果")
    Refresh-Dashboard
})

# ── 托盘图标 ──
$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
$notifyIcon.Text = "Windows 隐私卫士"
$notifyIcon.Visible = $true

# 动态生成图标
$bmp = New-Object System.Drawing.Bitmap(32,32)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = "AntiAlias"
$g.FillEllipse([System.Drawing.Brushes]::Green, 2, 2, 28, 28)
$g.Dispose()
$notifyIcon.Icon = [System.Drawing.Icon]::FromHandle($bmp.GetHicon())

$trayMenu = New-Object System.Windows.Forms.ContextMenuStrip
$showItem = $trayMenu.Items.Add("显示主窗口")
$showItem.Add_Click({ $form.Show(); $form.WindowState = "Normal"; $form.Activate() })
$trayMenu.Items.Add("-")
$exitItem = $trayMenu.Items.Add("退出")
$exitItem.Add_Click({ $notifyIcon.Visible = $false; $form.Close() })
$notifyIcon.ContextMenuStrip = $trayMenu

$notifyIcon.Add_DoubleClick({ $form.Show(); $form.WindowState = "Normal"; $form.Activate() })

$form.Add_Resize({
    if ($form.WindowState -eq "Minimized") {
        $form.Hide()
        $notifyIcon.ShowBalloonTip(2000, "隐私卫士", "已最小化到系统托盘", "Info")
    }
})

$form.Add_FormClosing({
    $notifyIcon.Visible = $false
    $script:MonitorTimer.Stop()
})

# ── 启动 ──
Write-Log "Windows 隐私卫士启动"
Refresh-Dashboard
[void]$form.ShowDialog()
