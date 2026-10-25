"""STL 미리보기 렌더러 (numpy + Pillow, OpenGL 불필요).

OpenSCAD 의 PNG 출력이 헤드리스 Docker 에서 동작하지 않아 직접 만든 정사영 z-버퍼 렌더러.
면 음영 + 깊이 경계선으로 기술 도면 느낌의 이미지를 만든다.

사용: python3 render_stl.py scene.json out.png
scene.json: {"size":[1400,1050], "view":{"yaw":25,"pitch":-20}, "bg":[246,244,239],
             "objects":[{"stl":"front.stl","color":[240,160,80],
                         "rotate_x":{"deg":100,"y":108.5,"z":17.95}, "translate":[0,0,30]},
                        {"box":[x,y,z,w,h,d],"color":[...]}]}
"""
import json
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter


def load_stl(fn):
    b = open(fn, "rb").read()
    if b[:5] == b"solid" and b"facet" in b[:400]:
        v = []
        for line in b.decode(errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("vertex"):
                v.append([float(c) for c in line.split()[1:4]])
        return np.array(v, dtype=float).reshape(-1, 3, 3)
    n = struct.unpack("<I", b[80:84])[0]
    a = np.frombuffer(b[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return a["v"].astype(float).reshape(-1, 3, 3)


def box_tris(x, y, z, w, h, d):
    p = np.array([[x, y, z], [x + w, y, z], [x + w, y + h, z], [x, y + h, z],
                  [x, y, z + d], [x + w, y, z + d], [x + w, y + h, z + d], [x, y + h, z + d]])
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (2, 3, 7), (2, 7, 6), (1, 2, 6), (1, 6, 5), (3, 0, 4), (3, 4, 7)]
    return np.array([[p[i], p[j], p[k]] for i, j, k in f], dtype=float)


def rot_x(deg):
    r = np.radians(deg)
    return np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])


def rot_y(deg):
    r = np.radians(deg)
    return np.array([[np.cos(r), 0, np.sin(r)], [0, 1, 0], [-np.sin(r), 0, np.cos(r)]])


def render(scene, out):
    W, H = scene.get("size", [1400, 1050])
    tris, cols = [], []
    for o in scene["objects"]:
        t = load_stl(o["stl"]) if "stl" in o else box_tris(*o["box"])
        if "rotate_x" in o:   # 힌지 축(y, z)을 중심으로 X축 회전
            rx = o["rotate_x"]
            c = np.array([0, rx["y"], rx["z"]])
            t = (t - c) @ rot_x(rx["deg"]).T + c
        if "translate" in o:
            t = t + np.array(o["translate"])
        tris.append(t)
        cols.append(np.tile(np.array(o["color"], dtype=float), (len(t), 1)))
    T = np.concatenate(tris)
    C = np.concatenate(cols)
    # 보는 방향: 모델을 yaw(Y축) → pitch(X축) 회전 후 -Z 쪽에서 바라봄(z 작을수록 가까움)
    v = scene.get("view", {})
    R = rot_x(v.get("pitch", 0)) @ rot_y(v.get("yaw", 0))
    P = T @ R.T
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    L1 = np.array([-0.4, 0.6, -0.7]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.6, -0.2, -0.5]); L2 /= np.linalg.norm(L2)
    shade = 0.38 + 0.5 * np.abs(n @ L1) + 0.17 * np.abs(n @ L2)
    rgb = np.clip(C * shade[:, None], 0, 255)
    # 화면 맞춤
    xy = P[:, :, :2].reshape(-1, 2)
    lo, hi = xy.min(0), xy.max(0)
    pad = 0.06
    s = min(W * (1 - 2 * pad) / (hi[0] - lo[0]), H * (1 - 2 * pad) / (hi[1] - lo[1]))
    off = np.array([W, H]) / 2 - s * (lo + hi) / 2
    S = np.empty_like(P)
    S[:, :, 0] = P[:, :, 0] * s + off[0]
    S[:, :, 1] = H - (P[:, :, 1] * s + off[1])
    S[:, :, 2] = P[:, :, 2]
    zbuf = np.full((H, W), np.inf)
    img = np.zeros((H, W, 3))
    img[:] = scene.get("bg", [246, 244, 239])
    ids = np.full((H, W), -1)
    for i in range(len(S)):
        a, b, c = S[i]
        x0, x1 = int(max(0, np.floor(min(a[0], b[0], c[0])))), int(min(W - 1, np.ceil(max(a[0], b[0], c[0]))))
        y0, y1 = int(max(0, np.floor(min(a[1], b[1], c[1])))), int(min(H - 1, np.ceil(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        w1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        z = w0 * a[2] + w1 * b[2] + w2 * c[2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = m & (z < sub)
        sub[upd] = z[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = rgb[i]
        ids[y0:y1 + 1, x0:x1 + 1][upd] = i
    # 윤곽선: 깊이가 크게 바뀌거나 면 방향이 바뀌는 곳
    zf = np.where(np.isinf(zbuf), zbuf[~np.isinf(zbuf)].max() + 50 if (~np.isinf(zbuf)).any() else 0, zbuf)
    dz = np.maximum(np.abs(np.diff(zf, axis=0, prepend=zf[:1])), np.abs(np.diff(zf, axis=1, prepend=zf[:, :1])))
    nrm = np.zeros((H, W, 3))
    valid = ids >= 0
    nrm[valid] = n[ids[valid]]
    dn = np.maximum(np.linalg.norm(np.diff(nrm, axis=0, prepend=nrm[:1]), axis=2),
                    np.linalg.norm(np.diff(nrm, axis=1, prepend=nrm[:, :1]), axis=2))
    edge = (dz > 1.2 / s * 3) | (dn > 0.35)
    img[edge] = img[edge] * 0.35
    Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.SMOOTH).save(out)


if __name__ == "__main__":
    render(json.load(open(sys.argv[1])), sys.argv[2])
