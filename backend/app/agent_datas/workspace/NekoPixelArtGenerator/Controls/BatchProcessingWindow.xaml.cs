using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using Microsoft.Win32;
using PixelArtGenerator.Models;
using PixelArtGenerator.Services;

namespace PixelArtGenerator.Controls
{
    public partial class BatchProcessingWindow : Window
    {
        private readonly IPythonPixelArtService _pixelArtService;
        private readonly PixelArtOptions _defaultOptions;
        private readonly ObservableCollection<BatchFileItem> _fileItems;
        private CancellationTokenSource _cancellationTokenSource;

        public BatchProcessingWindow(IPythonPixelArtService pixelArtService, PixelArtOptions defaultOptions)
        {
            InitializeComponent();
            
            _pixelArtService = pixelArtService;
            _defaultOptions = defaultOptions;
            _fileItems = new ObservableCollection<BatchFileItem>();
            
            FileListDataGrid.ItemsSource = _fileItems;
        }

        private void AddFilesButton_Click(object sender, RoutedEventArgs e)
        {
            var openFileDialog = new OpenFileDialog
            {
                Title = "选择图片文件",
                Filter = "图片文件|*.jpg;*.jpeg;*.png;*.bmp;*.gif|所有文件|*.*",
                Multiselect = true
            };

            if (openFileDialog.ShowDialog() == true)
            {
                foreach (var fileName in openFileDialog.FileNames)
                {
                    if (!_fileItems.Any(item => item.FilePath == fileName))
                    {
                        _fileItems.Add(new BatchFileItem
                        {
                            FileName = Path.GetFileName(fileName),
                            FilePath = fileName,
                            Status = "等待处理",
                            OutputPath = GenerateOutputPath(fileName)
                        });
                    }
                }
            }
        }

        private void RemoveSelectedButton_Click(object sender, RoutedEventArgs e)
        {
            var selectedItems = FileListDataGrid.SelectedItems.Cast<BatchFileItem>().ToList();
            foreach (var item in selectedItems)
            {
                _fileItems.Remove(item);
            }
        }

        private void ClearAllButton_Click(object sender, RoutedEventArgs e)
        {
            _fileItems.Clear();
        }

        private async void StartProcessButton_Click(object sender, RoutedEventArgs e)
        {
            if (_fileItems.Count == 0)
            {
                MessageBox.Show("请先添加要处理的文件", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            _cancellationTokenSource = new CancellationTokenSource();
            StartProcessButton.IsEnabled = false;
            AddFilesButton.IsEnabled = false;
            RemoveSelectedButton.IsEnabled = false;
            ClearAllButton.IsEnabled = false;

            try
            {
                await ProcessFilesAsync(_cancellationTokenSource.Token);
                MessageBox.Show("批量处理完成", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (OperationCanceledException)
            {
                MessageBox.Show("批量处理已取消", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"处理过程中发生错误: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally
            {
                StartProcessButton.IsEnabled = true;
                AddFilesButton.IsEnabled = true;
                RemoveSelectedButton.IsEnabled = true;
                ClearAllButton.IsEnabled = true;
            }
        }

        private void CancelButton_Click(object sender, RoutedEventArgs e)
        {
            _cancellationTokenSource?.Cancel();
        }

        private async Task ProcessFilesAsync(CancellationToken cancellationToken)
        {
            foreach (var item in _fileItems)
            {
                cancellationToken.ThrowIfCancellationRequested();

                try
                {
                    item.Status = "处理中...";
                    
                    // 加载图片
                    var bitmap = await Task.Run(() => 
                    {
                        using (var stream = File.OpenRead(item.FilePath))
                        {
                            var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
                            return decoder.Frames[0];
                        }
                    }, cancellationToken);

                    // 处理图片
                    using (var bitmapImage = BitmapFromSource(bitmap))
                    {
                        var result = await _pixelArtService.ProcessImageAsync(bitmapImage, _defaultOptions);
                        
                        if (result != null)
                        {
                            // 保存结果
                            await Task.Run(() => 
                            {
                                var encoder = new PngBitmapEncoder();
                                encoder.Frames.Add(BitmapFrame.Create(BitmapSourceFromBitmap(result)));
                                using (var fileStream = File.Create(item.OutputPath))
                                {
                                    encoder.Save(fileStream);
                                }
                            }, cancellationToken);
                            
                            item.Status = "已完成";
                        }
                        else
                        {
                            item.Status = "处理失败";
                        }
                    }
                }
                catch (Exception ex)
                {
                    item.Status = $"错误: {ex.Message}";
                }
            }
        }

        private string GenerateOutputPath(string inputPath)
        {
            var directory = Path.GetDirectoryName(inputPath);
            var fileNameWithoutExtension = Path.GetFileNameWithoutExtension(inputPath);
            var extension = Path.GetExtension(inputPath);
            return Path.Combine(directory, $"{fileNameWithoutExtension}_pixelart{extension}");
        }

        private System.Drawing.Bitmap BitmapFromSource(BitmapSource source)
        {
            using (var memoryStream = new MemoryStream())
            {
                var encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(source));
                encoder.Save(memoryStream);
                
                return new System.Drawing.Bitmap(memoryStream);
            }
        }

        private BitmapSource BitmapSourceFromBitmap(System.Drawing.Bitmap bitmap)
        {
            using (var memoryStream = new MemoryStream())
            {
                bitmap.Save(memoryStream, System.Drawing.Imaging.ImageFormat.Png);
                memoryStream.Position = 0;
                
                var bitmapImage = new BitmapImage();
                bitmapImage.BeginInit();
                bitmapImage.StreamSource = memoryStream;
                bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
                bitmapImage.EndInit();
                
                return bitmapImage;
            }
        }
    }

    public class BatchFileItem
    {
        public string FileName { get; set; }
        public string FilePath { get; set; }
        public string Status { get; set; }
        public string OutputPath { get; set; }
    }
}