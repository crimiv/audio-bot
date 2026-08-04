from PIL import Image, ImageDraw
import io

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
        num_points = len(normalized)
        step = max(1, num_points // width)

        if num_points > width:
            resampled = []
            for i in range(0, num_points - step + 1, step):
                chunk = normalized[i:i+step]
                resampled.append(max(chunk) if chunk else 0)
            if len(resampled) < width:
                resampled.extend([0] * (width - len(resampled)))
            normalized = resampled[:width]
        elif num_points < width:
            normalized = normalized + [0] * (width - num_points)

        normalized = normalized[:width]
        while len(normalized) < width:
            normalized.append(0)

        points = []
        for i, val in enumerate(normalized):
            x = i
            y = int(mid_y - val * (height // 2 - 6))
            points.append((x, y))

        if points:
            points.append((width - 1, mid_y + (height // 2 - 6)))
            points.append((0, mid_y + (height // 2 - 6)))
            points.append((0, points[0][1]))

            draw.polygon(points, fill=color)

            outline_points = points[:len(normalized)]
            if len(outline_points) > 1:
                draw.line(outline_points, fill=color, width=2)

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