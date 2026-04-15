using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using Microsoft.Win32;

namespace PixelArtGenerator.Controls
{
    public partial class OptionsWindow : Window
    {
        public OptionsWindow()
        {
            InitializeComponent();
            LoadSettings();
        }

        private void LoadSettings()
        {
            // 加载现有设置
            PythonPathTextBox.Text = Properties.Settings.Default.PythonPath;
            TempDirectoryTextBox.Text = Properties.Settings.Default.TempDirectory;
            AutoInstallDependenciesCheckBox.IsChecked = Properties.Settings.Default.AutoInstallDependencies;
            
            // 设置日志路径
            var logPath = Path.Combine(Path.GetTempPath(), "PixelArtGenerator", "processing.log");
            LogPathTextBox.Text = logPath;
        }

        private void SaveSettings()
        {
            // 保存设置
            Properties.Settings.Default.PythonPath = PythonPathTextBox.Text;
            Properties.Settings.Default.TempDirectory = TempDirectoryTextBox.Text;
            Properties.Settings.Default.AutoInstallDependencies = AutoInstallDependenciesCheckBox.IsChecked ?? false;
            Properties.Settings.Default.Save();
        }

        private void BrowsePythonPathButton_Click(object sender, RoutedEventArgs e)
        {
            var openFileDialog = new OpenFileDialog
            {
                Title = "选择Python可执行文件",
                Filter = "Python executable|python.exe|All files|*.*"
            };

            if (openFileDialog.ShowDialog() == true)
            {
                PythonPathTextBox.Text = openFileDialog.FileName;
            }
        }

        private void BrowseTempDirectoryButton_Click(object sender, RoutedEventArgs e)
        {
            using (var dialog = new System.Windows.Forms.FolderBrowserDialog())
            {
                if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK)
                {
                    TempDirectoryTextBox.Text = dialog.SelectedPath;
                }
            }
        }

        private void AutoDetectPythonButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // 尝试在常见位置查找Python
                string[] possiblePaths = {
                    @"C:\Python39\python.exe",
                    @"C:\Python38\python.exe",
                    @"C:\Python37\python.exe",
                    @"C:\Users\" + Environment.UserName + @"\AppData\Local\Programs\Python\Python39\python.exe",
                    @"C:\Users\" + Environment.UserName + @"\AppData\Local\Programs\Python\Python38\python.exe",
                    @"C:\Users\" + Environment.UserName + @"\AppData\Local\Programs\Python\Python37\python.exe"
                };

                foreach (string path in possiblePaths)
                {
                    if (File.Exists(path))
                    {
                        PythonPathTextBox.Text = path;
                        return;
                    }
                }

                // 如果在常见位置找不到，尝试使用where命令查找
                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "where",
                        Arguments = "python",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true
                    }
                };

                process.Start();
                string output = process.StandardOutput.ReadToEnd();
                process.WaitForExit();

                if (process.ExitCode == 0 && !string.IsNullOrEmpty(output))
                {
                    string[] paths = output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                    if (paths.Length > 0)
                    {
                        PythonPathTextBox.Text = paths[0];
                        return;
                    }
                }

                MessageBox.Show("无法自动检测到Python安装路径，请手动选择。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"自动检测Python路径时出错: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ViewLogButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string logPath = LogPathTextBox.Text;
                if (File.Exists(logPath))
                {
                    Process.Start("notepad.exe", logPath);
                }
                else
                {
                    MessageBox.Show("日志文件不存在。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"打开日志文件时出错: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ClearLogButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string logPath = LogPathTextBox.Text;
                if (File.Exists(logPath))
                {
                    File.WriteAllText(logPath, string.Empty);
                    MessageBox.Show("日志已清空。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                else
                {
                    MessageBox.Show("日志文件不存在。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"清空日志文件时出错: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OKButton_Click(object sender, RoutedEventArgs e)
        {
            SaveSettings();
            DialogResult = true;
            Close();
        }

        private void CancelButton_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}