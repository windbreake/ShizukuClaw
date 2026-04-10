import os
import subprocess
import sys

# 检查当前目录
print("当前工作目录:", os.getcwd())
print("目录内容:")
for item in os.listdir('.'):
 print(f" {item}")

# 检查是否已存在NekoPixelArtGenerator目录
target_dir = "NekoPixelArtGenerator"
if os.path.exists(target_dir):
 print(f"\n目录 {target_dir} 已存在")
 items = os.listdir(target_dir)
 print(f"现有文件数: {len(items)}")
 for item in items[:10]:
 print(f" {item}")
 if len(items) > 10:
 print(f" ... 还有 {len(items)-10} 个文件")
else:
 print(f"\n目录 {target_dir} 不存在，准备克隆...")
 # 尝试使用git clone
 try:
 result = subprocess.run(['git', 'clone', 'https://github.com/windbreake/NekoPixelArtGenerator.git'], 
 capture_output=True, text=True)
 print("Git clone 输出:", result.stdout)
 if result.stderr:
 print("Git clone 错误:", result.stderr)
 print("返回码:", result.returncode)
 
 # 检查是否克隆成功
 if os.path.exists(target_dir):
 print(f"成功克隆到 {target_dir}")
 else:
 print("克隆失败，目录未创建")
 except Exception as e:
 print(f"Git clone 异常: {e}")
 print("尝试备用方法...")