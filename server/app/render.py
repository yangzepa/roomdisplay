"""400x300 3색(흰/검/적) 프레임 생성.

모든 화면은 팔레트 인덱스 이미지(P 모드)로 통일한다: 0=흰, 1=검, 2=적.
"""
import io
import os
import time

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 400, 300
WHITE, BLACK, RED = 0, 1, 2

# 양자화 기준 색(패널 적색은 채도가 높으므로 순적색 기준)과 웹 미리보기 색
MATCH_RGB = [(255, 255, 255), (0, 0, 0), (255, 0, 0)]
PREVIEW_RGB = [(255, 255, 255), (20, 20, 20), (205, 25, 25)]

FONT_BOLD = os.environ.get("FONT_BOLD", "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf")
FONT_REG = os.environ.get("FONT_REG", "/usr/share/fonts/truetype/nanum/NanumSquareRoundR.ttf")
TITLE = os.environ.get("TITLE", "연구실")

STATES = {
    "in":      {"label": "재실",    "sub": "편하게 노크해 주세요",   "red": False},
    "away":    {"label": "부재중",  "sub": "잠시 자리를 비웠습니다", "red": True},
    "lecture": {"label": "강의 중", "sub": "강의 후 돌아옵니다",     "red": True},
    "meeting": {"label": "회의 중", "sub": "회의 후 돌아옵니다",     "red": True},
    "out":     {"label": "퇴근",    "sub": "오늘 업무는 끝났습니다", "red": False},
    "exercise": {"label": "운동 중", "sub": "운동 후 돌아옵니다",   "red": True},
}


def _palette(rgbs):
    flat = [c for rgb in rgbs for c in rgb]
    return flat + flat[-3:] * (256 - len(rgbs))


def _font(path, size):
    return ImageFont.truetype(path, size)


def _fit_text(draw, text, path, size, max_w):
    while size > 12:
        f = _font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(path, size)


def render_status(state, until="", label="", updated=None):
    info = STATES.get(state, STATES["in"])
    im = Image.new("P", (W, H), WHITE)
    im.putpalette(_palette(PREVIEW_RGB))
    d = ImageDraw.Draw(im)

    d.rectangle([0, 0, W - 1, 54], fill=BLACK)
    d.text((W // 2, 28), TITLE, font=_fit_text(d, TITLE, FONT_BOLD, 26, W - 30), fill=WHITE, anchor="mm")

    big = label.strip() or info["label"]
    d.text((W // 2, 140), big, font=_fit_text(d, big, FONT_BOLD, 92, W - 30),
           fill=RED if info["red"] else BLACK, anchor="mm")

    sub = f"{until} 복귀 예정" if until else info["sub"]
    d.text((W // 2, 222), sub, font=_fit_text(d, sub, FONT_REG, 26, W - 30), fill=BLACK, anchor="mm")

    d.line([20, 254, W - 20, 254], fill=BLACK, width=2)
    stamp = time.strftime("%m/%d %H:%M 갱신", time.localtime(updated or time.time()))
    d.text((W // 2, 276), stamp, font=_font(FONT_REG, 16), fill=BLACK, anchor="mm")
    return im


def convert_image(raw: bytes, fit="contain", dither=True):
    """임의의 이미지를 400x300 3색 인덱스 이미지로 변환."""
    src = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGBA")
        bg = Image.new("RGBA", src.size, (255, 255, 255, 255))
        src = Image.alpha_composite(bg, src)
    src = src.convert("RGB")

    if fit == "cover":
        img = ImageOps.fit(src, (W, H), Image.LANCZOS)
    else:
        img = Image.new("RGB", (W, H), (255, 255, 255))
        s = src.copy()
        s.thumbnail((W, H), Image.LANCZOS)
        img.paste(s, ((W - s.width) // 2, (H - s.height) // 2))

    pal = Image.new("P", (1, 1))
    pal.putpalette(_palette(MATCH_RGB))
    q = img.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)
    # 패딩 인덱스(>=3)는 모두 검정과 같은 색이므로 1로 정규화
    q = q.point(lambda i: i if i <= RED else BLACK)
    q.putpalette(_palette(PREVIEW_RGB))
    return q


def add_low_battery_banner(im):
    """화면 아래에 빨간 '배터리 부족' 띠. 꺼진 뒤에도 e-paper 에 남아 오래된 표시임을 알린다."""
    im = im.copy()
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 34, W - 1, H - 1], fill=RED)
    msg = "배터리 부족 · 표시가 최신이 아닐 수 있음"
    d.text((W // 2, H - 17), msg, font=_fit_text(d, msg, FONT_BOLD, 19, W - 20), fill=WHITE, anchor="mm")
    return im


def to_png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def load_png(data: bytes):
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


def frame_bytes(im) -> bytes:
    """ESP32 용: 흑 평면 15000B + 적 평면 15000B (MSB 우선, 1=잉크)."""
    idx = im.tobytes()
    blk = Image.frombytes("L", (W, H), bytes(255 if i == BLACK else 0 for i in idx)).convert("1")
    red = Image.frombytes("L", (W, H), bytes(255 if i == RED else 0 for i in idx)).convert("1")
    return blk.tobytes() + red.tobytes()
