#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试前端和后端之间的集成
创建一个简单测试图片并进行像素化处理
"""

import sys
import os
from PIL import Image, ImageDraw
import subprocess


def create_test_image():
    """创建一个测试图像"""
    # 创建一个300x300的彩色图像
    image = Image.new('RGB', (300, 300), color='white')
    draw = ImageDraw.Draw(image)

    # 绘制一些几何图形
    draw.rectangle([50, 50, 250, 250], fill='red', outline='black')
    draw.ellipse([100, 100, 200, 200], fill='blue', outline='black')
    draw.polygon([(150, 50), (100, 150), (200, 150)], fill='green')

    return image


def test_pixelation_process():
    """测试像素化处理过程"""
    print("开始测试前端和后端集成...")

    # 创建测试图像
    test_image = create_test_image()
    print("✓ 测试图像创建成功")

    # 保存测试图像
    input_path = "test_input.png"
    output_path = "test_output.png"
    test_image.save(input_path)
    print(f"✓ 测试图像已保存为 {input_path}")

    try:
        # 构建命令行参数
        cmd = [
            sys.executable,
            'PythonScripts/pixelate.py',
            '--input', input_path,
            '--output', output_path,
            '--pixel-size', '16',
            '--color-count', '32',
            '--palette', 'gameboy',
            '--dithering'
        ]

        print("✓ 正在执行像素化处理...")

        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✓ 像素化处理执行成功")
            if os.path.exists(output_path):
                print(f"✓ 输出文件已生成: {output_path}")
                print("🎉 前端和后端集成测试通过!")
                return True
            else:
                print("✗ 输出文件未生成")
                return False
        else:
            print(f"✗ 像素化处理失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ 像素化处理超时")
        return False
    except Exception as e:
        print(f"✗ 执行过程中出现错误: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(input_path):
            os.remove(input_path)
            print(f"✓ 已清理测试文件: {input_path}")

        if os.path.exists(output_path):
            os.remove(output_path)
            print(f"✓ 已清理测试文件: {output_path}")


if __name__ == '__main__':
    # 添加当前目录到Python路径
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    success = test_pixelation_process()

    if success:
        print("\n✅ 集成测试成功完成!")
        sys.exit(0)
    else:
        print("\n❌ 集成测试失败!")
        sys.exit(1)
