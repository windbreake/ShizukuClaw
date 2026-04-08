"""Web API测试模块，用于测试网络搜索功能"""

import csv
import os

import requests


def search_and_save(query, filename="results.csv", api_key=None, session=None):
    """搜索并保存结果到CSV文件
    
    Args:
        query (str): 搜索查询
        filename (str): 保存结果的文件名，默认为"results.csv"
        api_key (str): API key，可选，不传时读取环境变量
        session: requests-like 会话对象，便于测试注入
    """
    api_key = api_key or os.getenv("BOCHAAI_API_KEY", "")
    if not api_key:
        raise ValueError("BOCHAAI_API_KEY is required")

    client = session or requests
    url = "https://api.bochaai.com/v1/web-search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"query": query, "count": 10}

    response = client.post(url, headers=headers, json=payload, timeout=30)

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


def test_search_and_save_writes_csv(tmp_path, monkeypatch):
    """验证搜索结果可写入 CSV。"""

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "data": {
                    "webPages": {
                        "value": [
                            {"name": "n1", "url": "u1", "snippet": "s1"},
                            {"name": "n2", "url": "u2", "snippet": "s2"},
                        ]
                    }
                }
            }

    class _FakeSession:
        @staticmethod
        def post(*_args, **_kwargs):
            return _FakeResponse()

    monkeypatch.setenv("BOCHAAI_API_KEY", "dummy-key")
    out = tmp_path / "results.csv"
    search_and_save("test query", filename=str(out), session=_FakeSession())

    assert out.exists()
    rows = out.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3


def main():
    """主函数"""
    # 使用示例
    search_and_save("深度学习框架对比")


if __name__ == "__main__":
    main()