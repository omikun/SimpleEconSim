"""
sim_server/qr_code.py — Pure-Python dependency-free QR Code Generator.

Compliant with ISO/IEC 18004 specifications for QR Code 2005 / Model 2.
Supports Byte Mode encoding with Reed-Solomon GF(256) error correction (ECC Level L).
Produces scannable ANSI terminal outputs (full solid blocks and half-blocks),
SVG vector XML strings, and Pygame Surfaces.
"""

from typing import List, Tuple, Optional


# GF(256) Math for Reed-Solomon Error Correction (Primitive Polynomial 0x11D = 285)
EXP_TABLE = [0] * 512
LOG_TABLE = [0] * 256

def _init_gf256():
    x = 1
    for i in range(255):
        EXP_TABLE[i] = x
        LOG_TABLE[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        EXP_TABLE[i] = EXP_TABLE[i - 255]

_init_gf256()

def _gf_mul(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return EXP_TABLE[LOG_TABLE[x] + LOG_TABLE[y]]

def _rs_generator_poly(degree: int) -> List[int]:
    """Generate monic generator polynomial of specified degree in descending power order."""
    poly = [1]
    for i in range(degree):
        next_poly = [0] * (len(poly) + 1)
        for j, c in enumerate(poly):
            next_poly[j] ^= c
            next_poly[j + 1] ^= _gf_mul(c, EXP_TABLE[i])
        poly = next_poly
    return poly

def _rs_encode(data: List[int], ecc_len: int) -> List[int]:
    """Calculate Reed-Solomon error correction codewords for input data."""
    gen = _rs_generator_poly(ecc_len)
    msg = data + [0] * ecc_len
    for i in range(len(data)):
        lead = msg[i]
        if lead != 0:
            for j, g in enumerate(gen):
                msg[i + j] ^= _gf_mul(g, lead)
    return msg[len(data):]


# QR Specifications for Versions 1..6 (ECC Level L: 7% recovery, maximum data density)
# (Version: size, total_codewords, data_codewords, ec_codewords_per_block, num_blocks)
QR_SPECS_L = {
    1: (21, 26, 19, 7, 1),
    2: (25, 44, 34, 10, 1),
    3: (29, 70, 55, 15, 1),
    4: (33, 100, 80, 20, 1),
    5: (37, 134, 108, 26, 1),
    6: (41, 172, 136, 18, 2),
}

ALIGNMENT_LOCATIONS = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
}


class QRCode:
    """Pure-Python ISO/IEC 18004 QR Code Model and Multi-format Renderer."""

    def __init__(self, text: str):
        self.text = text
        self.data_bytes = text.encode('utf-8')
        self.version = self._determine_version(len(self.data_bytes))
        self.size, self.total_cw, self.data_cw, self.ec_cw, self.blocks = QR_SPECS_L[self.version]
        self.matrix: List[List[Optional[bool]]] = [[None] * self.size for _ in range(self.size)]
        self.is_function: List[List[bool]] = [[False] * self.size for _ in range(self.size)]
        self._build_qr()

    def _determine_version(self, byte_len: int) -> int:
        for ver, (_sz, _tc, data_cap, _ec, _blk) in QR_SPECS_L.items():
            # Byte mode header: 4 bits mode + 8 bits count + data bits
            needed_bits = 4 + 8 + (byte_len * 8)
            if needed_bits <= data_cap * 8:
                return ver
        raise ValueError(f"Text too long for supported QR versions (max ~130 bytes): {byte_len} bytes")

    def _build_qr(self):
        self._add_finder_patterns()
        self._add_alignment_patterns()
        self._add_timing_patterns()
        self._reserve_format_info()
        self._add_dark_module()

        codewords = self._encode_data()
        self._place_data(codewords)
        mask = self._choose_best_mask()
        self._apply_mask(mask)
        self._write_format_info(mask)

    def _set_module(self, r: int, c: int, val: bool, is_fn: bool = False):
        if 0 <= r < self.size and 0 <= c < self.size:
            self.matrix[r][c] = val
            if is_fn:
                self.is_function[r][c] = True

    def _add_finder_patterns(self):
        for ro, co in [(0, 0), (0, self.size - 7), (self.size - 7, 0)]:
            # 7x7 outer square, inner ring, and core
            for r in range(7):
                for c in range(7):
                    is_black = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                    self._set_module(ro + r, co + c, is_black, is_fn=True)
            # 1-module white separator border
            for i in range(-1, 8):
                for dr, dc in [(i, -1), (i, 7), (-1, i), (7, i)]:
                    r, c = ro + dr, co + dc
                    if 0 <= r < self.size and 0 <= c < self.size:
                        self._set_module(r, c, False, is_fn=True)

    def _add_alignment_patterns(self):
        coords = ALIGNMENT_LOCATIONS.get(self.version, [])
        for r_center in coords:
            for c_center in coords:
                # Skip finders
                if (r_center <= 8 and c_center <= 8) or \
                   (r_center <= 8 and c_center >= self.size - 8) or \
                   (r_center >= self.size - 8 and c_center <= 8):
                    continue
                # 5x5 alignment pattern
                for r in range(-2, 3):
                    for c in range(-2, 3):
                        is_black = (abs(r) == 2 or abs(c) == 2 or (r == 0 and c == 0))
                        self._set_module(r_center + r, c_center + c, is_black, is_fn=True)

    def _add_timing_patterns(self):
        for i in range(8, self.size - 8):
            val = (i % 2 == 0)
            if not self.is_function[6][i]:
                self._set_module(6, i, val, is_fn=True)
            if not self.is_function[i][6]:
                self._set_module(i, 6, val, is_fn=True)

    def _add_dark_module(self):
        # Dark module always at coordinate (4 * version + 9, 8)
        self._set_module(4 * self.version + 9, 8, True, is_fn=True)

    def _reserve_format_info(self):
        for i in range(9):
            self.is_function[8][i] = True
            self.is_function[i][8] = True
        for i in range(8):
            self.is_function[8][self.size - 1 - i] = True
            self.is_function[self.size - 1 - i][8] = True

    def _encode_data(self) -> List[int]:
        bits = []
        # Mode indicator: 0100 (Byte mode)
        bits.extend([0, 1, 0, 0])
        # Character count: 8 bits for versions 1..9
        cnt = len(self.data_bytes)
        for b in f"{cnt:08b}":
            bits.append(int(b))
        # Data bytes
        for byte in self.data_bytes:
            for b in f"{byte:08b}":
                bits.append(int(b))

        # Terminator up to 4 zero bits
        max_data_bits = self.data_cw * 8
        bits.extend([0] * min(4, max_data_bits - len(bits)))

        # Pad to multiple of 8
        while len(bits) % 8 != 0:
            bits.append(0)

        # Pack into bytes
        data_bytes = []
        for i in range(0, len(bits), 8):
            chunk = bits[i:i + 8]
            val = 0
            for bit in chunk:
                val = (val << 1) | bit
            data_bytes.append(val)

        # Pad with 0xEC and 0x11
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        while len(data_bytes) < self.data_cw:
            data_bytes.append(pad_bytes[pad_idx % 2])
            pad_idx += 1

        # Error correction encoding
        if self.blocks == 1:
            ec = _rs_encode(data_bytes, self.ec_cw)
            return data_bytes + ec
        else:
            # Multi-block interleaving
            b_len = self.data_cw // self.blocks
            blocks_data = []
            blocks_ec = []
            for b in range(self.blocks):
                b_data = data_bytes[b * b_len:(b + 1) * b_len]
                blocks_data.append(b_data)
                blocks_ec.append(_rs_encode(b_data, self.ec_cw))

            interleaved = []
            for i in range(b_len):
                for b in range(self.blocks):
                    interleaved.append(blocks_data[b][i])
            for i in range(self.ec_cw):
                for b in range(self.blocks):
                    interleaved.append(blocks_ec[b][i])
            return interleaved

    def _place_data(self, codewords: List[int]):
        bits = []
        for cw in codewords:
            for b in f"{cw:08b}":
                bits.append(int(b))

        bit_idx = 0
        r = self.size - 1
        c = self.size - 1
        dir_up = True

        while c > 0:
            if c == 6:
                c -= 1
            for i in range(self.size):
                row = (self.size - 1 - i) if dir_up else i
                for col in (c, c - 1):
                    if not self.is_function[row][col]:
                        val = bool(bits[bit_idx]) if bit_idx < len(bits) else False
                        self.matrix[row][col] = val
                        bit_idx += 1
            dir_up = not dir_up
            c -= 2

    @staticmethod
    def _mask_eval(mask_pat: int, r: int, c: int) -> bool:
        if mask_pat == 0:
            return (r + c) % 2 == 0
        elif mask_pat == 1:
            return r % 2 == 0
        elif mask_pat == 2:
            return c % 3 == 0
        elif mask_pat == 3:
            return (r + c) % 3 == 0
        elif mask_pat == 4:
            return ((r // 2) + (c // 3)) % 2 == 0
        elif mask_pat == 5:
            return ((r * c) % 2) + ((r * c) % 3) == 0
        elif mask_pat == 6:
            return (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
        elif mask_pat == 7:
            return (((r + c) % 2) + ((r * c) % 3)) % 2 == 0
        return False

    def _apply_mask(self, mask_pat: int):
        for r in range(self.size):
            for c in range(self.size):
                if not self.is_function[r][c]:
                    if self._mask_eval(mask_pat, r, c):
                        self.matrix[r][c] = not bool(self.matrix[r][c])

    def _penalty_score(self, m: int) -> int:
        grid = [[(not self.matrix[r][c]) if (not self.is_function[r][c] and self._mask_eval(m, r, c)) else bool(self.matrix[r][c])
                 for c in range(self.size)] for r in range(self.size)]
        score = 0

        # Penalty 1: Runs of >= 5 consecutive modules of same color
        for r in range(self.size):
            run_color = grid[r][0]
            run_len = 1
            for c in range(1, self.size):
                if grid[r][c] == run_color:
                    run_len += 1
                    if run_len == 5:
                        score += 3
                    elif run_len > 5:
                        score += 1
                else:
                    run_color = grid[r][c]
                    run_len = 1

        for c in range(self.size):
            run_color = grid[0][c]
            run_len = 1
            for r in range(1, self.size):
                if grid[r][c] == run_color:
                    run_len += 1
                    if run_len == 5:
                        score += 3
                    elif run_len > 5:
                        score += 1
                else:
                    run_color = grid[r][c]
                    run_len = 1

        # Penalty 2: 2x2 blocks of same color
        for r in range(self.size - 1):
            for c in range(self.size - 1):
                val = grid[r][c]
                if val == grid[r + 1][c] == grid[r][c + 1] == grid[r + 1][c + 1]:
                    score += 3

        # Penalty 3: Finder-like pattern 1:1:3:1:1
        pat1 = [True, False, True, True, True, False, True, False, False, False, False]
        pat2 = [False, False, False, False, True, False, True, True, True, False, True]
        for r in range(self.size):
            for c in range(self.size - 10):
                sub = grid[r][c:c + 11]
                if sub == pat1 or sub == pat2:
                    score += 40
        for c in range(self.size):
            for r in range(self.size - 10):
                sub = [grid[r + k][c] for k in range(11)]
                if sub == pat1 or sub == pat2:
                    score += 40

        # Penalty 4: Balance of dark / light modules
        total_modules = self.size * self.size
        dark_count = sum(sum(1 for val in row if val) for row in grid)
        pct = (dark_count * 100) // total_modules
        k = abs(pct - 50) // 5
        score += k * 10

        return score

    def _choose_best_mask(self) -> int:
        best_score = float('inf')
        best_mask = 0
        for m in range(8):
            score = self._penalty_score(m)
            if score < best_score:
                best_score = score
                best_mask = m
        return best_mask

    def _write_format_info(self, mask: int):
        """Write canonical 15-bit BCH format information to both copies."""
        # 5 bits: 2 bits for ECC Level L (01_2 = 1) and 3 bits for mask
        data = (1 << 3) | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits_15 = ((data << 10) | rem) ^ 0x5412

        # First copy (around top-left finder)
        for i in range(0, 6):
            self._set_module(8, i, bool((bits_15 >> i) & 1), is_fn=True)
        self._set_module(8, 7, bool((bits_15 >> 6) & 1), is_fn=True)
        self._set_module(8, 8, bool((bits_15 >> 7) & 1), is_fn=True)
        self._set_module(7, 8, bool((bits_15 >> 8) & 1), is_fn=True)
        for i in range(9, 15):
            self._set_module(14 - i, 8, bool((bits_15 >> i) & 1), is_fn=True)

        # Second copy (around bottom-left and top-right finders)
        for i in range(0, 7):
            self._set_module(self.size - 1 - i, 8, bool((bits_15 >> i) & 1), is_fn=True)
        for i in range(7, 15):
            self._set_module(8, self.size - 15 + i, bool((bits_15 >> i) & 1), is_fn=True)
        self._set_module(4 * self.version + 9, 8, True, is_fn=True)

    def to_ansi_terminal(self, quiet_zone: int = 4, style: str = 'full') -> str:
        """
        Render scannable QR code for terminal displays.

        style='full' (default):
            Uses 2 spaces with solid background color (\\033[40m  \\033[47m  ).
            Zero line-height font gaps, perfect ~1:1 aspect ratio,
            scanned instantly by iPhone camera.
        style='half':
            Uses Unicode half-block characters (▀, ▄, █, ' ') for compact terminals.
        """
        sz = self.size
        padded_w = sz + 2 * quiet_zone
        padded_h = sz + 2 * quiet_zone

        grid = [[False] * padded_w for _ in range(padded_h)]
        for r in range(sz):
            for c in range(sz):
                grid[r + quiet_zone][c + quiet_zone] = bool(self.matrix[r][c])

        lines = []

        if style == 'full':
            WHITE_BG = "\033[47m"  # White background
            BLACK_BG = "\033[40m"  # Black background
            RESET = "\033[0m"

            for r in range(padded_h):
                row_parts = []
                for c in range(padded_w):
                    is_dark = grid[r][c]
                    bg = BLACK_BG if is_dark else WHITE_BG
                    row_parts.append(f"{bg}  ")
                row_parts.append(RESET)
                lines.append("".join(row_parts))

            return "\n".join(lines)

        else:
            # Half-block compact mode
            WHITE_BG = "\033[47m"
            BLACK_TEXT = "\033[30m"
            RESET = "\033[0m"

            for r in range(0, padded_h, 2):
                row_str = WHITE_BG + BLACK_TEXT
                for c in range(padded_w):
                    top = grid[r][c] if r < padded_h else False
                    bot = grid[r + 1][c] if (r + 1) < padded_h else False

                    if top and bot:
                        row_str += "█"
                    elif top and not bot:
                        row_str += "▀"
                    elif not top and bot:
                        row_str += "▄"
                    else:
                        row_str += " "
                row_str += RESET
                lines.append(row_str)

            return "\n".join(lines)

    def to_svg(self, size_px: int = 280, quiet_zone: int = 4) -> str:
        """Generate standalone SVG XML string for browser rendering."""
        total_cells = self.size + 2 * quiet_zone
        cell_size = size_px / float(total_cells)

        rects = []
        for r in range(self.size):
            for c in range(self.size):
                if self.matrix[r][c]:
                    x = (c + quiet_zone) * cell_size
                    y = (r + quiet_zone) * cell_size
                    rects.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_size + 0.1:.2f}" height="{cell_size + 0.1:.2f}" fill="#111" />')

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size_px} {size_px}" width="{size_px}" height="{size_px}">
  <rect width="100%" height="100%" fill="#ffffff" rx="8" />
  {''.join(rects)}
</svg>'''

    def to_pygame_surface(self, module_px: int = 7, quiet_zone: int = 4):
        """Generate a sharp, high-contrast Pygame Surface for rendering in Dev Viewer."""
        import pygame
        total = self.size + 2 * quiet_zone
        surf = pygame.Surface((total * module_px, total * module_px))
        surf.fill((255, 255, 255))
        for r in range(self.size):
            for c in range(self.size):
                if self.matrix[r][c]:
                    rect = pygame.Rect(
                        (c + quiet_zone) * module_px,
                        (r + quiet_zone) * module_px,
                        module_px, module_px
                    )
                    surf.fill((12, 14, 18), rect)
        return surf


def generate_terminal_qr(url: str, style: str = 'full') -> str:
    """Generate scannable ANSI terminal QR code string for the given URL."""
    qr = QRCode(url)
    return qr.to_ansi_terminal(style=style)


def generate_svg_qr(url: str, size: int = 280) -> str:
    """Generate SVG XML string for the given URL."""
    qr = QRCode(url)
    return qr.to_svg(size_px=size)


def generate_pygame_qr(url: str, module_px: int = 7):
    """Generate a Pygame Surface QR code for in-engine HUD display."""
    qr = QRCode(url)
    return qr.to_pygame_surface(module_px=module_px)
