using System;
using System.Drawing;
using System.Threading.Tasks;
using PixelArtGenerator.Models;

namespace PixelArtGenerator.Services
{
    public interface IPythonPixelArtService
    {
        /// <summary>
        /// 处理单个图片并返回处理结果
        /// </summary>
        /// <param name="source">源图片</param>
        /// <param name="options">处理选项</param>
        /// <param name="progress">进度报告</param>
        /// <returns>处理后的图片</returns>
        Task<Bitmap> ProcessImageAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null);
        
        /// <summary>
        /// 处理单个图片并返回详细的处理结果
        /// </summary>
        /// <param name="source">源图片</param>
        /// <param name="options">处理选项</param>
        /// <param name="progress">进度报告</param>
        /// <returns>处理结果</returns>
        Task<ProcessingResult> ProcessImageWithResultAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null);
        
        /// <summary>
        /// 通过管道方式处理单个图片并返回详细的处理结果
        /// </summary>
        /// <param name="source">源图片</param>
        /// <param name="options">处理选项</param>
        /// <param name="progress">进度报告</param>
        /// <returns>处理结果</returns>
        Task<ProcessingResult> ProcessImageViaPipeAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null);
        
        /// <summary>
        /// 批量处理多个图片
        /// </summary>
        /// <param name="sources">源图片数组</param>
        /// <param name="options">处理选项</param>
        /// <param name="progress">进度报告</param>
        /// <returns>处理后的图片数组</returns>
        Task<Bitmap[]> BatchProcessAsync(Bitmap[] sources, PixelArtOptions options, IProgress<int> progress = null);
        
        /// <summary>
        /// 获取可用的调色板列表
        /// </summary>
        /// <returns>调色板名称数组</returns>
        Task<string[]> GetAvailablePalettesAsync();
        
        /// <summary>
        /// 获取可用的处理算法列表
        /// </summary>
        /// <returns>算法名称数组</returns>
        Task<string[]> GetAvailableAlgorithmsAsync();
        
        /// <summary>
        /// 获取指定调色板的颜色信息
        /// </summary>
        /// <param name="paletteName">调色板名称</param>
        /// <param name="colorCount">颜色数量</param>
        /// <returns>RGB颜色值数组</returns>
        Task<System.Drawing.Color[]> GetPaletteColorsAsync(string paletteName, int colorCount = 256);
        
        /// <summary>
        /// 检查Python环境是否可用
        /// </summary>
        /// <returns>是否可用的布尔值</returns>
        Task<bool> CheckPythonEnvironmentAsync();
        
        /// <summary>
        /// 安装或更新Python依赖
        /// </summary>
        /// <param name="progress">进度报告</param>
        /// <returns>是否成功的布尔值</returns>
        Task<bool> InstallDependenciesAsync(IProgress<string> progress = null);
    }
}