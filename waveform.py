from PIL import Image, ImageDraw
import io

def generate_waveform_image(waveform_data, width=600, height=150, color="#00FF88", bg_color="#1a1a2e"):
    try:
        if not waveform_data or len(waveform_data) < 10:
            return create_placeholder(width, height, "No waveform data", bg_color)

        max_val = max(abs(min(waveform_data)), abs(max(waveform_data)))
        if max_val == 0:
            return create_placeholder(width, height, "Audio is silent", bg_color)

        normalized = [v / max_val for v in waveform_data]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        mid_y = height // 2
        total_points = len(normalized)

        if total_points > width:
            step = total_points // width
            resampled = []
            for i in range(0, total_points, step):
                chunk = normalized[i:i+step]
                if chunk:
                    resampled.append(max(chunk))
            normalized = resampled

        if len(normalized) < width:
            normalized = normalized + [0] * (width - len(normalized))

        normalized = normalized[:width]

        points = []
        for i, val in enumerate(normalized):
            y = int(mid_y - val * (height // 2 - 6))
            points.append((i, y))

        draw.polygon(
            points + [(width - 1, mid_y + (height // 2 - 6)), (0, mid_y + (height // 2 - 6))],
            fill=color,
            outline=None
        )

        if len(points) > 1:
            draw.line(points, fill=color, width=2)

        return img

    except Exception as e:
        return create_placeholder(width, height, f"Error: {str(e)[:20]}", bg_color)

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