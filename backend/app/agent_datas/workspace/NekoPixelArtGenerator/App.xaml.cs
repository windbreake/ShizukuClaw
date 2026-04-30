using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace PixelArtGenerator
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            // 设置异常处理
            SetupExceptionHandling();
            
            // 确保Python依赖已安装
            EnsurePythonDependencies();
            
            base.OnStartup(e);
        }

        private void SetupExceptionHandling()
        {
            // UI线程未捕获异常处理
            DispatcherUnhandledException += OnDispatcherUnhandledException;
            
            // 非UI线程未捕获异常处理
            TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
            
            // 应用程序未处理异常处理
            AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        }

        private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
        {
            HandleException(e.Exception, "UI线程异常");
            e.Handled = true;
            
            // 强制写入桌面日志文件，确保能捕获任何异常
            try
            {
                var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                var logPath = Path.Combine(desktopPath, $"fatal_{DateTime.Now:yyyyMMdd_HHmmss}.log");
                var logContent = e.Exception.ToString();
                File.WriteAllText(logPath, logContent);
                MessageBox.Show($"致命错误，日志已写到桌面：{logPath}", "致命错误",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
            catch
            {
                // 即使写日志失败，也要确保程序退出
            }
            
            Environment.Exit(1); // 强制退出，避免卡死
        }

        private void OnUnobservedTaskException(object sender, System.Threading.Tasks.UnobservedTaskExceptionEventArgs e)
        {
            HandleException(e.Exception, "任务异常");
            e.SetObserved();
            
            // 强制写入桌面日志文件，确保能捕获任何异常
            try
            {
                var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                var logPath = Path.Combine(desktopPath, $"fatal_{DateTime.Now:yyyyMMdd_HHmmss}.log");
                var logContent = e.Exception.ToString();
                File.WriteAllText(logPath, logContent);
                MessageBox.Show($"致命错误，日志已写到桌面：{logPath}", "致命错误",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
            catch
            {
                // 即使写日志失败，也要确保程序退出
            }
            
            Environment.Exit(1); // 强制退出，避免卡死
        }

        private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
        {
            HandleException(e.ExceptionObject as Exception, "应用程序异常");
            
            // 强制写入桌面日志文件，确保能捕获任何异常
            try
            {
                var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                var logPath = Path.Combine(desktopPath, $"fatal_{DateTime.Now:yyyyMMdd_HHmmss}.log");
                var exception = e.ExceptionObject as Exception;
                var logContent = exception?.ToString() ?? "Unknown exception occurred";
                File.WriteAllText(logPath, logContent);
                MessageBox.Show($"致命错误，日志已写到桌面：{logPath}", "致命错误",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
            catch
            {
                // 即使写日志失败，也要确保程序退出
            }
            
            Environment.Exit(1); // 强制退出，避免卡死
        }

        private void HandleException(Exception exception, string context)
        {
            if (exception == null)
                return;

            try
            {
                // 记录异常信息
                LogException(exception, context);
                
                // 显示用户友好的错误信息
                ShowErrorMessage(exception, context);
            }
            catch
            {
                // 如果连错误处理都失败了，直接显示原始异常
                MessageBox.Show($"发生严重错误: {exception.Message}", "致命错误", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void LogException(Exception exception, string context)
        {
            try
            {
                var logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Logs", $"error_{DateTime.Now:yyyyMMdd}.log");
                var logDirectory = Path.GetDirectoryName(logPath);
                
                if (!Directory.Exists(logDirectory))
                    Directory.CreateDirectory(logDirectory);

                var logMessage = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {context}\n" +
                               $"异常类型: {exception.GetType().FullName}\n" +
                               $"异常消息: {exception.Message}\n" +
                               $"堆栈跟踪:\n{exception.StackTrace}\n" +
                               new string('-', 80) + "\n";

                File.AppendAllText(logPath, logMessage, Encoding.UTF8);
            }
            catch
            {
                // 记录失败不影响主程序
            }
        }

        private void ShowErrorMessage(Exception exception, string context)
        {
            var message = $"发生错误: {exception.Message}\n\n" +
                         $"上下文: {context}\n\n" +
                         "错误已记录到日志文件。\n" +
                         "请检查日志文件或联系技术支持。";

            MessageBox.Show(message, "错误", 
                MessageBoxButton.OK, MessageBoxImage.Error);
        }

        protected override void OnExit(ExitEventArgs e)
        {
            // 清理临时文件
            CleanupTempFiles();
            
            base.OnExit(e);
        }

        private void CleanupTempFiles()
        {
            try
            {
                var tempPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Temp");
                if (Directory.Exists(tempPath))
                {
                    var directoryInfo = new DirectoryInfo(tempPath);
                    foreach (var file in directoryInfo.GetFiles())
                    {
                        try
                        {
                            file.Delete();
                        }
                        catch
                        {
                            // 忽略单个文件删除错误
                        }
                    }
                }
            }
            catch
            {
                // 清理失败不影响程序退出
            }
        }

        private void EnsurePythonDependencies()
        {
            try
            {
                var scriptsPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "PythonScripts");
                var requirementsPath = Path.Combine(scriptsPath, "requirements.txt");
                
                if (!File.Exists(requirementsPath))
                    return;
                
                // 检查是否需要安装依赖
                var pythonPath = "python"; // 假设Python已在PATH中
                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonPath,
                    Arguments = $"-c \"import PIL, numpy\"",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                
                using (var process = Process.Start(startInfo))
                {
                    process.WaitForExit();
                    if (process.ExitCode != 0)
                    {
                        // 依赖未安装，尝试安装
                        InstallPythonDependencies(pythonPath, requirementsPath);
                    }
                }
            }
            catch
            {
                // 忽略依赖检查错误
            }
        }

        private void InstallPythonDependencies(string pythonPath, string requirementsPath)
        {
            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonPath,
                    Arguments = $"-m pip install -r \"{requirementsPath}\"",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                
                using (var process = Process.Start(startInfo))
                {
                    process.WaitForExit();
                }
            }
            catch
            {
                // 忽略安装错误
            }
        }
    }
}