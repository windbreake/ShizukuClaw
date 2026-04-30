# 像素画生成工具 (.NET WPF) - 项目大纲

## 项目结构

### 解决方案文件
- **PixelArtGenerator.sln** - Visual Studio解决方案文件
- **PixelArtGenerator.csproj** - WPF应用程序项目文件

### 主要文件夹结构
```
PixelArtGenerator/
├── App.xaml              # 应用程序入口和全局样式
├── App.xaml.cs           # 应用程序逻辑
├── MainWindow.xaml       # 主窗口界面
├── MainWindow.xaml.cs    # 主窗口逻辑
├── Models/               # 数据模型
│   ├── PixelArtOptions.cs
│   ├── ProcessingResult.cs
│   └── ImageInfo.cs
├── Services/             # 业务服务
│   ├── IPixelArtService.cs
│   ├── PythonPixelArtService.cs
│   └── FileService.cs
├── Controls/             # 自定义控件
│   ├── ImageViewer.xaml
│   ├── ParameterSlider.xaml
│   └── ProcessingProgress.xaml
├── Converters/           # 值转换器
│   ├── BooleanToVisibilityConverter.cs
│   └── BytesToImageConverter.cs
├── Resources/            # 资源文件
│   ├── Icons/            # 图标文件
│   ├── Styles/           # 样式文件
│   └── Templates/        # 控件模板
└── PythonScripts/        # Python后端脚本
    ├── pixelate.py       # 主要像素化处理
    ├── palettes.py       # 调色板处理
    └── utils.py          # 工具函数
```

## 核心文件功能详述

### 主界面文件
1. **MainWindow.xaml** - 主窗口界面设计
   - 菜单栏 (文件、编辑、视图、工具、帮助)
   - 工具栏 (打开、保存、处理、重置)
   - 主工作区 (左:原图, 右:预览)
   - 参数控制面板 (滑块、下拉框、复选框)
   - 状态栏 (图片信息、处理状态)

2. **MainWindow.xaml.cs** - 主窗口业务逻辑
   - 文件加载和保存
   - 参数控制事件处理
   - 图像处理调用
   - 界面状态管理

### 数据模型
3. **PixelArtOptions.cs** - 像素画处理参数
   ```csharp
   public class PixelArtOptions
   {
       public int PixelSize { get; set; }      // 像素大小 (4-64px)
       public int ColorCount { get; set; }     // 颜色数量 (2-256色)
       public string Palette { get; set; }     // 调色板选择
       public string Algorithm { get; set; }   // 处理算法
       public bool EnableDithering { get; set; } // 抖动效果
       public double EdgeSmoothing { get; set; } // 边缘平滑
       public double Contrast { get; set; }    // 对比度
       public double Brightness { get; set; }  // 亮度
       public double Saturation { get; set; }  // 饱和度
   }
   ```

4. **ProcessingResult.cs** - 处理结果
   ```csharp
   public class ProcessingResult
   {
       public Bitmap ProcessedImage { get; set; }
       public TimeSpan ProcessingTime { get; set; }
       public string Status { get; set; }
       public string ErrorMessage { get; set; }
   }
   ```

### 服务层
5. **IPixelArtService.cs** - 像素画服务接口
   ```csharp
   public interface IPixelArtService
   {
       Task<Bitmap> ProcessImageAsync(Bitmap source, PixelArtOptions options);
       Task<ProcessingResult> ProcessImageWithResultAsync(Bitmap source, PixelArtOptions options);
       Task<string[]> GetAvailablePalettesAsync();
       Task<string[]> GetAvailableAlgorithmsAsync();
   }
   ```

6. **PythonPixelArtService.cs** - Python后端调用实现
   - 使用Process类调用Python脚本
   - 参数传递和结果接收
   - 错误处理和日志记录
   - 进度报告机制

### 自定义控件
7. **ImageViewer.xaml** - 图片查看控件
   - 缩放和平移功能
   - 网格叠加显示
   - 拖拽文件支持
   - 放大镜功能

8. **ParameterSlider.xaml** - 参数滑块控件
   - 带数值标签的滑块
   - 最小/最大值显示
   - 实时数值更新
   - 键盘输入支持

### Python后端脚本
9. **pixelate.py** - 主要像素化处理脚本
   ```python
   def pixelate_image(image_path, output_path, pixel_size, color_count, palette, algorithm, **kwargs)
   def apply_dithering(image, color_count)
   def reduce_colors(image, target_colors)
   def apply_edge_smoothing(image, smooth_factor)
   ```

10. **palettes.py** - 调色板处理
    ```python
    def load_palette(palette_name)
    def create_custom_palette(image, color_count)
    def apply_palette(image, palette)
    ```

## 技术实现要点

### WPF特性使用
- **MVVM模式**: 使用ViewModel分离界面和逻辑
- **数据绑定**: 参数控件与ViewModel的双向绑定
- **命令模式**: 使用ICommand处理按钮点击
- **异步编程**: 使用async/await处理长时间操作
- **依赖注入**: 服务层的依赖注入管理

### 图像处理流程
1. **加载图片**: 支持多种格式 (JPG, PNG, BMP, GIF)
2. **参数验证**: 验证参数范围和有效性
3. **临时文件**: 创建临时文件传递数据
4. **Python调用**: 启动Python进程并传递参数
5. **结果处理**: 读取处理结果并显示
6. **资源清理**: 清理临时文件和资源

### 错误处理机制
- **文件错误**: 图片格式不支持、文件损坏等
- **参数错误**: 参数超出有效范围
- **Python错误**: Python脚本执行错误
- **内存错误**: 处理大图时的内存不足
- **超时处理**: 处理超时的超时机制

### 性能优化
- **异步处理**: 避免界面卡顿
- **内存管理**: 及时释放大图片内存
- **缓存机制**: 缓存处理结果
- **进度反馈**: 实时显示处理进度

## 部署和打包

### 发布配置
- **单文件发布**: .NET 5+的单文件发布
- **自包含部署**: 包含.NET运行时
- **Python依赖**: 打包Python环境和依赖库
- **图标资源**: 应用程序图标和UI图标

### 安装程序
- **MSI安装包**: 标准的Windows安装程序
- **依赖检查**: 自动检查和安装必要依赖
- **快捷方式**: 创建桌面和开始菜单快捷方式
- **文件关联**: 关联图片文件类型