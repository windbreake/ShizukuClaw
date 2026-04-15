# 像素画生成工具部署脚本
# PowerShell 脚本用于自动化部署过程

param(
    [string]$Configuration = "Release",
    [string]$Platform = "AnyCPU",
    [switch]$InstallPython = $false,
    [switch]$InstallDependencies = $false,
    [switch]$BuildOnly = $false,
    [switch]$Publish = $false,
    [switch]$CreateInstaller = $false
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# 检查管理员权限
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 检查依赖
function Test-Dependencies {
    Write-Info "检查系统依赖..."
    
    # 检查 .NET SDK
    try {
        $dotnetVersion = dotnet --version
        Write-Success ".NET SDK 已安装: $dotnetVersion"
    }
    catch {
        Write-Error ".NET SDK 未安装，请先安装 .NET 6.0 SDK"
        return $false
    }
    
    # 检查 Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python 已安装: $pythonVersion"
        
        # 检查 pip
        $pipVersion = pip --version 2>&1
        Write-Success "pip 已安装: $pipVersion"
    }
    catch {
        Write-Warning "Python 未安装或不在PATH中"
        if ($InstallPython) {
            Install-Python
        } else {
            Write-Error "请安装 Python 3.8+ 或使用 -InstallPython 参数"
            return $false
        }
    }
    
    return $true
}

# 安装 Python
function Install-Python {
    Write-Info "正在安装 Python..."
    try {
        # 使用 winget 安装 Python
        winget install Python.Python.3.11
        Write-Success "Python 安装完成"
    }
    catch {
        Write-Error "Python 安装失败: $_"
        Write-Info "请手动从 https://www.python.org/downloads/ 下载安装"
        exit 1
    }
}

# 安装 Python 依赖
function Install-PythonDependencies {
    Write-Info "正在安装 Python 依赖..."
    try {
        $requirementsPath = Join-Path $PSScriptRoot "PythonScripts\requirements.txt"
        if (Test-Path $requirementsPath) {
            pip install -r $requirementsPath
            Write-Success "Python 依赖安装完成"
        } else {
            Write-Warning "requirements.txt 文件未找到"
        }
    }
    catch {
        Write-Error "Python 依赖安装失败: $_"
        exit 1
    }
}

# 构建项目
function Build-Project {
    param([string]$Config, [string]$Platform)
    
    Write-Info "正在构建项目 ($Config - $Platform)..."
    
    try {
        # 清理之前的构建
        if (Test-Path "bin") {
            Remove-Item -Recurse -Force "bin"
        }
        if (Test-Path "obj") {
            Remove-Item -Recurse -Force "obj"
        }
        
        # 执行构建
        dotnet build -c $Config -p:Platform=$Platform
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "项目构建成功"
            return $true
        } else {
            Write-Error "项目构建失败"
            return $false
        }
    }
    catch {
        Write-Error "构建过程出错: $_"
        return $false
    }
}

# 发布项目
function Publish-Project {
    param([string]$Config)
    
    Write-Info "正在发布项目 ($Config)..."
    
    try {
        $publishDir = Join-Path $PSScriptRoot "publish"
        
        if (Test-Path $publishDir) {
            Remove-Item -Recurse -Force $publishDir
        }
        
        # 发布应用程序
        dotnet publish -c $Config -o $publishDir --self-contained false
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "项目发布成功"
            
            # 复制 Python 脚本
            $pythonScriptsDir = Join-Path $publishDir "PythonScripts"
            if (!(Test-Path $pythonScriptsDir)) {
                New-Item -ItemType Directory -Path $pythonScriptsDir | Out-Null
            }
            
            Copy-Item -Path "PythonScripts\*.py" -Destination $pythonScriptsDir
            Copy-Item -Path "PythonScripts\requirements.txt" -Destination $pythonScriptsDir
            
            # 复制演示图片
            $resourcesDir = Join-Path $publishDir "Resources"
            if (!(Test-Path $resourcesDir)) {
                New-Item -ItemType Directory -Path $resourcesDir | Out-Null
            }
            
            Copy-Item -Path "Resources\*" -Destination $resourcesDir -Recurse
            
            Write-Success "文件复制完成"
            return $true
        } else {
            Write-Error "项目发布失败"
            return $false
        }
    }
    catch {
        Write-Error "发布过程出错: $_"
        return $false
    }
}

# 创建安装程序
function Create-Installer {
    Write-Info "正在创建安装程序..."
    
    try {
        # 检查是否有安装程序制作工具
        $installerTools = @(
            "Advanced Installer",
            "WiX Toolset",
            "Inno Setup"
        )
        
        $toolFound = $false
        foreach ($tool in $installerTools) {
            if (Get-Command $tool -ErrorAction SilentlyContinue) {
                Write-Success "找到安装程序制作工具: $tool"
                $toolFound = $true
                break
            }
        }
        
        if (!$toolFound) {
            Write-Warning "未找到安装程序制作工具"
            Write-Info "推荐使用以下工具之一:"
            Write-Info "- Advanced Installer (https://www.advancedinstaller.com/)"
            Write-Info "- WiX Toolset (https://wixtoolset.org/)"
            Write-Info "- Inno Setup (https://jrsoftware.org/isinfo.php)"
            return $false
        }
        
        Write-Success "请使用上述工具手动创建安装程序"
        return $true
    }
    catch {
        Write-Error "创建安装程序出错: $_"
        return $false
    }
}

# 主执行流程
function Main {
    Write-Info "开始部署像素画生成工具..."
    Write-Info "配置: $Configuration, 平台: $Platform"
    
    # 检查管理员权限（如果需要）
    if ($InstallPython -or $CreateInstaller) {
        if (!(Test-Administrator)) {
            Write-Error "需要管理员权限执行此操作"
            Write-Info "请以管理员身份运行 PowerShell"
            exit 1
        }
    }
    
    # 检查依赖
    if (!(Test-Dependencies)) {
        exit 1
    }
    
    # 安装 Python 依赖
    if ($InstallDependencies) {
        Install-PythonDependencies
    }
    
    # 构建项目
    if (!(Build-Project -Config $Configuration -Platform $Platform)) {
        exit 1
    }
    
    # 发布项目
    if ($Publish) {
        if (!(Publish-Project -Config $Configuration)) {
            exit 1
        }
    }
    
    # 创建安装程序
    if ($CreateInstaller) {
        Create-Installer
    }
    
    Write-Success "部署完成！"
    
    if ($Publish) {
        $exePath = Join-Path $PSScriptRoot "publish\PixelArtGenerator.exe"
        if (Test-Path $exePath) {
            Write-Info "可执行文件位置: $exePath"
            Write-Info "您可以运行程序开始使用了！"
        }
    }
}

# 显示帮助信息
function Show-Help {
    Write-Host "像素画生成工具部署脚本" -ForegroundColor Cyan
    Write-Host "用法: .\deploy.ps1 [参数]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "参数:"
    Write-Host "  -Configuration <Debug|Release>  构建配置 (默认: Release)"
    Write-Host "  -Platform <AnyCPU|x64|x86>      目标平台 (默认: AnyCPU)"
    Write-Host "  -InstallPython                  自动安装 Python"
    Write-Host "  -InstallDependencies            安装 Python 依赖"
    Write-Host "  -BuildOnly                      仅构建项目"
    Write-Host "  -Publish                        发布应用程序"
    Write-Host "  -CreateInstaller                创建安装程序"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\deploy.ps1 -Configuration Debug -InstallDependencies"
    Write-Host "  .\deploy.ps1 -Publish -CreateInstaller"
    Write-Host "  .\deploy.ps1 -BuildOnly"
}

# 处理命令行参数
if ($args -contains "-h" -or $args -contains "--help") {
    Show-Help
    exit 0
}

# 执行主函数
Main