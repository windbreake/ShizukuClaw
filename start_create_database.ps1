Write-Host "============================="
Write-Host "  数据库一键创建工具"
Write-Host "============================="
Write-Host ""
Write-Host "正在创建数据库和表..."
Write-Host ""

python src/create_database.py

Write-Host ""
Write-Host "数据库创建完成！"
Write-Host ""
Write-Host "按任意键继续..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")