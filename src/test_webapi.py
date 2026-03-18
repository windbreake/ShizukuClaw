"""Web API测试模块，用于测试网络搜索功能"""

import csv
import requests


def search_and_save(query, filename="results.csv"):
    """搜索并保存结果到CSV文件
    
    Args:
        query (str): 搜索查询
        filename (str): 保存结果的文件名，默认为"results.csv"
    """
    api_key = "sk-0f0c3eea391f468bbe7bb027a98e62f8"
    url = "https://api.bochaai.com/v1/web-search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"query": query, "count": 10}

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code == 200:
        data = response.json()["data"]["webPages"]["value"]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["标题", "链接", "摘要"])
            for item in data:
                writer.writerow([item["name"], item["url"], item["snippet"]])
        print(f"结果已保存至{filename}！")
    else:
        print("搜索失败！")


def main():
    """主函数"""
    # 使用示例
    search_and_save("深度学习框架对比")


if __name__ == "__main__":
    main()