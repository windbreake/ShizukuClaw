# Neko Pixel Art Generator ——本地部署的像素画生成工具
[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=300&size=24&pause=1000&color=F750EE&vCenter=true&random=true&width=435&lines=awa~)](https://git.io/typing-svg)


一个.NET桌面应用程序，用于将普通图片转换为精美的像素画效果。该工具采用现代WPF界面设计，结合Python后端处理引擎，提供强大的像素画生成功能。
## 特点

- 采用Python的高性能处理引擎，基于NumPy和Numba实现
- 使用SLIC超像素算法，提供更自然的像素化效果
- 拥有多种抖动算法（Floyd-Steinberg、Atkinson等）
- 可选的边缘轮廓增强效果
- 可选的像素网格显示功能
- 具备颜色量化算法，提高处理速度和质量
- 优秀的图像处理效率
- 使用管道模式，通过内存传输图像数据减少磁盘I/O

## 功能特性

### 核心功能
- **实时预览** - 左侧显示原图，右侧实时显示像素画效果
- **多种像素化算法** - 支持基础、平均值、中值滤波、SLIC超像素等多种算法
- **丰富的调色板** - 内置20+种预设调色板（Game Boy、NES、Commodore 64等）
- **高级参数控制** - 像素大小、颜色数量、抖动效果、边缘平滑等
- **基础调整** - 亮度、对比度、饱和度实时调整
- **边缘轮廓** - 可选的边缘轮廓增强效果
- **网格显示** - 可视化像素网格

### 专业工具
- **批量处理** - 支持多个图片同时处理
- **预设管理** - 保存和加载常用的参数配置
- **多种格式支持** - JPG、PNG、BMP、GIF等主流图片格式
- **高质量输出** - 支持多种输出格式和质量设置

### 技术特性
- **异步处理** - 不阻塞UI界面，流畅的用户体验
- **进度显示** - 实时显示处理进度和状态
- **错误处理** - 完善的错误捕获和用户提示
- **内存优化** - 高效处理大尺寸图片
- **高性能处理引擎** - 基于NumPy和Numba的高性能图像处理算法
- **多种抖动算法** - 支持Floyd-Steinberg和Atkinson等多种抖动算法
- **卡通效果** - 可选的边缘增强卡通化效果
- **管道传输** - 通过内存管道传输图像数据，减少磁盘I/O

## 系统要求

### 运行环境
- **操作系统**: Windows 10/11 (64位)
- **.NET运行时**: .NET 6.0 或更高版本
- **Python环境**: Python 3.8+ (推荐3.9-3.11)
- **内存要求**: 最少4GB RAM，推荐8GB以上
- **存储空间**: 至少500MB可用空间

### Python依赖
```
Pillow>=9.0.0      # 图像处理库
numpy>=1.21.0      # 数值计算库
scikit-learn>=1.0.0 # 机器学习库
scipy>=1.7.0       # 科学计算库
numba>=0.56.0      # 性能加速库
```

## 安装指南

### 方法一：预编译包安装
1. 从 [Releases](https://github.com/windbreake/NekoPixelArtGenerator/releases) 页面下载最新版本
2. 解压到任意目录
3. 运行 `PixelArtGenerator.exe`

### 方法二：源码编译
1. 克隆代码仓库
```bash
git clone https://github.com/windbreake/NekoPixelArtGenerator.git
cd PixelArtGenerator
```

2. 安装Python依赖
```bash
cd PythonScripts
pip install -r requirements.txt
cd ..
```

3. 编译项目
```bash
# 使用Visual Studio 2022或更高版本
# 或使用.NET CLI
dotnet build -c Release
```

4. 运行程序
```bash
dotnet run -c Release
```

## 使用指南

### 基本操作
1. **打开图片** - 点击"文件"→"打开图片"或拖拽图片到界面
2. **调整参数** - 使用右侧参数面板调整效果
3. **实时预览** - 参数调整时自动更新预览效果
4. **保存结果** - 点击"文件"→"保存结果"保存像素画图片

### 参数说明

#### 基本参数
- **像素大小 (4-64px)** - 控制像素块的尺寸，数值越大像素感越强
- **颜色数量 (2-256色)** - 控制调色板中的颜色数量
- **调色板** - 选择不同的色彩风格（复古、现代、单色等）
- **处理算法** - 选择不同的像素化算法

#### 高级选项
- **抖动效果** - 启用颜色抖动，使过渡更自然
- **抖动强度 (0-1)** - 控制抖动的强度
- **边缘平滑 (0-1)** - 控制像素边缘的平滑程度
- **对比度 (0.1-3.0)** - 调整图像对比度
- **亮度 (0.1-2.0)** - 调整图像亮度
- **饱和度 (0-2.0)** - 调整颜色饱和度
- **卡通效果** - 启用边缘增强的卡通化效果
- **边缘轮廓** - 启用边缘轮廓增强效果
- **轮廓粗细** - 控制边缘轮廓的粗细程度
- **轮廓颜色** - 自定义边缘轮廓的颜色
- **网格显示** - 显示像素网格辅助线

### 快捷键
- `Ctrl+O` - 打开图片
- `Ctrl+S` - 保存结果
- `Ctrl+Z` - 撤销
- `Ctrl+Y` - 重做
- `Ctrl+R` - 重置参数
- `Space` - 拖拽查看图片（在图片区域）
- `Ctrl+滚轮` - 缩放图片

## 后端集成

### Python脚本调用
应用程序通过进程调用方式与Python后端交互：

```csharp
// 服务接口调用示例
var service = new PythonPixelArtService(pythonPath, scriptsPath);
var result = await service.ProcessImageAsync(bitmap, options);
```

### API设计
- **同步处理** - 通过临时文件交换数据
- **进度报告** - 通过JSON文件实时报告处理进度
- **错误处理** - 通过标准错误流传递错误信息
- **参数传递** - 通过命令行参数传递处理参数

### 自定义算法扩展
要添加新的处理算法：

1. 在 `pixelate.py` 中添加新的算法函数
2. 在 `GetAvailableAlgorithmsAsync()` 方法中添加算法名称
3. 更新UI界面的算法选择列表

## 高性能处理引擎

### 核心算法优化
我们采用了基于NumPy和Numba的实现方案，其具有以下优势：

1. **SLIC超像素算法** - 使用超像素分割技术，生成更自然的像素化效果
2. **K-means颜色量化** - 使用scikit-learn的MiniBatchKMeans算法进行高效颜色量化
3. **多种抖动算法** - 支持Floyd-Steinberg和Atkinson等多种抖动算法
4. **调色板映射** - 使用查找表优化颜色映射过程
5. **卡通效果** - 边缘检测叠加增强效果
6. **Numba加速** - 使用Numba JIT编译器大幅提升数值计算性能

### 处理管道
处理管道按以下顺序执行：
1. 像素化处理
2. 颜色量化
3. 调色板映射
4. 抖动处理
5. 卡通效果（可选）

## 开发指南

### 项目结构
```
PixelArtGenerator/
├── Models/                 # 数据模型
│   ├── PixelArtOptions.cs    # 处理参数模型
│   ├── ProcessingResult.cs   # 处理结果模型
│   └── ImageInfo.cs         # 图片信息模型
├── Services/               # 业务服务
│   ├── IPythonPixelArtService.cs  # Python服务接口
│   ├── PythonPixelArtService.cs   # Python服务实现
│   └── FileService.cs       # 文件服务
├── Controls/               # 自定义控件
├── Converters/             # 值转换器
├── Resources/              # 资源文件
│   ├── Icons/             # 图标文件
│   └── Styles/            # 样式文件
└── PythonScripts/          # Python后端脚本
    ├── pixelate.py         # 主要处理脚本
    ├── processors.py       # 高性能处理模块
    ├── palettes.py         # 调色板管理
    └── requirements.txt    # Python依赖
```

### 技术栈
- **前端框架**: WPF (.NET 6)
- **UI技术**: XAML + C#
- **图像处理**: System.Drawing.Common
- **后端引擎**: Python 3.8+
- **图像库**: Pillow (PIL)
- **数值计算**: NumPy
- **机器学习**: scikit-learn
- **性能加速**: Numba
- **科学计算**: SciPy

### 构建配置
项目支持多种构建配置：
- Debug/Release 模式
- x86/x64/AnyCPU 平台
- 单文件发布
- 自包含部署

## 故障排除

### 常见问题

#### 1. Python环境未找到
**问题**: 应用程序启动时提示Python环境错误
**解决**: 
- 确保已安装Python 3.8+
- 检查系统PATH环境变量
- 在应用设置中指定Python路径

#### 2. 图片处理失败
**问题**: 处理图片时出现错误
**解决**:
- 检查图片格式是否支持
- 确认图片未损坏
- 查看日志文件获取详细信息

#### 3. 性能问题
**问题**: 处理大图时卡顿或内存不足
**解决**:
- 增加系统内存
- 调整处理参数（减小像素大小）
- 使用批量处理功能

#### 4. 依赖安装失败
**问题**: Python依赖安装失败
**解决**:
```bash
pip install -r PythonScripts/requirements.txt --upgrade
```

如果遇到网络问题，可以使用国内镜像源：
```bash
pip install -r PythonScripts/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 更新日志

### v2.1.0 (2025-11-18)
- 新增高性能处理引擎，基于NumPy和Numba实现
- 添加SLIC超像素算法，提供更自然的像素化效果
- 添加多种抖动算法（Floyd-Steinberg、Atkinson等）
- 添加可选的边缘轮廓增强效果
- 添加可选的像素网格显示功能
- 优化颜色量化算法，提高处理速度和质量
- 改进整体处理性能，大幅提升大图像处理效率
- 添加管道模式，通过内存传输图像数据减少磁盘I/O

### v2.0.0 (2025-11-16)
- 新增高性能处理引擎
- 添加拜耳抖动算法
- 添加卡通效果选项
- 优化颜色量化算法
- 提升整体处理性能

### v1.2.0 (2024-05-20)
- 添加批量处理功能
- 改进UI交互体验
- 修复部分图像处理bug

### v1.1.0 (2024-03-15)
- 添加调色板预览功能
- 增加更多预设调色板
- 优化内存使用

### v1.0.0 (2024-01-10)
- 初始版本发布
- 基础像素画生成功能
- 支持多种图像格式

## 许可证

本项目采用MIT许可证，详情请查看 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请通过以下方式联系我们：
- 提交 [GitHub Issues](https://github.com/windbreake/NekoPixelArtGenerator/issues)
- 发送邮件至 windbreak339@gmail.com
