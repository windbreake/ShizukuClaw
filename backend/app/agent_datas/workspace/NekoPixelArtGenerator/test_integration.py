#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试脚本
测试整个像素画生成器的Python后端功能
"""

import sys
import os
import tempfile
from PIL import Image
import numpy as np

def test_complete_workflow():
    """测试完整的工作流程"""
    try:
        # 导入必要的模块
        import processors
        import pixelate
        
        print("✓ 成功导入所有模块")
        
        # 创建测试图像
        test_image = Image.new('RGB', (200, 200), color='red')
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(test_image)
            draw.rectangle([50, 50, 150, 150], fill='blue')
            draw.ellipse([75, 75, 125, 125], fill='green')
        except ImportError:
            pass  # 如果没有ImageDraw，就使用纯色图像
        
        print("✓ 成功创建测试图像")
        
        # 测试完整处理管道
        from io import BytesIO
        img_byte_arr = BytesIO()
        test_image.save(img_byte_arr, format='PNG')
        image_bytes = img_byte_arr.getvalue()
        
        options = {
            'block_size': 8,
            'max_colors': 32,
            'enable_dither': True,
            'dither_strength': 0.1,
            'enable_cartoon': False,
            'palette_name': 'gameboy'
        }
        
        result_bytes = processors.process_image_internal(image_bytes, options)
        result_image = Image.open(BytesIO(result_bytes))
        assert result_image.size == test_image.size, "完整处理管道后尺寸不匹配"
        print("✓ 完整处理管道测试通过")
        
        # 测试命令行接口
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.png")
            output_path = os.path.join(temp_dir, "output.png")
            
            test_image.save(input_path, "PNG")
            
            # 模拟命令行调用
            import subprocess
            import sys
            
            cmd = [
                sys.executable, 
                'pixelate.py',
                '--input', input_path,
                '--output', output_path,
                '--pixel-size', '10',
                '--color-count', '16',
                '--palette', 'gameboy',
                '--dithering',
                '--dither-strength', '0.1'
            ]
            
            # 切换到脚本目录
            original_cwd = os.getcwd()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.exists(os.path.join(script_dir, 'PythonScripts')):
                script_dir = os.path.join(script_dir, 'PythonScripts')
            os.chdir(script_dir)
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and os.path.exists(output_path):
                    print("✓ 命令行接口测试通过")
                else:
                    print(f"✗ 命令行接口测试失败: {result.stderr}")
                    return False
            except subprocess.TimeoutExpired:
                print("✗ 命令行接口测试超时")
                return False
            finally:
                os.chdir(original_cwd)
        
        print("\n🎉 所有测试通过！后端功能正常工作。")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # 添加当前目录到Python路径
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PythonScripts'))
    
    print("开始集成测试...")
    success = test_complete_workflow()
    sys.exit(0 if success else 1)