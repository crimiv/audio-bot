from PIL import Image, ImageDraw
import io
import math

def generate_waveform_image(waveform_data, width=600, height=150, color="#00FF88", bg_color="#1a1a2e"):
    """Generate a waveform image from waveform data."""
    
    if not waveform_data or len(waveform_data) < 2:
        # Return a placeholder if no data
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        draw.text((width//2 - 40, height//2 - 10), "No waveform data", fill="white")
        return img
    
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Normalize waveform data
    max_val = max(abs(min(waveform_data)), abs(max(waveform_data)))
    if max_val == 0:
        max_val = 1
    
    normalized = [v / max_val for v in waveform_data]
    
    # Draw waveform
    mid_y = height // 2
    bar_width = max(1, width // len(normalized))
    
    for i, val in enumerate(normalized):
        x = i * bar_width
        # Clamp value
        val = max(-1, min(1, val))
        bar_height = int(abs(val) * (height // 2 - 4))
        
        if val >= 0:
            y0 = mid_y - bar_height
            y1 = mid_y
        else:
            y0 = mid_y
            y1 = mid_y + bar_height
        
        # Ensure at least 1px height
        if y1 - y0 < 1:
            y1 = y0 + 1
        
        draw.rectangle([x, y0, x + bar_width - 1, y1], fill=color)
    
    return img

def waveform_to_bytes(img, format="PNG"):
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf