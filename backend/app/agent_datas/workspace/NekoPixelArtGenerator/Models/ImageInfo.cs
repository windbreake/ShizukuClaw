using System;

namespace PixelArtGenerator.Models
{
    public class ImageInfo
    {
        public string FilePath { get; set; }
        public string FileName { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public string Format { get; set; }
        public long FileSize { get; set; }
        public DateTime LastModified { get; set; }
        
        public string Dimensions => $"{Width} x {Height}";
        public string FileSizeString => FormatFileSize(FileSize);
        
        public ImageInfo()
        {
        }
        
        public ImageInfo(string filePath)
        {
            FilePath = filePath;
            FileName = System.IO.Path.GetFileName(filePath);
            
            var fileInfo = new System.IO.FileInfo(filePath);
            FileSize = fileInfo.Length;
            LastModified = fileInfo.LastWriteTime;
            Format = System.IO.Path.GetExtension(filePath).ToUpper();
        }
        
        private string FormatFileSize(long bytes)
        {
            const int scale = 1024;
            string[] orders = { "B", "KB", "MB", "GB" };
            
            var max = (long)Math.Pow(scale, orders.Length - 1);
            
            foreach (var order in orders)
            {
                if (bytes > max)
                    return $"{decimal.Divide(bytes, max):##.##} {order}";
                max /= scale;
            }
            
            return "0 B";
        }
        
        public override string ToString()
        {
            return $"{FileName} - {Dimensions} - {FileSizeString}";
        }
    }
}