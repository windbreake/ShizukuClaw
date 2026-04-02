import os

# 删除 test2.txt 文件
file_path = "./agent_datas/workspace/test2.txt"
if os.path.exists(file_path):
    os.remove(file_path)
    print(f"已删除文件: {file_path}")
else:
    print(f"文件不存在: {file_path}")