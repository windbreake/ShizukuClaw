using System;
using System.Drawing;

namespace PixelArtGenerator.Models
{
    public class ProcessingResult
    {
        public Bitmap ProcessedImage { get; set; }
        public TimeSpan ProcessingTime { get; set; }
        public string Status { get; set; }
        public string ErrorMessage { get; set; }
        public bool IsSuccess => string.IsNullOrEmpty(ErrorMessage);
        
        public ProcessingResult()
        {
            Status = "Unknown";
        }
        
        public static ProcessingResult Success(Bitmap image, TimeSpan processingTime)
        {
            return new ProcessingResult
            {
                ProcessedImage = image,
                ProcessingTime = processingTime,
                Status = "Success",
                ErrorMessage = null
            };
        }
        
        public static ProcessingResult Failure(string errorMessage)
        {
            return new ProcessingResult
            {
                ProcessedImage = null,
                ProcessingTime = TimeSpan.Zero,
                Status = "Failed",
                ErrorMessage = errorMessage
            };
        }
    }
}