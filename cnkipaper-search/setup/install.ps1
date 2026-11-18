# 在技能目录下创建 .venv 并安装全部依赖（Windows PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File setup\install.ps1
$ErrorActionPreference = "Stop"

$SkillDir = Split-Path -Parent $PSScriptRoot
$VenvDir  = Join-Path $SkillDir ".venv"
$VenvPy   = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 python，请先安装 Python 3.10+ 并加入 PATH"
}

Write-Host "[1/4] 创建 venv: $VenvDir"
python -m venv $VenvDir

Write-Host "[2/4] 升级 pip"
& $VenvPy -m pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple

Write-Host "[3/4] 安装依赖（cnki-deepsearch / openpyxl / markitdown）"
& $VenvPy -m pip install -r (Join-Path $SkillDir "requirements.txt") -i https://pypi.tuna.tsinghua.edu.cn/simple

Write-Host "[4/4] 安装 Playwright Chromium（cnki-deepsearch 需要）"
& $VenvPy -m playwright install chromium

Write-Host ""
Write-Host "完成。"
Write-Host "技能目录: $SkillDir"
Write-Host "解释器:   $VenvPy"
Write-Host "下一步:   把 setup/mcp.example.json 里的 <SKILL_DIR> 替换为上面的技能目录，合并进 MCP 配置。"
