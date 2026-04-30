using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Windows.Media.Imaging;

namespace PixelArtGenerator.Services
{
    public interface IFileService
    {
        Task<BitmapSource> LoadImageAsync(string filePath);
        void SaveImage(BitmapSource image, string filePath);
        Task<Bitmap> LoadBitmapAsync(string filePath);
        void SaveBitmap(Bitmap bitmap, string filePath);
        string[] GetSupportedFormats();
        bool IsSupportedFormat(string filePath);
        Task<BitmapSource> DownloadImageAsync(string url);
    }

    public class FileService : IFileService
    {
        private static readonly object _lockObject = new object();
        private static readonly HttpClient _httpClient = new HttpClient();

        public string[] GetSupportedFormats()
        {
            return new[]
            {
                ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".ico"
            };
        }

        public bool IsSupportedFormat(string filePath)
        {
            if (string.IsNullOrEmpty(filePath))
                return false;

            var extension = Path.GetExtension(filePath).ToLower();
            return GetSupportedFormats().Contains(extension);
        }

        public async Task<BitmapSource> LoadImageAsync(string filePath)
        {
            if (string.IsNullOrEmpty(filePath))
                throw new ArgumentNullException(nameof(filePath));

            if (!File.Exists(filePath))
                throw new FileNotFoundException($"文件未找到: {filePath}");

            if (!IsSupportedFormat(filePath))
                throw new NotSupportedException($"不支持的文件格式: {Path.GetExtension(filePath)}");

            return await Task.Run(() =>
            {
                try
                {
                    using (var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read))
                    {
                        var bitmapImage = new BitmapImage();
                        bitmapImage.BeginInit();
                        bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
                        bitmapImage.StreamSource = stream;
                        bitmapImage.EndInit();
                        bitmapImage.Freeze();
                        return bitmapImage;
                    }
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException($"加载图片失败: {ex.Message}", ex);
                }
            });
        }

        public async Task<BitmapSource> DownloadImageAsync(string url)
        {
            if (string.IsNullOrEmpty(url))
                throw new ArgumentNullException(nameof(url));

            try
            {
                // 下载图片数据
                var imageData = await _httpClient.GetByteArrayAsync(url);
                
                using (var memoryStream = new MemoryStream(imageData))
                {
                    var bitmapImage = new BitmapImage();
                    bitmapImage.BeginInit();
                    bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
                    bitmapImage.StreamSource = memoryStream;
                    bitmapImage.EndInit();
                    bitmapImage.Freeze();
                    return bitmapImage;
                }
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"下载图片失败: {ex.Message}", ex);
            }
        }

        public void SaveImage(BitmapSource image, string filePath)
        {
            if (image == null)
                throw new ArgumentNullException(nameof(image));

            if (string.IsNullOrEmpty(filePath))
                throw new ArgumentNullException(nameof(filePath));

            var directory = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            lock (_lockObject)
            {
                try
                {
                    var extension = Path.GetExtension(filePath).ToLower();
                    BitmapEncoder encoder;

                    switch (extension)
                    {
                        case ".jpg":
                        case ".jpeg":
                            encoder = new JpegBitmapEncoder { QualityLevel = 95 };
                            break;
                        case ".png":
                            encoder = new PngBitmapEncoder();
                            break;
                        case ".bmp":
                            encoder = new BmpBitmapEncoder();
                            break;
                        case ".gif":
                            encoder = new GifBitmapEncoder();
                            break;
                        case ".tiff":
                            encoder = new TiffBitmapEncoder();
                            break;
                        default:
                            encoder = new PngBitmapEncoder();
                            break;
                    }

                    encoder.Frames.Add(BitmapFrame.Create(image));

                    using (var stream = new FileStream(filePath, FileMode.Create, FileAccess.Write))
                    {
                        encoder.Save(stream);
                    }
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException($"保存图片失败: {ex.Message}", ex);
                }
            }
        }

        public async Task<Bitmap> LoadBitmapAsync(string filePath)
        {
            if (string.IsNullOrEmpty(filePath))
                throw new ArgumentNullException(nameof(filePath));

            if (!File.Exists(filePath))
                throw new FileNotFoundException($"文件未找到: {filePath}");

            if (!IsSupportedFormat(filePath))
                throw new NotSupportedException($"不支持的文件格式: {Path.GetExtension(filePath)}");

            return await Task.Run(() =>
            {
                try
                {
                    lock (_lockObject)
                    {
                        return new Bitmap(filePath);
                    }
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException($"加载位图失败: {ex.Message}", ex);
                }
            });
        }

        public void SaveBitmap(Bitmap bitmap, string filePath)
        {
            if (bitmap == null)
                throw new ArgumentNullException(nameof(bitmap));

            if (string.IsNullOrEmpty(filePath))
                throw new ArgumentNullException(nameof(filePath));

            var directory = Path.GetDirectoryName(filePath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            lock (_lockObject)
            {
                try
                {
                    var extension = Path.GetExtension(filePath).ToLower();
                    ImageFormat format;

                    switch (extension)
                    {
                        case ".jpg":
                        case ".jpeg":
                            format = ImageFormat.Jpeg;
                            break;
                        case ".png":
                            format = ImageFormat.Png;
                            break;
                        case ".bmp":
                            format = ImageFormat.Bmp;
                            break;
                        case ".gif":
                            format = ImageFormat.Gif;
                            break;
                        case ".tiff":
                            format = ImageFormat.Tiff;
                            break;
                        default:
                            format = ImageFormat.Png;
                            break;
                    }

                    bitmap.Save(filePath, format);
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException($"保存位图失败: {ex.Message}", ex);
                }
            }
        }

        public static BitmapSource ConvertBitmapToBitmapSource(Bitmap bitmap)
        {
            if (bitmap == null)
                throw new ArgumentNullException(nameof(bitmap));

            lock (_lockObject)
            {
                using (var memoryStream = new MemoryStream())
                {
                    bitmap.Save(memoryStream, ImageFormat.Png);
                    memoryStream.Position = 0;

                    var bitmapImage = new BitmapImage();
                    bitmapImage.BeginInit();
                    bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
                    bitmapImage.StreamSource = memoryStream;
                    bitmapImage.EndInit();
                    bitmapImage.Freeze();

                    return bitmapImage;
                }
            }
        }

        public static Bitmap ConvertBitmapSourceToBitmap(BitmapSource bitmapSource)
        {
            if (bitmapSource == null)
                throw new ArgumentNullException(nameof(bitmapSource));

            lock (_lockObject)
            {
                using (var memoryStream = new MemoryStream())
                {
                    var encoder = new PngBitmapEncoder();
                    encoder.Frames.Add(BitmapFrame.Create(bitmapSource));
                    encoder.Save(memoryStream);
                    memoryStream.Position = 0;

                    return new Bitmap(memoryStream);
                }
            }
        }
    }
}