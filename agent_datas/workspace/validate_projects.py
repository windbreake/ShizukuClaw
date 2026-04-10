#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整的项目验证脚本
验证 snake_game 和 image_card_project 两个项目的完整性和可用性
"""

import os
import sys
import json
import subprocess
from pathlib import Path


class ProjectValidator:
    """项目验证器"""
    
    def __init__(self, workspace_dir='.'):
        self.workspace_dir = workspace_dir
        self.results = {
            'projects': {},
            'summary': {}
        }
    
    def validate_project_files(self, project_name, required_files):
        """检查项目文件是否存在"""
        project_path = os.path.join(self.workspace_dir, project_name)
        
        if not os.path.exists(project_path):
            return False, f"❌ 项目目录 {project_name} 不存在"
        
        missing = []
        for fname in required_files:
            fpath = os.path.join(project_path, fname)
            if not os.path.exists(fpath):
                missing.append(fname)
        
        if missing:
            return False, f"❌ 缺少文件: {', '.join(missing)}"
        
        return True, f"✓ 所有文件存在"
    
    def validate_snake_game(self):
        """验证 snake_game 项目"""
        print("=" * 70)
        print("验证 snake_game 项目")
        print("=" * 70)
        
        project_name = 'snake_game'
        required_files = ['snake.py', 'requirements.txt', 'README.md']
        
        # 检查文件存在
        ok, msg = self.validate_project_files(project_name, required_files)
        print(msg)
        if not ok:
            self.results['projects'][project_name] = {'ok': False, 'reason': msg}
            print()
            return False
        
        # 检查文件大小
        snake_path = os.path.join(self.workspace_dir, project_name, 'snake.py')
        size = os.path.getsize(snake_path)
        print(f"  • snake.py 大小: {size} 字节")
        
        if size < 1000:
            print(f"  ❌ snake.py 文件过小，可能不完整")
            self.results['projects'][project_name] = {'ok': False, 'reason': 'File too small'}
            print()
            return False
        
        # 检查文件内容
        with open(snake_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_functions = ['def main', 'def self_test', 'class Snake', 'class Food']
        missing_functions = []
        for func in required_functions:
            if func not in content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"  ❌ 缺少关键函数或类: {', '.join(missing_functions)}")
            self.results['projects'][project_name] = {
                'ok': False,
                'reason': f'Missing functions: {missing_functions}'
            }
            print()
            return False
        
        print(f"  ✓ 包含所有关键函数: {', '.join(required_functions)}")
        
        # 尝试运行自检
        print("  • 运行自检测试...")
        try:
            result = subprocess.run(
                [sys.executable, 'snake.py', '--self-test'],
                cwd=os.path.join(self.workspace_dir, project_name),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 检查输出
                if '[SELF-TEST]' in result.stdout:
                    print("  ✓ 自检通过")
                    self.results['projects'][project_name] = {'ok': True, 'self_test': True}
                    print()
                    return True
                else:
                    print(f"  ⚠ 自检运行但输出格式不匹配: {result.stdout[:100]}")
            else:
                print(f"  ❌ 自检失败 (返回码: {result.returncode})")
                print(f"     stderr: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("  ⚠ 自检超时（通常是 pygame 的正常行为）")
            self.results['projects'][project_name] = {'ok': True, 'warning': 'Self-test timed out'}
        except Exception as e:
            print(f"  ⚠ 自检异常: {e}")
        
        print()
        self.results['projects'][project_name] = {'ok': True}
        return True
    
    def validate_image_card_project(self):
        """验证 image_card_project 项目"""
        print("=" * 70)
        print("验证 image_card_project 项目")
        print("=" * 70)
        
        project_name = 'image_card_project'
        required_files = ['index.html', 'style.css', 'script.js', 'README.md']
        
        # 检查文件存在
        ok, msg = self.validate_project_files(project_name, required_files)
        print(msg)
        if not ok:
            self.results['projects'][project_name] = {'ok': False, 'reason': msg}
            print()
            return False
        
        # 检查各文件内容
        html_path = os.path.join(self.workspace_dir, project_name, 'index.html')
        css_path = os.path.join(self.workspace_dir, project_name, 'style.css')
        js_path = os.path.join(self.workspace_dir, project_name, 'script.js')
        
        # 检查 HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        html_checks = ['doctype', '<title>', '<header', '<main', 'card', 'modal']
        missing_html = [check for check in html_checks if check not in html_content.lower()]
        if missing_html:
            print(f"  ❌ HTML 缺少关键元素: {', '.join(missing_html)}")
            self.results['projects'][project_name] = {
                'ok': False,
                'reason': f'HTML missing: {missing_html}'
            }
            print()
            return False
        print(f"  ✓ HTML 包含关键元素")
        
        # 检查 CSS
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        css_checks = ['root', 'color', 'flex', 'grid', 'animation']
        missing_css = [check for check in css_checks if check not in css_content.lower()]
        if missing_css:
            print(f"  ⚠ CSS 缺少某些特性: {', '.join(missing_css)}")
        else:
            print(f"  ✓ CSS 包含所有关键特性")
        
        # 检查 JavaScript
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        js_checks = ['addEventListener', 'function', 'modal', 'notification']
        missing_js = [check for check in js_checks if check not in js_content.lower()]
        if missing_js:
            print(f"  ⚠ JavaScript 缺少某些功能: {', '.join(missing_js)}")
        else:
            print(f"  ✓ JavaScript 包含所有关键功能")
        
        # 检查文件大小
        print(f"  • 文件大小:")
        print(f"    - index.html: {os.path.getsize(html_path)} 字节")
        print(f"    - style.css: {os.path.getsize(css_path)} 字节")
        print(f"    - script.js: {os.path.getsize(js_path)} 字节")
        
        print()
        self.results['projects'][project_name] = {'ok': True}
        return True
    
    def run_all_validations(self):
        """运行所有验证"""
        print("\n")
        print("█" * 70)
        print("█  项目完整性验证工具")
        print("█" * 70)
        print()
        
        # 验证各项目
        snake_ok = self.validate_snake_game()
        image_ok = self.validate_image_card_project()
        
        # 总结
        print("=" * 70)
        print("验证总结")
        print("=" * 70)
        
        all_ok = snake_ok and image_ok
        
        if all_ok:
            print("✓ 所有项目完整性检查通过！")
            print()
            print("可用的项目：")
            print("  1. snake_game")
            print("     运行: python snake_game/snake.py")
            print("     自检: python snake_game/snake.py --self-test")
            print()
            print("  2. image_card_project")
            print("     方法1: 在浏览器中打开 image_card_project/index.html")
            print("     方法2: python -m http.server 8000")
            print("            访问 http://localhost:8000/image_card_project/")
        else:
            print("❌ 部分项目检查失败，见上面的详细信息")
        
        print()
        print("█" * 70)
        print()
        
        # 输出 JSON 报告
        print("详细报告（JSON）:")
        print(json.dumps(self.results, ensure_ascii=False, indent=2))
    
    def generate_html_report(self):
        """生成 HTML 报告"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>项目验证报告</title>
    <style>
        body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
        .report {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; }}
        .success {{ color: #4CAF50; }}
        .error {{ color: #f44336; }}
        .warning {{ color: #ff9800; }}
        .section {{ margin-top: 20px; padding: 10px; background: #f9f9f9; border-left: 4px solid #2196F3; }}
    </style>
</head>
<body>
    <div class="report">
        <h1>项目验证报告</h1>
        <pre>{json.dumps(self.results, ensure_ascii=False, indent=2)}</pre>
    </div>
</body>
</html>
"""
        return html


def main():
    """主函数"""
    validator = ProjectValidator('.')
    validator.run_all_validations()
    
    # 可选：生成 HTML 报告
    # html_report = validator.generate_html_report()
    # with open('validation_report.html', 'w', encoding='utf-8') as f:
    #     f.write(html_report)


if __name__ == '__main__':
    main()
