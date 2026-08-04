from PIL import Image, ImageDraw
import io
import math

def generate_waveform_image(waveform_data, width=600, height=150, color="#00FF88", bg_color="#1a1a2e"):
    try:
        if not waveform_data or len(waveform_data) < 2:
            return create_placeholder(width, height, "No waveform data", bg_color)

        max_val = max(abs(min(waveform_data)), abs(max(waveform_data)))
        if max_val == 0:
            return create_placeholder(width, height, "Audio is silent", bg_color)

        normalized = [v / max_val for v in waveform_data]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        mid_y = height // 2
        num_bars = len(normalized)
        bar_width = max(1, width // num_bars)

        for i, val in enumerate(normalized):
            x = i * bar_width
            val = max(-1, min(1, val))
            bar_height = int(abs(val) * (height // 2 - 4))

            if val >= 0:
                y0 = mid_y - bar_height
                y1 = mid_y
            else:
                y0 = mid_y
                y1 = mid_y + bar_height

            if y1 - y0 < 1:
                y1 = y0 + 1

            draw.rectangle([x, y0, x + bar_width - 1, y1], fill=color)

        return img

    except Exception:
        return create_placeholder(width, height, "Waveform error", bg_color)

def create_placeholder(width, height, text, bg_color="#1a1a2e"):
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    draw.text((width//2 - 40, height//2 - 10), text, fill="white")
    draw.rectangle([0, 0, width-1, height-1], outline="#333333")
    return img

def waveform_to_bytes(img, format="PNG"):
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf