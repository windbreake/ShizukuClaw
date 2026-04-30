# run_with_logging.ps1
# 运行 PixelArtGenerator 并记录任何异常到项目目录

# 切换到项目目录
Set-Location "C:\Users\win11\Desktop\AgentPix\DMEO"

# 运行应用程序并将输出重定向到日志文件
dotnet run > application_output.log 2>&1

Write-Host "Application finished. Check application_output.log for details."