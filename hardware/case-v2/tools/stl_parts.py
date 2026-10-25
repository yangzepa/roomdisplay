"""STL 을 연결된 덩어리별로 나눠 bbox 를 출력한다(겹침 위치 찾기·치수 확인용).

사용: python3 stl_parts.py file.stl
"""
import struct
import sys


def load(fn):
    b = open(fn, "rb").read()
    if b[:5] == b"solid":
        tris, cur = [], []
        for line in b.decode(errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("vertex"):
                cur.append(tuple(map(float, line.split()[1:])))
                if len(cur) == 3:
                    tris.append(cur)
                    cur = []
        return tris
    n = struct.unpack("<I", b[80:84])[0]
    return [[struct.unpack("<12f", b[84 + i * 50:84 + i * 50 + 48])[3 * k + 3:3 * k + 6] for k in range(3)]
            for i in range(n)]


def main(fn):
    t = load(fn)
    print(len(t), "triangles")
    if not t:
        return
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            a = parent[a]
        return a

    for tr in t:
        ks = [tuple(round(c, 3) for c in p) for p in tr]
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
    groups = {}
    for tr in t:
        groups.setdefault(find(tuple(round(c, 3) for c in tr[0])), []).extend(tr)
    for g in sorted(groups.values(), key=len, reverse=True)[:15]:
        xs, ys, zs = zip(*g)
        print(f"X {min(xs):7.2f}..{max(xs):7.2f}  Y {min(ys):7.2f}..{max(ys):7.2f}  Z {min(zs):6.2f}..{max(zs):6.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
