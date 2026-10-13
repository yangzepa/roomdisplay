"""연구실 e-paper 문패 서버.

웹 UI: 갤러리에서 이미지(상태 화면 또는 업로드 그림)를 클릭하면 문패로 전송.
ESP32: /api/wait 롱폴링 → seq 변경 시 /frame.bin(30000B) 수신.
"""
import asyncio
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import render

DATA = Path(os.environ.get("DATA_DIR", "/data"))
IMG_DIR = DATA / "images"
STATE_FILE = DATA / "state.json"
POOL_FILE = DATA / "pool.json"      # {"order": ["status:in", "image:<id>", ...], "hidden": ["status:lecture", ...]}
BAT_LOG = DATA / "battery.csv"      # t,mv,rssi — 5분에 한 번씩 기록
BAT_LOG_EVERY = 300
CHARGE_FILE = DATA / "charge.json"
USB_MV = 4300                       # 이 이상이면 USB 전원(ADC 에 VBUS 가 읽힘)
BAT_MAH = float(os.environ.get("BAT_MAH", "560"))        # 셀 용량
CHARGE_MA = float(os.environ.get("CHARGE_MA", "400"))    # 충전 IC 정전류(추정치, 실측으로 보정)
CALIB_FILE = DATA / "calib.json"    # 만충 직후 실측으로 잡은 ADC 게인 보정
FULL_REST_MV = 4180                 # 만충 후 소부하 상태의 기대 전압
EVENTS_FILE = DATA / "events.json"  # 배터리 교체·펌웨어 변경·보정 등 기록에 대한 주석
EVENT_TYPES = {"battery": "배터리 교체", "firmware": "펌웨어", "calib": "보정", "note": "메모"}


def load_events():
    try:
        return sorted(json.loads(EVENTS_FILE.read_text()), key=lambda e: e["t"])
    except (OSError, ValueError):
        return []


def bat_installed():
    """현재 셀 장착 시각 = 마지막 '배터리 교체' 이벤트. 없으면 환경변수(구버전 호환)."""
    swaps = [e["t"] for e in load_events() if e["type"] == "battery"]
    return swaps[-1] if swaps else int(os.environ.get("BAT_INSTALLED", "0"))
LOW_PCT, LOW_CLEAR_PCT = 8, 15      # 배터리 부족 경고 켜기/끄기 기준(보정 후 잔량 %)
WAIT_SEC = 50          # 기본 롱폴링 대기(초). 문패가 w= 로 더 길게 요청 가능
WAIT_MAX = 300
MAX_UPLOAD = 25 * 1024 * 1024
STATIC = Path(__file__).parent / "static"

IMG_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="roomdisplay")
cond = asyncio.Condition()
device = {"seen": 0.0, "ip": "", "wait": WAIT_SEC, "bat_mv": None, "rssi": None, "uptime": None, "bat_t": 0.0,
          "low": False}
_last_log = {"t": 0.0}
_recent_bat = []


def record_device(request, bat=None, rssi=None, up=None):
    """문패 보고 기록. 배터리 부족 상태가 바뀌면 True(화면 다시 그려야 함)."""
    now = time.time()
    device.update(seen=now, ip=request.client.host if request.client else "")
    if bat is None:
        return False
    device.update(bat_mv=bat, rssi=rssi, uptime=up, bat_t=now)
    track_charge(bat, now)
    # ADC 값이 송신 순간 처지는 일이 잦아 최근 3회 중앙값으로 판단, 히스테리시스 적용
    _recent_bat[:] = (_recent_bat + [bat])[-3:]
    med = sorted(_recent_bat)[len(_recent_bat) // 2]
    pct = battery_pct(med)
    was = device["low"]
    if med >= USB_MV or pct >= LOW_CLEAR_PCT:
        device["low"] = False
    elif len(_recent_bat) == 3 and pct <= LOW_PCT:
        device["low"] = True
    changed = device["low"] != was
    if now - _last_log["t"] >= BAT_LOG_EVERY:
        _last_log["t"] = now
        with BAT_LOG.open("a") as f:
            f.write(f"{int(now)},{bat},{rssi if rssi is not None else ''}\n")
    return changed


def discharge_runs(rows):
    """배터리 로그를 방전 구간(USB 아님, 20분 넘는 공백 없음)으로 나눔."""
    runs, cur = [], []
    for t, mv in rows:
        if cur and (t - cur[-1][0] > 1200 or (mv >= USB_MV) != (cur[-1][1] >= USB_MV)):
            runs.append(cur)
            cur = []
        cur.append((t, mv))
    if cur:
        runs.append(cur)
    return [r for r in runs if r[0][1] < USB_MV]


def last_full_run(rows):
    """가장 최근의 '거의 만충(≥90%)에서 시작해 방전으로 끝난' 구간. 1회 충전 지속 시간의 기준값."""
    runs = discharge_runs([(t, mv) for t, mv in rows if t >= bat_installed()])
    for r in reversed(runs[:-1] if runs and time.time() - runs[-1][-1][0] < 1200 else runs):
        if battery_pct(r[0][1]) >= 90 and battery_pct(min(mv for _, mv in r[-3:])) <= 15:
            return {"start": r[0][0], "end": r[-1][0], "hours": round((r[-1][0] - r[0][0]) / 3600, 1),
                    "start_mv": r[0][1], "end_mv": r[-1][1]}
    return None

def estimate_life(hist, window_h=6, empty_mv=3500):
    """최근 window_h 시간의 배터리 구간(USB 제외) 기울기로 남은 시간 추정. 데이터 부족 시 None."""
    pts = [(t, mv) for t, mv, _ in hist if mv < USB_MV and t >= time.time() - window_h * 3600]
    # USB 를 뽑은 직후의 급강하 구간을 피하려고 마지막 USB 기록 이후 10분은 제외
    usb_t = max((t for t, mv, _ in hist if mv >= USB_MV), default=0)
    pts = [(t, mv) for t, mv in pts if t >= usb_t + 600]
    if len(pts) < 4 or pts[-1][0] - pts[0][0] < 1800:
        return None
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    mv_ = sum(v for _, v in pts) / n
    den = sum((t - mt) ** 2 for t, _ in pts)
    slope = sum((t - mt) * (v - mv_) for t, v in pts) / den * 3600   # mV/h
    if slope >= -0.5:
        return {"mv_per_h": round(slope, 1), "hours_left": None}
    empty_raw = empty_mv / _gain()
    return {"mv_per_h": round(slope, 1), "hours_left": max(0.0, round((pts[-1][1] - empty_raw) / -slope, 1)),
            "span_h": round((pts[-1][0] - pts[0][0]) / 3600, 1)}


def _calib():
    try:
        return json.loads(CALIB_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _gain():
    """ADC 전압 게인(멀티미터 실측 기준). 원시값 × gain = 실제 셀 전압."""
    return float(_calib().get("gain", 1.0))


def _full_mv():
    """이 보드 충전 회로의 실제 만충 전압(보정 후). 잔량 100% 기준."""
    return float(_calib().get("full_mv", 4200))


def _save_calib(**kw):
    c = _calib()
    c.update(kw, t=time.time())
    CALIB_FILE.write_text(json.dumps(c, ensure_ascii=False))


def calibrate_full(raw_mv, now, source):
    """만충 직후 원시 전압으로 100% 기준 전압 갱신. 게인(전압 정확도)은 건드리지 않음."""
    full = raw_mv * _gain()
    if not 3950 <= full <= 4300:
        return None
    _save_calib(full_mv=round(full), full_source=source, full_at=now)
    return round(full)


def _load_charge():
    try:
        return json.loads(CHARGE_FILE.read_text())
    except (OSError, ValueError):
        return {"active": False}


def _bat_log():
    if not BAT_LOG.exists():
        return []
    rows = []
    for line in BAT_LOG.read_text().splitlines():
        p = line.split(",")
        if len(p) >= 2 and p[0] and p[1]:
            rows.append((int(p[0]), int(p[1])))
    return rows


def track_charge(bat, now):
    """USB 연결/해제 전이를 감지해 충전 세션을 기록."""
    ch = _load_charge()
    usb = bat >= USB_MV
    if usb and not ch.get("active"):
        rows = _bat_log()
        start = now
        for t, mv in reversed(rows):            # 로그 끝의 연속 USB 구간 시작 시각
            if mv < USB_MV:
                break
            start = t
        before = [(t, mv) for t, mv in rows if mv < USB_MV and t <= start]
        pre = before[-1] if before and start - before[-1][0] < 2 * 3600 else None
        ch = {"active": True, "start": start, "pre_mv": pre[1] if pre else None,
              "start_pct": battery_pct(pre[1]) if pre else 0}
        CHARGE_FILE.write_text(json.dumps(ch))
    elif not usb and ch.get("active"):
        est = charge_estimate(ch, now)
        ch.update(active=False, end=now, end_est_pct=est["pct"], first_mv=bat)
        # 완충 추정 후 30분 이상 더 꽂혀 있었다면 확실히 만충 → 뽑은 직후 전압으로 게인 보정
        if est["pct"] >= 100 and est["full_since_min"] >= 30:
            ch["calibrated_full_mv"] = calibrate_full(bat, now, "auto-unplug")
        CHARGE_FILE.write_text(json.dumps(ch))


def charge_profile():
    """C-rate 에 따른 충전 곡선 근사.
    전류가 작을수록(저 C-rate) 정전류 구간이 더 높은 잔량까지 이어지고, 정전압 구간은 남은 용량/평균전류로 길어진다."""
    crate = CHARGE_MA / BAT_MAH
    cc_end = 80 + 15 * (1 - min(1.0, crate / 0.5))            # 1C≈80%, 0.06C≈93%
    taper_h = (100 - cc_end) / 100 * BAT_MAH / (CHARGE_MA * 0.5)  # 정전압 구간 평균 전류 ≈ 정전류의 절반
    return crate, cc_end, taper_h


def charge_estimate(ch, now=None):
    """정전류(→cc_end%) + 정전압(cc_end→100%) 근사로 충전 진행률 추정."""
    now = now or time.time()
    h = (now - ch["start"]) / 3600
    p0 = ch.get("start_pct") or 0
    crate, cc_end, taper_h = charge_profile()
    cc_rate = crate * 100                                       # %/h
    h_cc = max(0.0, (cc_end - p0) / cc_rate)
    t_h = taper_h * min(1.0, (100 - max(p0, cc_end)) / (100 - cc_end))   # 이미 정전압 구간에서 시작한 경우 비례 축소
    full_h = h_cc + t_h
    if h <= h_cc:
        pct = p0 + cc_rate * h
    else:
        start_t = max(p0, cc_end)
        pct = start_t + (100 - start_t) * min(1.0, (h - h_cc) / t_h if t_h else 1.0)
    return {"pct": round(min(100, pct)), "minutes_left": round(max(0.0, full_h - h) * 60), "elapsed_min": round(h * 60),
            "full_since_min": max(0, round((h - full_h) * 60)),
            "start": ch["start"], "start_pct": p0, "pre_known": ch.get("pre_mv") is not None,
            "charge_ma": CHARGE_MA, "bat_mah": BAT_MAH}


def battery_pct(mv):
    """LiPo 개방전압 기준 대략적 잔량(%). 부하/온도에 따라 오차 큼."""
    if mv is None:
        return None
    # 실제 전압으로 보정한 뒤, 이 보드의 만충 전압을 4200 으로 늘려 표준 LiPo 곡선에 맞춤
    mv = mv * _gain()
    mv = 3300 + (mv - 3300) * (4200 - 3300) / (_full_mv() - 3300)
    table = [(4200, 100), (4100, 90), (4000, 80), (3900, 65), (3800, 50), (3750, 40),
             (3700, 30), (3650, 20), (3600, 12), (3500, 5), (3300, 0)]
    if mv >= 4200:
        return 100
    for (v1, p1), (v2, p2) in zip(table, table[1:]):
        if mv >= v2:
            return round(p2 + (p1 - p2) * (mv - v2) / (v1 - v2))
    return 0

state = {"current": {"kind": "status", "state": "in", "until": "", "label": ""}, "seq": 1, "updated": time.time()}
if STATE_FILE.exists():
    try:
        state.update(json.loads(STATE_FILE.read_text()))
    except (ValueError, OSError):
        pass


# ---------- 이미지 저장소 ----------

def _meta_path(iid):
    return IMG_DIR / f"{iid}.json"


def _check_id(iid):
    if not iid.isalnum() or not _meta_path(iid).exists():
        raise HTTPException(404, "no such image")


def list_images():
    metas = []
    for p in IMG_DIR.glob("*.json"):
        try:
            metas.append(json.loads(p.read_text()))
        except ValueError:
            continue
    return sorted(metas, key=lambda m: m["created"], reverse=True)


def _load_pool():
    try:
        return json.loads(POOL_FILE.read_text())
    except (OSError, ValueError):
        return {"order": [], "hidden": []}


def _save_pool(pool):
    POOL_FILE.write_text(json.dumps(pool, ensure_ascii=False))


def pool_items():
    """문패 풀 = 업로드한 그림들. 저장된 순서 → 순서에 없는 새 그림은 뒤에(최신순).
    (예전의 글자 상태 카드는 풀에서 뺐다. 상태는 그림에 연결해서 쓴다.)"""
    pool = _load_pool()
    items = {f"image:{m['id']}": {"key": f"image:{m['id']}", "kind": "image", **m} for m in list_images()}
    ordered = [items.pop(k) for k in pool["order"] if k in items]
    rest = sorted(items.values(), key=lambda i: -i.get("created", 0))
    return ordered + rest


def state_images():
    """상태 키 → 연결된 그림 id. 그림 메타의 'state' 필드로 지정."""
    out = {}
    for m in sorted(list_images(), key=lambda m: m.get("state_at", 0)):
        if m.get("state") in render.STATES:
            out[m["state"]] = m["id"]
    return out


def pool_add_front(key):
    pool = _load_pool()
    order = [k for k in (pool["order"] or [i["key"] for i in pool_items()]) if k != key]
    pool["order"] = [key] + order
    pool["hidden"] = [k for k in pool["hidden"] if k != key]
    _save_pool(pool)


def displayed_image_id(cur):
    """이 current 가 실제로 보여줄 그림 id. 없으면 None(글자 상태 화면)."""
    iid = cur.get("image") if cur.get("kind") == "status" else cur.get("id")
    return iid if iid and _meta_path(iid).exists() else None


def current_image():
    cur = state["current"]
    iid = displayed_image_id(cur)
    if iid:
        im = render.load_png((IMG_DIR / f"{iid}.png").read_bytes())
    else:   # 상태에 연결된 그림이 없을 때만 글자 화면으로 대체
        im = render.render_status(cur.get("state", "in"), cur.get("until", ""), cur.get("label", ""), state["updated"])
    if device["low"]:
        im = render.add_low_battery_banner(im)
    return im


async def set_current(cur, force=False):
    """표시 대상을 바꾼다. 보여줄 그림이 지금과 같으면 seq 를 올리지 않아 문패를 다시 그리지 않는다
    (자동화가 같은 상태를 반복 전송해도 e-paper 갱신·배터리 소모가 없음)."""
    async with cond:
        old = state["current"]
        same = not force and displayed_image_id(old) == displayed_image_id(cur) and (
            displayed_image_id(cur) is not None or
            (old.get("state"), old.get("label", ""), old.get("until", "")) == (cur.get("state"), cur.get("label", ""), cur.get("until", "")))
        if same:
            state["current"] = cur          # 의미(상태 이름 등)만 갱신, 화면은 그대로
        else:
            state.update(current=cur, seq=state["seq"] + 1, updated=time.time())
            cond.notify_all()
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))
    return {**public_state(), "refreshed": not same}


def public_state():
    return {**state, "device_seen": device["seen"], "device_ip": device["ip"]}


@app.get("/api/device")
def device_info(days: float = 7):
    since = time.time() - days * 86400
    hist = []
    if BAT_LOG.exists():
        for line in BAT_LOG.read_text().splitlines():
            t, mv, rssi = (line.split(",") + ["", ""])[:3]
            if t and float(t) >= since:
                hist.append([int(t), int(mv), int(rssi) if rssi else None])
    mv = device["bat_mv"]
    ch = _load_charge()
    full = last_full_run(_bat_log())
    if mv and mv < USB_MV and _recent_bat:          # 송신 순간 처짐 노이즈 완화: 최근 3회 중앙값
        mv = sorted(_recent_bat)[len(_recent_bat) // 2]
    pct = battery_pct(mv)
    by_run = round(full["hours"] * pct / 100, 1) if full and pct is not None and mv and mv < USB_MV else None
    return {**device, "bat_mv": round(mv * _gain()) if mv else mv, "bat_raw_mv": device["bat_mv"], "bat_pct": pct, "est": estimate_life(hist), "gain": _gain(), "full_mv": _full_mv(),
            "last_full": full, "hours_left_by_run": by_run,
            "charge": charge_estimate(ch) if ch.get("active") and mv and mv >= USB_MV else None, "usb": bool(device["bat_mv"] and device["bat_mv"] >= USB_MV),
            "online": time.time() - device["seen"] < device["wait"] + 40, "history": [[t, round(v * _gain()), r] for t, v, r in hist]}


def png(data):
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})


# ---------- 웹 UI / API ----------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/state")
def get_state():
    return public_state()


@app.get("/api/statuses")
def statuses():
    """자동화가 쓰는 상태 이름과, 각 상태에 연결된 그림."""
    bound = state_images()
    return [{"key": k, "label": v["label"], "image": bound.get(k)} for k, v in render.STATES.items()]


@app.get("/api/preview/status.png")
def preview_status(state_key: str = "in", until: str = "", label: str = ""):
    if state_key not in render.STATES:
        raise HTTPException(400, "unknown state")
    return png(render.to_png(render.render_status(state_key, until[:10], label[:20])))


@app.get("/api/current.png")
@app.get("/preview.png")
def preview_current():
    return png(render.to_png(current_image()))


class ShowReq(BaseModel):
    kind: str
    state: str = "in"
    until: str = ""
    label: str = ""
    id: str = ""


@app.post("/api/show")
async def show(req: ShowReq):
    if req.kind == "status":
        if req.state not in render.STATES:
            raise HTTPException(400, "unknown state")
        return await set_current({"kind": "status", "state": req.state, "until": req.until[:10],
                                  "label": req.label[:20], "image": state_images().get(req.state)})
    if req.kind == "image":
        _check_id(req.id)
        meta = json.loads(_meta_path(req.id).read_text())
        if meta.get("state") in render.STATES:
            # 상태에 연결된 그림을 직접 누른 경우: 자동화가 같은 상태로 판정해도 다시 그리지 않도록 상태 형태로 저장
            return await set_current({"kind": "status", "state": meta["state"], "until": "", "label": "", "image": req.id})
        return await set_current({"kind": "image", "id": req.id})
    raise HTTPException(400, "kind must be status or image")


class EventReq(BaseModel):
    type: str = "note"
    text: str
    t: float | None = None


@app.get("/api/events")
def get_events():
    return load_events()


@app.post("/api/events")
def add_event(req: EventReq):
    if req.type not in EVENT_TYPES or not req.text.strip():
        raise HTTPException(400, "type must be one of " + ",".join(EVENT_TYPES))
    ev = load_events()
    e = {"t": req.t or time.time(), "type": req.type, "text": req.text.strip()[:300]}
    ev.append(e)
    EVENTS_FILE.write_text(json.dumps(sorted(ev, key=lambda x: x["t"]), ensure_ascii=False, indent=1))
    return e


@app.get("/api/images")
def images():
    return list_images()


@app.get("/api/pool")
def get_pool():
    pool = _load_pool()
    hidden = [{"key": k, "name": render.STATES[k.split(":", 1)[1]]["label"]}
              for k in pool["hidden"] if k.split(":", 1)[1] in render.STATES]
    return {"items": pool_items(), "hidden": hidden}


class OrderReq(BaseModel):
    order: list[str]


@app.post("/api/pool/order")
def set_order(req: OrderReq):
    pool = _load_pool()
    pool["order"] = req.order[:1000]
    _save_pool(pool)
    return {"ok": True}


@app.delete("/api/pool/{key}")
def pool_remove(key: str):
    kind, _, ident = key.partition(":")
    if kind == "image":
        return delete_image(ident)
    if kind != "status" or ident not in render.STATES:
        raise HTTPException(404, "no such item")
    pool = _load_pool()
    if key not in pool["hidden"]:
        pool["hidden"].append(key)
    _save_pool(pool)
    return {"hidden": key}


@app.post("/api/pool/{key}/restore")
def pool_restore(key: str):
    if key.split(":", 1)[-1] not in render.STATES:
        raise HTTPException(404, "no such item")
    pool_add_front(key)
    return {"restored": key}


@app.post("/api/images")
async def upload(file: UploadFile = File(...), fit: str = Form("contain"), dither: bool = Form(True),
                 show: bool = Form(False), name: str = Form("")):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "too large")
    fit = "cover" if fit == "cover" else "contain"
    try:
        im = render.convert_image(raw, fit, dither)
    except Exception as e:
        raise HTTPException(400, f"이미지를 열 수 없습니다: {e}")
    iid = secrets.token_hex(6)
    ext = Path(file.filename or "").suffix.lower()[:6] or ".img"
    (IMG_DIR / f"{iid}.orig{ext}").write_bytes(raw)
    (IMG_DIR / f"{iid}.png").write_bytes(render.to_png(im))
    meta = {"id": iid, "name": (name or file.filename or iid)[:80], "created": time.time(),
            "fit": fit, "dither": dither, "orig": f"{iid}.orig{ext}"}
    _meta_path(iid).write_text(json.dumps(meta, ensure_ascii=False))
    pool_add_front(f"image:{iid}")
    if show:
        await set_current({"kind": "image", "id": iid})
    return meta


class ReconvertReq(BaseModel):
    fit: str = "contain"
    dither: bool = True


@app.post("/api/images/{iid}/reconvert")
async def reconvert(iid: str, req: ReconvertReq):
    _check_id(iid)
    meta = json.loads(_meta_path(iid).read_text())
    raw = (IMG_DIR / meta["orig"]).read_bytes()
    meta["fit"] = "cover" if req.fit == "cover" else "contain"
    meta["dither"] = req.dither
    (IMG_DIR / f"{iid}.png").write_bytes(render.to_png(render.convert_image(raw, meta["fit"], meta["dither"])))
    _meta_path(iid).write_text(json.dumps(meta, ensure_ascii=False))
    if displayed_image_id(state["current"]) == iid:   # 표시 중인 그림이면 문패도 갱신
        await set_current(state["current"], force=True)
    return meta


class MetaReq(BaseModel):
    name: str | None = None
    state: str | None = None     # "" 이면 연결 해제


@app.post("/api/images/{iid}/meta")
async def image_meta(iid: str, req: MetaReq):
    _check_id(iid)
    meta = json.loads(_meta_path(iid).read_text())
    if req.name is not None and req.name.strip():
        meta["name"] = req.name.strip()[:80]
    if req.state is not None:
        if req.state and req.state not in render.STATES:
            raise HTTPException(400, "unknown state")
        if req.state:   # 한 상태에는 그림 하나만 — 기존 연결 해제
            for m in list_images():
                if m.get("state") == req.state and m["id"] != iid:
                    m.pop("state", None)
                    _meta_path(m["id"]).write_text(json.dumps(m, ensure_ascii=False))
            meta.update(state=req.state, state_at=time.time())
        else:
            meta.pop("state", None)
    _meta_path(iid).write_text(json.dumps(meta, ensure_ascii=False))
    # 지금 그 상태를 표시 중이면 새 그림으로 바로 반영
    cur = state["current"]
    if cur.get("kind") == "status":
        await set_current({**cur, "image": state_images().get(cur.get("state"))})
    return meta


@app.get("/api/images/{iid}/preview.png")
def image_preview(iid: str):
    _check_id(iid)
    return FileResponse(IMG_DIR / f"{iid}.png", media_type="image/png")


@app.get("/api/images/{iid}/original")
def image_original(iid: str):
    _check_id(iid)
    meta = json.loads(_meta_path(iid).read_text())
    return FileResponse(IMG_DIR / meta["orig"])


@app.delete("/api/images/{iid}")
def delete_image(iid: str):
    _check_id(iid)
    meta = json.loads(_meta_path(iid).read_text())
    for f in (meta["orig"], f"{iid}.png", f"{iid}.json"):
        (IMG_DIR / f).unlink(missing_ok=True)
    return {"deleted": iid}


# ---------- ESP32 ----------

RESET_REASONS = {1: "전원 켜짐", 3: "소프트웨어 재시작(자가 복구)", 4: "예외/패닉", 5: "인터럽트 워치독",
                 6: "태스크 워치독", 7: "기타 워치독", 8: "딥슬립 복귀", 9: "브라운아웃(전압 부족)"}


@app.get("/api/wait")
async def wait(request: Request, seq: int = 0, w: int = WAIT_SEC, bat: int | None = None,
               rssi: int | None = None, up: int | None = None,
               rr: int | None = None, nf: int | None = None, ds: int | None = None):
    w = max(5, min(w, WAIT_MAX))
    device["wait"] = w
    if rr is not None:   # 펌웨어 진단값: 부팅 원인, 누적 실패, 마지막 WiFi 끊김 사유
        device.update(reset_reason=RESET_REASONS.get(rr, f"코드 {rr}"), fails=nf, disc_reason=ds)
    if record_device(request, bat, rssi, up):
        # 배터리 부족 경고 띠를 붙이거나 떼도록 화면 갱신 유도
        async with cond:
            state["seq"] += 1
            STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))
            cond.notify_all()
    async with cond:
        try:
            await asyncio.wait_for(cond.wait_for(lambda: state["seq"] != seq), w)
        except asyncio.TimeoutError:
            pass
        return JSONResponse({"seq": state["seq"], "updated": state["updated"]})


@app.get("/frame.bin")
def frame(request: Request):
    record_device(request)
    seq = state["seq"]
    body = render.frame_bytes(current_image())
    return Response(body, media_type="application/octet-stream", headers={"X-Seq": str(seq)})
