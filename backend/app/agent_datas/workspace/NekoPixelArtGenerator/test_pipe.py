#!/usr/bin/env python3
"""
Simple test script to verify pipe communication
"""
import sys
from PIL import Image
from io import BytesIO

def main():
    print("Starting pipe test...", file=sys.stderr)
    
    try:
        # Read image data from stdin
        image_data = sys.stdin.buffer.read()
        print(f"Read {len(image_data)} bytes from stdin", file=sys.stderr)
        
        # Create BytesIO object
        image_stream = BytesIO(image_data)
        
        # Open image
        img = Image.open(image_stream)
        print(f"Opened image: {img.size}, {img.mode}", file=sys.stderr)
        
        # Just return the same image (no processing)
        output_stream = BytesIO()
        img.save(output_stream, format="PNG")
        image_data = output_stream.getvalue()
        
        # Write to stdout
        sys.stdout.buffer.write(image_data)
        sys.stdout.buffer.flush()
        
        print("SUCCESS:PIPE_MODE", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()