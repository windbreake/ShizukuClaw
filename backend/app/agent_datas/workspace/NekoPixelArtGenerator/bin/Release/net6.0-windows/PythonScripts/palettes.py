#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调色板管理脚本
提供各种预设调色板和颜色处理功能
"""

import json
import sys
from typing import List, Tuple, Dict

def get_available_palettes() -> Dict[str, str]:
    """获取所有可用的调色板"""
    palettes = {
        'default': '默认调色板',
        'original': '原始颜色',
        'gameboy': 'Game Boy风格',
        'nes': 'NES游戏风格',
        'c64': 'Commodore 64风格',
        'amiga': 'Amiga风格',
        'atari': 'Atari 2600风格',
        'monochrome': '单色',
        'sepia': '怀旧棕褐色',
        'vaporwave': '蒸汽波风格',
        'neon': '霓虹色彩',
        'pastel': '柔和色彩',
        'earth': '大地色调',
        'ocean': '海洋色调',
        'sunset': '日落色调',
        'forest': '森林色调',
        'desert': '沙漠色调',
        'winter': '冬季色调',
        'spring': '春季色调',
        'autumn': '秋季色调'
    }
    return palettes

def get_palette_colors(palette_name: str, color_count: int = 256) -> List[Tuple[int, int, int]]:
    """获取指定调色板的颜色列表"""
    palettes = {
        'default': [
            (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
            (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)
        ],
        
        'gameboy': [
            (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
        ],
        
        'nes': [
            (84, 84, 84), (0, 30, 116), (8, 16, 144), (48, 0, 136),
            (68, 0, 100), (92, 0, 48), (136, 0, 0), (120, 16, 0),
            (104, 40, 0), (88, 48, 0), (64, 64, 0), (0, 120, 0),
            (8, 104, 0), (0, 88, 0), (0, 64, 88), (0, 0, 0)
        ],
        
        'c64': [
            (0, 0, 0), (255, 255, 255), (136, 0, 0), (170, 255, 238),
            (204, 68, 204), (0, 204, 85), (170, 68, 0), (102, 102, 0),
            (238, 119, 119), (221, 102, 0), (238, 170, 51), (0, 136, 0),
            (170, 170, 170), (85, 85, 85), (119, 119, 255), (85, 85, 85)
        ],
        
        'amiga': [
            (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
            (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
            (255, 128, 0), (255, 0, 128), (128, 255, 0), (0, 255, 128),
            (128, 0, 255), (0, 128, 255), (192, 192, 192), (128, 128, 128)
        ],
        
        'atari': [
            (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
            (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
            (128, 128, 128), (255, 128, 128), (128, 255, 128), (128, 128, 255)
        ],
        
        'monochrome': [
            (0, 0, 0), (255, 255, 255)
        ],
        
        'sepia': [
            (62, 39, 35), (147, 104, 67), (211, 161, 116),
            (241, 217, 169), (255, 245, 208), (255, 255, 255)
        ],
        
        'vaporwave': [
            (255, 105, 180), (255, 20, 147), (138, 43, 226), (75, 0, 130),
            (0, 191, 255), (135, 206, 250), (255, 255, 255), (192, 192, 192),
            (255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 0)
        ],
        
        'neon': [
            (255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 0),
            (0, 255, 0), (0, 0, 255), (255, 255, 255), (255, 165, 0)
        ],
        
        'pastel': [
            (255, 182, 193), (255, 218, 185), (255, 255, 186), (186, 255, 201),
            (186, 225, 255), (255, 186, 255), (255, 229, 229), (229, 229, 255)
        ],
        
        'earth': [
            (139, 69, 19), (160, 82, 45), (205, 133, 63), (222, 184, 135),
            (245, 222, 179), (210, 180, 140), (188, 143, 143), (165, 42, 42)
        ],
        
        'ocean': [
            (0, 0, 139), (0, 0, 255), (30, 144, 255), (64, 224, 208),
            (127, 255, 212), (173, 216, 230), (240, 248, 255), (0, 191, 255)
        ],
        
        'sunset': [
            (255, 69, 0), (255, 99, 71), (255, 140, 0), (255, 165, 0),
            (255, 215, 0), (255, 255, 0), (255, 182, 193), (255, 192, 203)
        ],
        
        'forest': [
            (0, 100, 0), (34, 139, 34), (50, 205, 50), (60, 179, 113),
            (107, 142, 35), (124, 252, 0), (173, 255, 47), (240, 255, 240)
        ],
        
        'desert': [
            (210, 180, 140), (222, 184, 135), (245, 222, 179), (250, 240, 230),
            (255, 228, 196), (255, 239, 213), (255, 248, 220), (255, 250, 250)
        ],
        
        'winter': [
            (176, 224, 230), (173, 216, 230), (240, 248, 255), (245, 255, 250),
            (248, 248, 255), (250, 250, 250), (255, 255, 255), (192, 192, 192)
        ],
        
        'spring': [
            (0, 255, 127), (50, 205, 50), (60, 179, 113), (107, 142, 35),
            (173, 255, 47), (255, 182, 193), (255, 192, 203), (255, 218, 185)
        ],
        
        'autumn': [
            (255, 69, 0), (255, 99, 71), (255, 140, 0), (255, 165, 0),
            (205, 133, 63), (210, 180, 140), (139, 69, 19), (160, 82, 45)
        ]
    }
    
    if palette_name not in palettes:
        return []
    
    colors = palettes[palette_name]
    
    # 如果颜色数量超过需要的，进行均匀采样
    if len(colors) > color_count:
        step = len(colors) / color_count
        colors = [colors[int(i * step)] for i in range(color_count)]
    
    # 如果颜色数量不足，进行插值补充
    elif len(colors) < color_count:
        colors = interpolate_colors(colors, color_count)
    
    return colors

def interpolate_colors(colors, target_count):
    """通过插值增加颜色数量"""
    if len(colors) >= target_count:
        return colors[:target_count]
    
    result = []
    for i in range(target_count):
        # 计算在原始颜色列表中的位置
        position = i * (len(colors) - 1) / (target_count - 1)
        
        if position >= len(colors) - 1:
            result.append(colors[-1])
        else:
            # 线性插值
            index = int(position)
            t = position - index
            
            if index + 1 < len(colors):
                color1 = colors[index]
                color2 = colors[index + 1]
                
                interpolated = tuple(
                    int(color1[j] + t * (color2[j] - color1[j]))
                    for j in range(3)
                )
                result.append(interpolated)
            else:
                result.append(colors[index])
    
    return result

def get_algorithms():
    """获取可用的处理算法"""
    algorithms = {
        'basic': '基础像素化',
        'average': '平均值采样',
        'median': '中值滤波',
        'adaptive': '自适应采样',
        'vector': '矢量化',
        'smooth': '平滑处理'
    }
    return algorithms

def main():
    """主函数 - 处理命令行参数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--list-palettes':
            palettes = get_available_palettes()
            print(json.dumps(palettes, ensure_ascii=False, indent=2))
            
        elif command == '--list-algorithms':
            algorithms = get_algorithms()
            print(json.dumps(algorithms, ensure_ascii=False, indent=2))
            
        elif command == '--get-palette-colors':
            if len(sys.argv) > 2:
                palette_name = sys.argv[2]
                color_count = int(sys.argv[3]) if len(sys.argv) > 3 else 256
                colors = get_palette_colors(palette_name, color_count)
                print(json.dumps(colors, ensure_ascii=False, indent=2))
            else:
                print("Usage: palettes.py --get-palette-colors <palette_name> [color_count]")
                sys.exit(1)
                
        else:
            print("Unknown command")
            sys.exit(1)
    else:
        # 默认显示可用调色板
        palettes = get_available_palettes()
        print(json.dumps(palettes, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()