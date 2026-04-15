using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using PixelArtGenerator.Models;

namespace PixelArtGenerator.Services
{
    public class PythonPixelArtService : IPythonPixelArtService
    {
        private readonly string _pythonPath;
        private readonly string _scriptsPath;
        private readonly string _tempDirectory;
        private readonly string _logPath;
        private static readonly object _lockObject = new object();

        public PythonPixelArtService(string pythonPath, string scriptsPath)
        {
            _pythonPath = pythonPath ?? throw new ArgumentNullException(nameof(pythonPath));
            _scriptsPath = scriptsPath ?? throw new ArgumentNullException(nameof(scriptsPath));
            _tempDirectory = Path.Combine(Path.GetTempPath(), "PixelArtGenerator");
            _logPath = Path.Combine(_tempDirectory, "processing.log");
            
            // 确保临时目录存在
            Directory.CreateDirectory(_tempDirectory);
        }

        public async Task<Bitmap> ProcessImageAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null)
        {
            var result = await ProcessImageWithResultAsync(source, options, progress);
            return result.ProcessedImage;
        }

        public async Task<ProcessingResult> ProcessImageWithResultAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null)
        {
            if (source == null)
                throw new ArgumentNullException(nameof(source));
            
            if (options == null)
                throw new ArgumentNullException(nameof(options));

            var startTime = DateTime.Now;
            
            try
            {
                LogMessage($"开始处理图片: {options.PixelSize}px, {options.ColorCount} colors");
                
                // 创建临时文件
                var tempFiles = CreateTempFiles();
                
                try
                {
                    // 保存源图片
                    SaveBitmapToFile(source, tempFiles.InputPath);
                    LogMessage($"源图片已保存到: {tempFiles.InputPath}");
                    
                    // 构建命令行参数
                    var arguments = BuildCommandArguments(options, tempFiles);
                    LogMessage($"执行命令: {_pythonPath} \"{Path.Combine(_scriptsPath, "pixelate.py")}\" {arguments}");
                    
                    // 执行Python脚本
                    var result = await ExecutePythonScriptAsync(
                        Path.Combine(_scriptsPath, "pixelate.py"), 
                        arguments, 
                        tempFiles, 
                        progress);
                    
                    if (result.IsSuccess && File.Exists(tempFiles.OutputPath))
                    {
                        LogMessage($"处理成功，输出文件: {tempFiles.OutputPath}");
                        
                        // 加载处理后的图片
                        var processedImage = LoadBitmapFromFile(tempFiles.OutputPath);
                        
                        var processingTime = DateTime.Now - startTime;
                        LogMessage($"处理完成，耗时: {processingTime.TotalSeconds:F2}秒");
                        
                        return ProcessingResult.Success(
                            processedImage, 
                            processingTime);
                    }
                    else
                    {
                        LogMessage($"处理失败: {result.ErrorMessage}");
                        return ProcessingResult.Failure(result.ErrorMessage);
                    }
                }
                finally
                {
                    // 清理临时文件
                    CleanupTempFiles(tempFiles);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"处理异常: {ex}");
                return ProcessingResult.Failure($"处理失败: {ex.Message}");
            }
        }

        // 新增的方法：通过内存管道处理图像
        public async Task<ProcessingResult> ProcessImageViaPipeAsync(Bitmap source, PixelArtOptions options, IProgress<int> progress = null)
        {
            if (source == null)
                throw new ArgumentNullException(nameof(source));
            
            if (options == null)
                throw new ArgumentNullException(nameof(options));

            var startTime = DateTime.Now;
            
            // 将Bitmap转换为字节数组
            byte[] imageData;
            using (var memoryStream = new MemoryStream())
            {
                source.Save(memoryStream, ImageFormat.Png);
                imageData = memoryStream.ToArray();
            }
            
            try
            {
                LogMessage($"开始通过管道处理图片: {options.PixelSize}px, {options.ColorCount} colors");
                
                // 构建命令行参数，使用管道模式
                var arguments = BuildPipeCommandArguments(options);
                LogMessage($"执行管道命令: {_pythonPath} \"{Path.Combine(_scriptsPath, "pixelate.py")}\" {arguments}");
                
                // 执行Python脚本并通过管道传输数据
                var result = await ExecutePythonScriptWithPipesAsync(
                    Path.Combine(_scriptsPath, "pixelate.py"), 
                    arguments, 
                    imageData,
                    progress);
                
                if (result.IsSuccess && result.OutputData != null)
                {
                    LogMessage($"管道处理成功");
                    
                    // 从输出数据创建Bitmap
                    using (var memoryStream = new MemoryStream(result.OutputData))
                    {
                        var processedImage = new Bitmap(memoryStream);
                        
                        var processingTime = DateTime.Now - startTime;
                        LogMessage($"管道处理完成，耗时: {processingTime.TotalSeconds:F2}秒");
                        
                        return ProcessingResult.Success(
                            processedImage, 
                            processingTime);
                    }
                }
                else
                {
                    LogMessage($"管道处理失败: {result.ErrorMessage}");
                    return ProcessingResult.Failure(result.ErrorMessage);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"管道处理异常: {ex}");
                return ProcessingResult.Failure($"处理失败: {ex.Message}");
            }
        }

        public async Task<Bitmap[]> BatchProcessAsync(Bitmap[] sources, PixelArtOptions options, IProgress<int> progress = null)
        {
            if (sources == null || sources.Length == 0)
                throw new ArgumentException("源图片数组不能为空");

            var results = new Bitmap[sources.Length];
            var totalProgress = 0;
            
            for (int i = 0; i < sources.Length; i++)
            {
                var itemProgress = new Progress<int>(value =>
                {
                    var overallProgress = (i * 100 + value) / sources.Length;
                    progress?.Report(overallProgress);
                });
                
                results[i] = await ProcessImageAsync(sources[i], options, itemProgress);
            }
            
            return results;
        }

        public async Task<string[]> GetAvailablePalettesAsync()
        {
            try
            {
                var arguments = "--list-palettes";
                var result = await ExecutePythonScriptAsync(
                    Path.Combine(_scriptsPath, "palettes.py"), 
                    arguments, 
                    null, 
                    null);
                
                if (result.IsSuccess && !string.IsNullOrEmpty(result.Output))
                {
                    var palettes = JsonSerializer.Deserialize<Dictionary<string, string>>(result.Output);
                    return palettes.Keys.ToArray();
                }
                
                return new[] { "default" };
            }
            catch
            {
                return new[] { "default" };
            }
        }

        public async Task<string[]> GetAvailableAlgorithmsAsync()
        {
            // 算法列表在C#代码中定义，保持同步
            return new[]
            {
                "basic",
                "average", 
                "median",
                "adaptive",
                "vector",
                "smooth",
                "slic"
            };
        }

        public async Task<System.Drawing.Color[]> GetPaletteColorsAsync(string paletteName, int colorCount = 256)
        {
            try
            {
                var arguments = $"--get-palette-colors {paletteName} {colorCount}";
                var result = await ExecutePythonScriptAsync(
                    Path.Combine(_scriptsPath, "palettes.py"), 
                    arguments, 
                    null, 
                    null);
                
                if (result.IsSuccess && !string.IsNullOrEmpty(result.Output))
                {
                    var colors = JsonSerializer.Deserialize<List<List<int>>>(result.Output);
                    return colors.Select(c => System.Drawing.Color.FromArgb(c[0], c[1], c[2])).ToArray();
                }
                
                return new[] { System.Drawing.Color.Black, System.Drawing.Color.White };
            }
            catch
            {
                return new[] { System.Drawing.Color.Black, System.Drawing.Color.White };
            }
        }

        public async Task<bool> CheckPythonEnvironmentAsync()
        {
            try
            {
                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = _pythonPath,
                        Arguments = "--version",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    }
                };

                process.Start();
                await process.WaitForExitAsync();
                
                return process.ExitCode == 0;
            }
            catch
            {
                return false;
            }
        }

        public async Task<bool> InstallDependenciesAsync(IProgress<string> progress = null)
        {
            try
            {
                var requirementsPath = Path.Combine(_scriptsPath, "requirements.txt");
                
                if (!File.Exists(requirementsPath))
                {
                    progress?.Report("requirements.txt 文件未找到");
                    return false;
                }

                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = _pythonPath,
                        Arguments = $"-m pip install -r \"{requirementsPath}\"",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    }
                };

                process.OutputDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                        progress?.Report(e.Data);
                };

                process.ErrorDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                        progress?.Report($"ERROR: {e.Data}");
                };

                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                
                await process.WaitForExitAsync();
                
                return process.ExitCode == 0;
            }
            catch (Exception ex)
            {
                progress?.Report($"安装依赖失败: {ex.Message}");
                return false;
            }
        }

        #region 私有方法
        private TempFiles CreateTempFiles()
        {
            var guid = Guid.NewGuid().ToString("N");
            return new TempFiles
            {
                InputPath = Path.Combine(_tempDirectory, $"{guid}_input.png"),
                OutputPath = Path.Combine(_tempDirectory, $"{guid}_output.png"),
                ProgressPath = Path.Combine(_tempDirectory, $"{guid}_progress.json")
            };
        }

        private string BuildCommandArguments(PixelArtOptions options, TempFiles tempFiles)
        {
            var sb = new StringBuilder();
            sb.Append($"\"{tempFiles.InputPath}\" ");
            sb.Append($"--output \"{tempFiles.OutputPath}\" ");
            sb.Append($"--pixel-size {options.PixelSize} ");
            sb.Append($"--color-count {options.ColorCount} ");
            sb.Append($"--palette \"{options.Palette}\" ");
            sb.Append($"--algorithm \"{options.Algorithm}\" ");
            
            if (options.EnableDithering)
                sb.Append("--dithering ");
            
            sb.Append($"--edge-smoothing {options.EdgeSmoothing:F2} ");
            sb.Append($"--contrast {options.Contrast:F2} ");
            sb.Append($"--brightness {options.Brightness:F2} ");
            sb.Append($"--saturation {options.Saturation:F2} ");
            sb.Append($"--progress-file \"{tempFiles.ProgressPath}\" ");
            
            // 添加网格线选项
            if (options.ShowGrid)
                sb.Append("--show-grid ");
            
            // 添加边缘描边选项
            if (options.EnableEdgeOutline)
            {
                sb.Append("--edge-outline ");
                sb.Append($"--edge-outline-thickness {options.EdgeOutlineThickness} ");
                sb.Append($"--edge-outline-color {options.EdgeOutlineColorR},{options.EdgeOutlineColorG},{options.EdgeOutlineColorB} ");
            }
            
            return sb.ToString();
        }

        // 构建用于管道传输的命令行参数
        private string BuildPipeCommandArguments(PixelArtOptions options)
        {
            var sb = new StringBuilder();
            sb.Append("--pipe-mode ");  // 启用管道模式
            sb.Append($"--pixel-size {options.PixelSize} ");
            sb.Append($"--color-count {options.ColorCount} ");
            sb.Append($"--palette \"{options.Palette}\" ");
            sb.Append($"--algorithm \"{options.Algorithm}\" ");
            
            if (options.EnableDithering)
                sb.Append("--dithering ");
            
            sb.Append($"--edge-smoothing {options.EdgeSmoothing:F2} ");
            sb.Append($"--contrast {options.Contrast:F2} ");
            sb.Append($"--brightness {options.Brightness:F2} ");
            sb.Append($"--saturation {options.Saturation:F2} ");
            
            // 添加网格线选项
            if (options.ShowGrid)
                sb.Append("--show-grid ");
            
            // 添加边缘描边选项
            if (options.EnableEdgeOutline)
            {
                sb.Append("--edge-outline ");
                sb.Append($"--edge-outline-thickness {options.EdgeOutlineThickness} ");
                sb.Append($"--edge-outline-color {options.EdgeOutlineColorR},{options.EdgeOutlineColorG},{options.EdgeOutlineColorB} ");
            }
            
            return sb.ToString();
        }

        private async Task<(bool IsSuccess, string Output, string ErrorMessage)> ExecutePythonScriptAsync(
            string scriptPath, string arguments, TempFiles tempFiles, IProgress<int> progress)
        {
            var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = _pythonPath,
                    Arguments = $"\"{scriptPath}\" {arguments}",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    WorkingDirectory = _scriptsPath
                }
            };

            try
            {
                LogMessage($"启动进程: {_pythonPath} \"{scriptPath}\" {arguments}");
                
                // 检查Python路径是否存在
                if (!File.Exists(_pythonPath) && _pythonPath != "python")
                {
                    LogMessage($"Python路径不存在: {_pythonPath}，尝试使用系统PATH中的python");
                    process.StartInfo.FileName = "python";
                }
                
                try 
                {
                    process.Start();
                }
                catch (Exception startEx)
                {
                    LogMessage($"启动进程失败: {startEx.Message}");
                    // 如果使用指定路径失败，尝试使用系统PATH中的python
                    if (process.StartInfo.FileName != "python")
                    {
                        LogMessage("尝试使用系统PATH中的python");
                        process.StartInfo.FileName = "python";
                        process.Start();
                    }
                    else
                    {
                        throw; // 如果已经是"python"还失败，则抛出异常
                    }
                }
                
                // 监控进度（如果提供了进度文件）
                var progressTask = MonitorProgressAsync(tempFiles?.ProgressPath, progress);
                
                // 读取输出（使用超时机制避免死锁）
                var outputTask = process.StandardOutput.ReadToEndAsync();
                var errorTask = process.StandardError.ReadToEndAsync();
                
                // 等待进程完成，设置超时
                var processExitTask = process.WaitForExitAsync();
                var timeoutTask = Task.Delay(TimeSpan.FromMinutes(5)); // 5分钟超时
                var completedTask = await Task.WhenAny(processExitTask, timeoutTask);
                
                if (completedTask == timeoutTask)
                {
                    // 超时，杀死进程
                    try
                    {
                        process.Kill();
                    }
                    catch (Exception killEx)
                    {
                        LogMessage($"杀死超时进程失败: {killEx.Message}");
                    }
                    
                    return (false, null, "处理超时");
                }
                
                // 并行等待进度监控
                await Task.WhenAll(processExitTask, progressTask ?? Task.CompletedTask);
                
                var output = await outputTask;
                var error = await errorTask;
                
                LogMessage($"进程退出码: {process.ExitCode}");
                if (!string.IsNullOrEmpty(output))
                    LogMessage($"标准输出: {output}");
                if (!string.IsNullOrEmpty(error))
                    LogMessage($"错误输出: {error}");
                
                if (process.ExitCode == 0)
                {
                    return (true, output.Trim(), null);
                }
                else
                {
                    // 如果有错误输出，返回错误信息，否则返回通用错误
                    var errorMessage = !string.IsNullOrEmpty(error) ? error.Trim() : "处理失败，退出代码: " + process.ExitCode;
                    return (false, null, errorMessage);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"执行脚本异常: {ex}");
                return (false, null, ex.Message);
            }
            finally
            {
                process?.Dispose();
            }
        }

        // 通过管道执行Python脚本的新方法
        private async Task<(bool IsSuccess, byte[] OutputData, string ErrorMessage)> ExecutePythonScriptWithPipesAsync(
            string scriptPath, string arguments, byte[] inputData, IProgress<int> progress)
        {
            Process process = null;
            MemoryStream outputMemoryStream = null;
            
            try
            {
                process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = _pythonPath,
                        Arguments = $"\"{scriptPath}\" {arguments}",
                        UseShellExecute = false,
                        RedirectStandardInput = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true,
                        WorkingDirectory = _scriptsPath
                    }
                };

                LogMessage($"启动管道进程: {_pythonPath} \"{scriptPath}\" {arguments}");
                
                // 检查Python路径是否存在
                if (!File.Exists(_pythonPath) && _pythonPath != "python")
                {
                    LogMessage($"Python路径不存在: {_pythonPath}，尝试使用系统PATH中的python");
                    process.StartInfo.FileName = "python";
                }
                
                try 
                {
                    process.Start();
                }
                catch (Exception startEx)
                {
                    LogMessage($"启动进程失败: {startEx.Message}");
                    // 如果使用指定路径失败，尝试使用系统PATH中的python
                    if (process.StartInfo.FileName != "python")
                    {
                        LogMessage("尝试使用系统PATH中的python");
                        process.StartInfo.FileName = "python";
                        process.Start();
                    }
                    else
                    {
                        throw; // 如果已经是"python"还失败，则抛出异常
                    }
                }
                
                // 异步写入输入数据
                await process.StandardInput.BaseStream.WriteAsync(inputData, 0, inputData.Length);
                process.StandardInput.Close();
                
                // 读取输出数据
                outputMemoryStream = new MemoryStream();
                var outputDataTask = process.StandardOutput.BaseStream.CopyToAsync(outputMemoryStream);
                var errorTask = process.StandardError.ReadToEndAsync();
                
                // 等待进程完成，设置超时
                var processExitTask = process.WaitForExitAsync();
                var timeoutTask = Task.Delay(TimeSpan.FromMinutes(5)); // 5分钟超时
                var completedTask = await Task.WhenAny(processExitTask, timeoutTask);
                
                if (completedTask == timeoutTask)
                {
                    // 超时，杀死进程
                    try
                    {
                        process.Kill();
                    }
                    catch (Exception killEx)
                    {
                        LogMessage($"杀死超时进程失败: {killEx.Message}");
                    }
                    
                    return (false, null, "处理超时");
                }
                
                await outputDataTask; // 等待复制完成
                
                var error = await errorTask;
                
                LogMessage($"管道进程退出码: {process.ExitCode}");
                if (!string.IsNullOrEmpty(error))
                    LogMessage($"管道错误输出: {error}");
                
                if (process.ExitCode == 0)
                {
                    // 获取输出数据
                    var outputData = outputMemoryStream.ToArray();
                    return (true, outputData, null);
                }
                else
                {
                    // 如果有错误输出，返回错误信息，否则返回通用错误
                    var errorMessage = !string.IsNullOrEmpty(error) ? error.Trim() : "处理失败，退出代码: " + process.ExitCode;
                    return (false, null, errorMessage);
                }
            }
            catch (Exception ex)
            {
                LogMessage($"执行管道脚本异常: {ex}");
                return (false, null, ex.Message);
            }
            finally
            {
                // 确保资源被正确释放
                process?.Dispose();
                outputMemoryStream?.Dispose();
            }
        }

        private async Task MonitorProgressAsync(string progressFilePath, IProgress<int> progress)
        {
            if (string.IsNullOrEmpty(progressFilePath) || progress == null)
                return;

            // 添加超时机制，防止无限等待
            var timeout = DateTime.Now.AddMinutes(5); // 5分钟超时，给长时间处理更多时间
            var lastProgress = 0;
            var sameProgressStartTime = DateTime.Now;

            while (DateTime.Now < timeout)
            {
                try
                {
                    if (File.Exists(progressFilePath))
                    {
                        var json = await File.ReadAllTextAsync(progressFilePath);
                        if (!string.IsNullOrEmpty(json))
                        {
                            var progressData = JsonSerializer.Deserialize<ProgressData>(json);
                            progress.Report(progressData.Progress);
                            
                            // 检查进度是否停滞
                            if (progressData.Progress > lastProgress)
                            {
                                lastProgress = progressData.Progress;
                                sameProgressStartTime = DateTime.Now;
                            }
                            else if (DateTime.Now.Subtract(sameProgressStartTime).TotalSeconds > 30)
                            {
                                // 如果进度30秒内没有更新，退出循环
                                break;
                            }
                            
                            if (progressData.Progress >= 100)
                                break;
                        }
                    }
                }
                catch (Exception ex)
                {
                    // 忽略进度读取错误，但记录到日志中
                    LogMessage($"读取进度文件时出错: {ex.Message}");
                }
                
                // 检查是否应该退出
                if (DateTime.Now >= timeout)
                    break;
                
                await Task.Delay(500); // 减少检查频率，避免占用过多资源
            }
        }

        private void SaveBitmapToFile(Bitmap bitmap, string filePath)
        {
            lock (_lockObject)
            {
                bitmap.Save(filePath, ImageFormat.Png);
            }
        }

        private Bitmap LoadBitmapFromFile(string filePath)
        {
            lock (_lockObject)
            {
                return new Bitmap(filePath);
            }
        }

        private void CleanupTempFiles(TempFiles tempFiles)
        {
            if (tempFiles == null)
                return;

            try
            {
                foreach (var file in new[] { tempFiles.InputPath, tempFiles.OutputPath, tempFiles.ProgressPath })
                {
                    if (File.Exists(file))
                        File.Delete(file);
                }
            }
            catch
            {
                // 忽略清理错误
            }
        }

        private void LogMessage(string message)
        {
            try
            {
                var logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {message}{Environment.NewLine}";
                File.AppendAllText(_logPath, logEntry);
            }
            catch
            {
                // 忽略日志写入错误
            }
        }

        private class TempFiles
        {
            public string InputPath { get; set; }
            public string OutputPath { get; set; }
            public string ProgressPath { get; set; }
        }

        private class ProgressData
        {
            public int Progress { get; set; }
            public string Message { get; set; }
            public double Timestamp { get; set; }
        }
        #endregion
    }
}