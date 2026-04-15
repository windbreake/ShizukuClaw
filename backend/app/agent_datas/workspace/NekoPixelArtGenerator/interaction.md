# 像素画生成工具 (.NET前端) - 交互设计

## 核心功能交互

### 1. 图片加载与显示
- **文件选择对话框**: 标准的Windows文件选择器，支持多种图片格式
- **拖拽加载**: 支持从文件管理器拖拽图片到应用窗口
- **图片预览**: 在左侧显示原始图片，右侧显示处理后的像素画预览
- **缩放和平移**: 鼠标滚轮缩放，拖拽平移查看图片细节

### 2. 像素画参数控制面板
- **像素大小滑块**: 实时调整像素块大小 (4-64px)，显示数值标签
- **颜色数量控制**: 滑块控制调色板颜色数量 (2-256色)，带实时数值显示
- **调色板选择器**: 下拉菜单选择预设调色板 (复古游戏、现代艺术、单色等)
- **算法选择**: 单选按钮组选择不同的像素化算法
- **实时预览**: 参数调整时自动更新右侧预览图像

### 3. 高级设置选项卡
- **抖动效果**: CheckBox控制是否启用颜色抖动
- **边缘平滑**: Slider控制像素边缘的平滑程度
- **对比度调整**: Slider调整图像对比度
- **亮度调整**: Slider实时亮度控制
- **饱和度调整**: Slider控制颜色饱和度

### 4. 工具栏功能
- **打开文件**: 标准工具栏按钮
- **保存结果**: 保存处理后的像素画图片
- **重置参数**: 一键重置所有处理参数
- **批量处理**: 打开批量处理窗口
- **设置**: 应用配置对话框

### 5. 状态栏显示
- **图片信息**: 显示当前图片的尺寸、格式等信息
- **处理状态**: 显示"就绪"、"处理中"、"完成"等状态
- **进度条**: 处理过程中的进度显示

## 用户操作流程

1. **启动应用**: 显示空界面和操作提示
2. **加载图片**: 通过文件对话框或拖拽加载图片
3. **参数调整**: 实时调整各种参数并查看预览效果
4. **精细调优**: 使用高级选项进行细节调整
5. **保存结果**: 选择输出格式和质量，保存处理后的图片

## 批量处理功能

### 批量处理窗口
- **多文件选择**: 支持选择多个图片文件
- **参数同步**: 将主界面的参数应用到所有文件
- **处理队列**: 显示待处理的文件列表
- **进度监控**: 每个文件的处理进度条
- **结果管理**: 批量保存或单独处理

## 后端集成接口设计

### Python后端调用方案
- **进程调用**: 使用Process类调用Python脚本
- **参数传递**: 通过命令行参数传递处理参数
- **文件交换**: 通过临时文件交换图片数据
- **进度通信**: 使用标准输出获取处理进度
- **错误处理**: 捕获Python脚本的错误信息

### API接口设计
```csharp
public interface IPixelArtService
{
    Task<Bitmap> ProcessImageAsync(Bitmap source, PixelArtOptions options);
    Task<Bitmap[]> BatchProcessAsync(Bitmap[] sources, PixelArtOptions options);
    Task<string[]> GetAvailablePalettesAsync();
    Task<string[]> GetAvailableAlgorithmsAsync();
}
```

### 数据模型
```csharp
public class PixelArtOptions
{
    public int PixelSize { get; set; }
    public int ColorCount { get; set; }
    public string Palette { get; set; }
    public string Algorithm { get; set; }
    public bool EnableDithering { get; set; }
    public double EdgeSmoothing { get; set; }
    public double Contrast { get; set; }
    public double Brightness { get; set; }
    public double Saturation { get; set; }
}
```

## 技术特性

### 性能优化
- **异步处理**: 使用async/await避免界面卡顿
- **缓存机制**: 缓存处理结果，避免重复计算
- **内存管理**: 及时释放大图片占用的内存
- **进度反馈**: 实时显示处理进度

### 用户体验
- **快捷键支持**: 支持Ctrl+O打开文件，Ctrl+S保存等快捷键
- **撤销重做**: 支持参数调整的撤销重做功能
- **预设管理**: 保存和加载常用的参数预设
- **最近文件**: 显示最近处理的文件列表