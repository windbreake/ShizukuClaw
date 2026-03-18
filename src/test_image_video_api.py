"""图片和视频API测试模块"""

import json
import requests


def test_image_generation():
    """测试图片生成API"""
    url = "http://localhost:5001/v1/images/generations"
    
    headers = {
        "Authorization": "Bearer neko-proxy-key-123",
        "Content-Type": "application/json"
    }
    
    data = {
        "prompt": "一只可爱的猫咪在阳光下玩耍",
        "n": 1,
        "size": "1024x1024"
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("图片生成API响应:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    return response


def test_video_generation():
    """测试视频生成API"""
    url = "http://localhost:5001/v1/videos/generations"
    
    headers = {
        "Authorization": "Bearer neko-proxy-key-123",
        "Content-Type": "application/json"
    }
    
    data = {
        "prompt": "一只猫咪在花园里追逐蝴蝶的视频",
        "duration": 5
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    print("\n视频生成API响应:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    return response


def main():
    """主函数，执行测试"""
    print("开始测试图片和视频生成API...")
    
    # 测试图片生成
    try:
        image_response = test_image_generation()
        print(f"图片生成状态码: {image_response.status_code}")
    except requests.RequestException as e:
        print(f"图片生成测试失败: {e}")
    except json.JSONDecodeError as e:
        print(f"图片生成响应解析失败: {e}")
    except Exception as e:
        print(f"图片生成测试出现未知错误: {e}")
    
    # 测试视频生成
    try:
        video_response = test_video_generation()
        print(f"视频生成状态码: {video_response.status_code}")
    except requests.RequestException as e:
        print(f"视频生成测试失败: {e}")
    except json.JSONDecodeError as e:
        print(f"视频生成响应解析失败: {e}")
    except Exception as e:
        print(f"视频生成测试出现未知错误: {e}")
    
    print("测试完成。")


if __name__ == "__main__":
    main()