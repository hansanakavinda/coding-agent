"""Generates an animated terminal demo GIF for the README without external dependencies."""

import struct
from pathlib import Path


def lzw_compress(data: bytes, min_code_size: int) -> bytes:
    """Encode stream of color indices into LZW compressed sub-blocks."""
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    next_code = end_code + 1
    code_size = min_code_size + 1

    table = {bytes([i]): i for i in range(clear_code)}

    bits = 0
    num_bits = 0
    out_bytes = bytearray()

    def write_bits(code: int, size: int) -> None:
        nonlocal bits, num_bits
        bits |= code << num_bits
        num_bits += size
        while num_bits >= 8:
            out_bytes.append(bits & 0xFF)
            bits >>= 8
            num_bits -= 8

    write_bits(clear_code, code_size)

    pattern = bytearray()
    for b in data:
        pattern.append(b)
        if bytes(pattern) not in table:
            # write prefix code
            write_bits(table[bytes(pattern[:-1])], code_size)
            if next_code < 4096:
                table[bytes(pattern)] = next_code
                next_code += 1
                if next_code > (1 << code_size) and code_size < 12:
                    code_size += 1
            else:
                write_bits(clear_code, code_size)
                table = {bytes([i]): i for i in range(clear_code)}
                next_code = end_code + 1
                code_size = min_code_size + 1
            pattern = bytearray([b])

    if pattern:
        write_bits(table[bytes(pattern)], code_size)
    write_bits(end_code, code_size)

    if num_bits > 0:
        out_bytes.append(bits & 0xFF)

    # Package into GIF sub-blocks (max 255 bytes each)
    subblocks = bytearray([min_code_size])
    idx = 0
    while idx < len(out_bytes):
        chunk = out_bytes[idx : idx + 255]
        subblocks.append(len(chunk))
        subblocks.extend(chunk)
        idx += 255
    subblocks.append(0)  # Block terminator
    return bytes(subblocks)


def create_demo_gif(output_path: Path) -> None:
    """Create a styled animated GIF representing the agent CLI demo."""
    width, height = 720, 360

    # Color palette (Catppuccin Mocha themed)
    # 0: BG (#1E1E2E), 1: Header (#181825), 2: Text (#CDD6F4), 3: Accent Green (#A6E3A1),
    # 4: Accent Cyan (#89DCEB), 5: Accent Yellow (#F9E2AF), 6: Border (#45475A), 7: Red (#F38BA8)
    palette = [
        0x1E, 0x1E, 0x2E,  # 0: bg dark
        0x18, 0x18, 0x25,  # 1: top bar
        0xCD, 0xD6, 0xF4,  # 2: text white/fg
        0xA6, 0xE3, 0xA1,  # 3: green
        0x89, 0xDC, 0xEB,  # 4: cyan
        0xF9, 0xE2, 0xAF,  # 5: yellow
        0x45, 0x47, 0x5A,  # 6: border/dim
        0xF3, 0x8B, 0xA8,  # 7: red
    ]
    # Pad palette to 256 colors
    palette.extend([0] * (256 * 3 - len(palette)))

    # Frame definitions: each frame has a delay in 1/100ths of a sec and a draw function
    frames = []

    # Simple 5x7 bitmap font for rendering ASCII characters onto pixel grid
    FONT = {
        ' ': [0, 0, 0, 0, 0],
        '$': [0x12, 0x2A, 0x7F, 0x2A, 0x24],
        '>': [0x41, 0x22, 0x14, 0x08, 0x00],
        '-': [0x08, 0x08, 0x08, 0x08, 0x08],
        '_': [0x40, 0x40, 0x40, 0x40, 0x40],
        ':': [0x00, 0x36, 0x36, 0x00, 0x00],
        '/': [0x20, 0x10, 0x08, 0x04, 0x02],
        '.': [0x00, 0x60, 0x60, 0x00, 0x00],
        '(': [0x00, 0x1C, 0x22, 0x41, 0x00],
        ')': [0x00, 0x41, 0x22, 0x1C, 0x00],
        '[': [0x00, 0x7F, 0x41, 0x41, 0x00],
        ']': [0x00, 0x41, 0x41, 0x7F, 0x00],
        'a': [0x20, 0x54, 0x54, 0x78, 0x40],
        'b': [0x7F, 0x48, 0x44, 0x38, 0x00],
        'c': [0x38, 0x44, 0x44, 0x28, 0x00],
        'd': [0x38, 0x44, 0x48, 0x7F, 0x00],
        'e': [0x38, 0x54, 0x54, 0x18, 0x00],
        'f': [0x08, 0x7E, 0x09, 0x02, 0x00],
        'g': [0x18, 0xA4, 0xA4, 0x7C, 0x00],
        'h': [0x7F, 0x08, 0x04, 0x78, 0x00],
        'i': [0x00, 0x44, 0x7D, 0x40, 0x00],
        'j': [0x60, 0x80, 0x84, 0x7D, 0x00],
        'k': [0x7F, 0x10, 0x28, 0x44, 0x00],
        'l': [0x00, 0x41, 0x7F, 0x40, 0x00],
        'm': [0x7C, 0x04, 0x18, 0x04, 0x78],
        'n': [0x7C, 0x08, 0x04, 0x78, 0x00],
        'o': [0x38, 0x44, 0x44, 0x38, 0x00],
        'p': [0xFC, 0x24, 0x24, 0x18, 0x00],
        'q': [0x18, 0x24, 0x24, 0xFC, 0x00],
        'r': [0x7C, 0x08, 0x04, 0x08, 0x00],
        's': [0x48, 0x54, 0x54, 0x24, 0x00],
        't': [0x04, 0x3F, 0x44, 0x20, 0x00],
        'u': [0x3C, 0x40, 0x40, 0x7C, 0x00],
        'v': [0x1C, 0x20, 0x40, 0x3C, 0x00],
        'w': [0x3C, 0x40, 0x30, 0x40, 0x3C],
        'x': [0x44, 0x28, 0x10, 0x28, 0x44],
        'y': [0x1C, 0xA0, 0xA0, 0x7C, 0x00],
        'z': [0x44, 0x64, 0x54, 0x4C, 0x44],
        'A': [0x7E, 0x11, 0x11, 0x11, 0x7E],
        'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
        'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
        'D': [0x7F, 0x41, 0x41, 0x22, 0x1C],
        'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
        'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
        'G': [0x3E, 0x41, 0x49, 0x49, 0x7A],
        'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
        'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
        'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
        'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F],
        'N': [0x7F, 0x04, 0x08, 0x10, 0x7F],
        'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
        'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
        'R': [0x7F, 0x09, 0x19, 0x29, 0x46],
        'S': [0x46, 0x49, 0x49, 0x49, 0x31],
        'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
        'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
        'W': [0x7F, 0x20, 0x18, 0x20, 0x7F],
        '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
        '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
        '2': [0x42, 0x61, 0x51, 0x49, 0x46],
        '3': [0x21, 0x41, 0x45, 0x4B, 0x31],
        '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
        '5': [0x27, 0x45, 0x45, 0x45, 0x39],
        '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
        '7': [0x01, 0x71, 0x09, 0x05, 0x03],
        '8': [0x36, 0x49, 0x49, 0x49, 0x36],
        '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
    }

    def render_text(grid: bytearray, x0: int, y0: int, text: str, color: int, scale: int = 2) -> None:
        cx = x0
        for char in text:
            cols = FONT.get(char, [0, 0, 0, 0, 0])
            for col_idx, col in enumerate(cols):
                for row_idx in range(8):
                    if col & (1 << row_idx):
                        for sy in range(scale):
                            for sx in range(scale):
                                px = cx + col_idx * scale + sx
                                py = y0 + row_idx * scale + sy
                                if 0 <= px < width and 0 <= py < height:
                                    grid[py * width + px] = color
            cx += (len(cols) + 1) * scale

    def make_base_window() -> bytearray:
        grid = bytearray(width * height)
        # Background
        for i in range(len(grid)):
            grid[i] = 0

        # Title bar (top 32px)
        for y in range(32):
            for x in range(width):
                grid[y * width + x] = 1

        # Border
        for x in range(width):
            grid[32 * width + x] = 6
            grid[(height - 1) * width + x] = 6
        for y in range(height):
            grid[y * width] = 6
            grid[y * width + (width - 1)] = 6

        # Window controls (red, yellow, green dots)
        for dy in range(10):
            for dx in range(10):
                if (dx - 5) ** 2 + (dy - 5) ** 2 <= 16:
                    grid[(11 + dy) * width + (20 + dx)] = 7  # red
                    grid[(11 + dy) * width + (40 + dx)] = 5  # yellow
                    grid[(11 + dy) * width + (60 + dx)] = 3  # green

        render_text(grid, 280, 8, "free-coding-agent - bash", 6, scale=2)
        return grid

    # Storyboard:
    # Frame 1: Terminal prompt
    f1 = make_base_window()
    render_text(f1, 30, 50, "$ free-agent", 3, scale=2)
    frames.append((f1, 150))

    # Frame 2: Welcome banner & prompt
    f2 = make_base_window()
    render_text(f2, 30, 50, "$ free-agent", 3, scale=2)
    render_text(f2, 30, 85, "[Free Coding Agent v0.1.0]", 4, scale=2)
    render_text(f2, 30, 115, "Model: openrouter/free (auto-routed)", 5, scale=2)
    render_text(f2, 30, 145, "Workspace: ./my_project (state isolated)", 6, scale=2)
    render_text(f2, 30, 185, "> Refactor calculate_total in billing.py", 2, scale=2)
    frames.append((f2, 220))

    # Frame 3: Model thought & tool call
    f3 = bytearray(f2)
    render_text(f3, 30, 225, "* Thinking: read billing.py line-by-line", 5, scale=2)
    render_text(f3, 30, 255, "  [Tool] read_file(path='billing.py')", 4, scale=2)
    frames.append((f3, 200))

    # Frame 4: Unified diff preview & completion
    f4 = bytearray(f3)
    render_text(f4, 30, 285, "  [Diff] @@ -12,4 +12,4 @@ unified diff", 3, scale=2)
    render_text(f4, 30, 315, "[Done] Successfully updated billing.py", 3, scale=2)
    frames.append((f4, 300))

    # Build GIF binary
    output = bytearray()
    output.extend(b"GIF89a")
    output.extend(struct.pack("<HH", width, height))
    output.append(0x87)  # GCT present, 8 bits/pixel (256 colors)
    output.append(0)     # Background color index
    output.append(0)     # Pixel aspect ratio
    output.extend(bytes(palette))

    # Netscape Application Extension for infinite looping
    output.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")

    min_code_size = 8
    for grid, delay_cs in frames:
        # Graphic Control Extension
        output.extend(b"\x21\xf9\x04\x00")
        output.extend(struct.pack("<H", delay_cs))
        output.append(0)  # Transparent color index
        output.append(0)  # Block terminator

        # Image Descriptor
        output.append(0x2C)
        output.extend(struct.pack("<HHHH", 0, 0, width, height))
        output.append(0)  # No local color table

        # Raster Data
        compressed = lzw_compress(grid, min_code_size)
        output.extend(compressed)

    # Trailer
    output.append(0x3B)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output)
    print(f"Generated {output_path} ({len(output)} bytes)")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "docs" / "assets" / "demo.gif"
    create_demo_gif(out)
