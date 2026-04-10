import os
import sys
import json
import subprocess

print("=== 开始部署技能 (GitHub: microsoft/skills) ===")
print(f"技能信息: source=github, skill_id=microsoft__skills, name=skills, url=https://github.com/microsoft/skills")

# 检查当前目录
print(f"\n当前工作目录: {os.getcwd()}")
print("目录内容:")
for item in os.listdir('.'):
 print(f" {item}")

# 检查是否已有技能目录
skill_name = "microsoft_skills"
deploy_dir = skill_name

print(f"\n准备部署技能: {skill_name}")
print(f"技能目录: {deploy_dir}")

# 检查是否已存在
if os.path.exists(deploy_dir):
 print(f"警告: 目录 {deploy_dir} 已存在")
 # 列出已有内容
 print(f"现有内容:")
 for item in os.listdir(deploy_dir):
 print(f" {item}")
else:
 print(f"目录 {deploy_dir} 不存在，将创建")

# 尝试使用git clone
print(f"\n尝试从GitHub克隆技能库...")
try:
 # 先检查git是否可用
 result = subprocess.run(['git', '--version'], capture_output=True, text=True)
 if result.returncode == 0:
 print(f"Git可用: {result.stdout.strip()}")
 
 # 克隆仓库
 clone_cmd = ['git', 'clone', 'https://github.com/microsoft/skills.git', deploy_dir]
 print(f"执行命令: {' '.join(clone_cmd)}")
 
 result = subprocess.run(clone_cmd, capture_output=True, text=True)
 if result.returncode == 0:
 print(f"克隆成功!")
 print(f"输出: {result.stdout}")
 else:
 print(f"克隆失败!")
 print(f"错误: {result.stderr}")
 else:
 print(f"Git不可用: {result.stderr}")
except Exception as e:
 print(f"Git操作异常: {e}")

# 检查部署结果
print(f"\n=== 部署结果检查 ===")
if os.path.exists(deploy_dir):
 print(f"✓ 技能目录已创建: {deploy_dir}")
 
 # 统计文件数量
 file_count = 0
 dir_count = 0
 for root, dirs, files in os.walk(deploy_dir):
 file_count += len(files)
 dir_count += len(dirs)
 
 print(f"✓ 目录统计: {dir_count} 个子目录, {file_count} 个文件")
 
 # 列出根目录内容
 print(f"\n技能根目录内容:")
 for item in os.listdir(deploy_dir):
 item_path = os.path.join(deploy_dir, item)
 if os.path.isdir(item_path):
 print(f" 📁 {item}/")
 else:
 print(f" 📄 {item}")
 
 # 检查是否有README或说明文件
 readme_files = []
 for f in os.listdir(deploy_dir):
 if f.lower().startswith('readme'):
 readme_files.append(f)
 
 if readme_files:
 print(f"\n找到说明文件: {readme_files}")
 # 读取第一个README
 readme_path = os.path.join(deploy_dir, readme_files[0])
 try:
 with open(readme_path, 'r', encoding='utf-8') as f:
 content = f.read(500) # 读取前500字符
 print(f"\nREADME预览:")
 print(content[:500] + "..." if len(content) > 500 else content)
 except Exception as e:
 print(f"读取README失败: {e}")
else:
 print(f"✗ 技能目录未创建")

print(f"\n=== 部署完成 ===")