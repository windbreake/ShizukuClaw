from PIL import Image, ImageDraw

# Create a new 16x16 image with a transparent background
img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw a simple arrow pointing down (download icon)
# Arrow shaft
draw.rectangle([7, 2, 8, 10], fill=(255, 255, 255, 255))

# Arrow head
draw.polygon([(5, 8), (10, 8), (7.5, 12)], fill=(255, 255, 255, 255))

# Save the image
img.save('Resources/Icons/download.png')
print("Download icon created successfully!")