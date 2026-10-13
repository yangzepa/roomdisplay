// ============================================================
//  e-paper 문패 케이스 초안 (WeAct 4.2" 3색 + TTGO T-Display + LiPo)
//  좌표: X=가로, Y=세로(아래가 0), Z=깊이(앞면 0 → 뒷면 +)
//  [MEASURE] 표시 값은 반드시 캘리퍼로 실측 후 수정
// ============================================================

part = "assembly";   // "shell" | "cover" | "assembly"

// ---------- e-paper 모듈 ----------
pcb_w   = 94.0;   // [MEASURE] WeAct 기판 가로
pcb_h   = 90.0;   // [MEASURE] WeAct 기판 세로
pcb_t   = 1.6;
panel_w = 91.0;   // 패널 외곽 (데이터시트 91 x 77 x 1.25)
panel_h = 77.0;
panel_t = 1.25;
tape_t  = 0.3;    // [MEASURE] 패널-기판 사이 양면테이프 두께
panel_x = (pcb_w - panel_w) / 2;  // [MEASURE] 기판 좌하단 기준 패널 위치
panel_y = 2.0;                    // [MEASURE]
active_w = 84.8;  // 표시 영역 (데이터시트)
active_h = 63.6;
active_x = (panel_w - active_w) / 2;  // 패널 좌하단 기준
active_y = 10.0;  // [MEASURE] FPC 쪽 테두리가 더 넓음 — 위/아래 확인
win_margin = 0.6; // 창을 표시 영역보다 살짝 크게

// ---------- 케이스 ----------
clr     = 0.5;    // 기판 둘레 여유
wall    = 4.0;    // 측벽 (모서리에 M2 나사 들어감)
front_t = 1.6;    // 앞판 두께
comp_d  = 10.0;   // 기판 뒷면 ~ 뒷판 안쪽면 공간 (배터리, T-Display)

// ---------- T-Display (기판 우하단 구석, USB가 오른쪽 벽) ----------
td_w = 52.0; td_h = 25.5; td_t = 8.0;    // [MEASURE] 핀 정리 후 두께
td_x = pcb_w - td_w; td_y = 0;          // 기판 좌표 기준
usb_w = 13.0; usb_h = 7.5; usb_z = 4.0; // usb_z: 뒷판 안쪽면에서 USB 중심까지 [MEASURE]
sw_side = "bottom";                      // 스위치 접근 구멍: "bottom" | "top" | "none"
sw_from_usb = 8.0;  sw_w = 10.0; sw_h = 5.0; sw_z = 4.0; // [MEASURE]

// ---------- 배터리 (603450 기준, 보호회로 포함 길이) ----------
bat_w = 54.0; bat_h = 35.0; bat_t = 6.5; // [MEASURE]
bat_x = 3.0;  bat_y = 32.0;
fence_t = 1.2; fence_hgt = 4.0;

// ---------- 뒷판 / 자석 / 나사 ----------
mag_d = 10.0; mag_t = 2.0;   // [MEASURE] 네오디뮴 원판
mag_inset = 13.0;
cover_t = mag_t + 0.6;
screw_pilot = 1.7;  screw_clear = 2.3;  screw_head = 4.2;  screw_depth = 8;
post_d = 4.0;  post_inset = 4.0;

$fn = 48;

// ---------- 파생 치수 ----------
in_w = pcb_w + 2*clr;
in_h = pcb_h + 2*clr;
W = in_w + 2*wall;
H = in_h + 2*wall;
stack = panel_t + tape_t;              // 앞판 안쪽면 ~ 기판 앞면
D = front_t + stack + pcb_t + comp_d;  // 본체 깊이
ox = wall + clr;  oy = wall + clr;     // 기판 좌하단의 케이스 좌표

module rrect(w, h, t, r=2) {
  linear_extrude(t) offset(r) offset(-r) square([w, h]);
}

module screw_pts() {
  for (p = [[wall/2, wall/2], [W-wall/2, wall/2], [wall/2, H-wall/2], [W-wall/2, H-wall/2]])
    translate(p) children();
}

// ================= 본체(앞판 + 측벽) =================
module shell() {
  difference() {
    rrect(W, H, D, 3);
    // 내부 공간
    translate([wall, wall, front_t]) cube([in_w, in_h, D]);
    // 표시 창 (앞쪽으로 45° 모따기)
    wx = ox + panel_x + active_x - win_margin;
    wy = oy + panel_y + active_y - win_margin;
    ww = active_w + 2*win_margin;
    wh = active_h + 2*win_margin;
    translate([0, 0, -0.01]) hull() {
      translate([wx, wy, front_t]) cube([ww, wh, 0.02]);
      translate([wx - front_t, wy - front_t, 0]) cube([ww + 2*front_t, wh + 2*front_t, 0.02]);
    }
    // 모서리 나사 구멍 (뒷면에서)
    screw_pts() translate([0, 0, D - screw_depth]) cylinder(d=screw_pilot, h=screw_depth + 1);
    // USB-C 구멍 (오른쪽 벽)
    translate([W - wall - 1, oy + td_y + td_h/2 - usb_w/2, D - usb_z - usb_h/2])
      cube([wall + 2, usb_w, usb_h]);
    // 스위치 접근 구멍
    if (sw_side != "none") {
      sx = ox + td_x + td_w - sw_from_usb - sw_w/2;
      if (sw_side == "bottom")
        translate([sx, -1, D - sw_z - sw_h/2]) cube([sw_w, wall + 2, sw_h]);
      else
        translate([sx, H - wall - 1, D - sw_z - sw_h/2]) cube([sw_w, wall + 2, sw_h]);
    }
  }
  // 기판 받침 턱: 기판 둘레 3mm 띠 중 패널이 없는 곳 (패널 두께만큼 높이)
  translate([0, 0, front_t]) linear_extrude(stack)
    difference() {
      translate([wall, wall]) square([in_w, in_h]);
      translate([ox + 3, oy + 3]) square([pcb_w - 6, pcb_h - 6]);
      translate([ox + panel_x - 0.5, oy + panel_y - 0.5]) square([panel_w + 1, panel_h + 1]);
    }
}

// ================= 뒷판 (출력 방향: 바깥면이 베드) =================
// 출력용: 케이스 좌표로 만든 뒷판을 Y 미러 → 뒤집어 조립하면 위치가 맞음
module cover() { translate([0, H, 0]) mirror([0, 1, 0]) cover_raw(); }

module cover_raw() {
  difference() {
    rrect(W, H, cover_t, 3);
    // 자석 포켓 (바깥면)
    for (p = [[mag_inset, mag_inset], [W-mag_inset, mag_inset], [mag_inset, H-mag_inset], [W-mag_inset, H-mag_inset]])
      translate([p.x, p.y, -0.01]) cylinder(d=mag_d + 0.2, h=mag_t + 0.1);
    // 나사 구멍 + 머리 자리
    screw_pts() {
      translate([0, 0, -1]) cylinder(d=screw_clear, h=cover_t + 2);
      translate([0, 0, -0.01]) cylinder(d=screw_head, h=1.3);
    }
  }
  translate([0, 0, cover_t]) {
    // 기판 누름 기둥 (T-Display와 겹치는 위치는 생략)
    for (p = [[post_inset, post_inset], [pcb_w-post_inset, post_inset],
              [post_inset, pcb_h-post_inset], [pcb_w-post_inset, pcb_h-post_inset]])
      if (!(p.x > td_x - post_d && p.y < td_y + td_h + post_d))
        translate([ox + p.x, oy + p.y, 0]) cylinder(d=post_d, h=comp_d);
    // 배터리 울타리
    translate([ox + bat_x - fence_t, oy + bat_y - fence_t, 0]) difference() {
      cube([bat_w + 2*fence_t, bat_h + 2*fence_t, fence_hgt]);
      translate([fence_t, fence_t, -1]) cube([bat_w, bat_h, fence_hgt + 2]);
      // 배선 출구 (오른쪽 가운데)
      translate([bat_w, bat_h/2 - 5, -1]) cube([fence_t + 2, 10, fence_hgt + 2]);
    }
    // T-Display 울타리 (왼쪽, 위쪽만 — 아래/오른쪽은 측벽)
    translate([ox + td_x - fence_t - 0.3, oy + td_y, 0]) cube([fence_t, td_h + 0.3, 3]);
    translate([ox + td_x - fence_t - 0.3, oy + td_y + td_h + 0.3, 0]) cube([td_w * 0.6, fence_t, 3]);
  }
}

// ================= 조립 미리보기 =================
module ghosts() {
  translate([ox + panel_x, oy + panel_y, front_t]) color("white", 0.8) cube([panel_w, panel_h, panel_t]);
  translate([ox, oy, front_t + stack]) color("black", 0.6) cube([pcb_w, pcb_h, pcb_t]);
  translate([ox + bat_x, oy + bat_y, D - bat_t]) color("silver", 0.8) cube([bat_w, bat_h, bat_t]);
  translate([ox + td_x, oy + td_y, D - td_t]) color("royalblue", 0.8) cube([td_w, td_h, td_t]);
}

if (part == "shell") shell();
else if (part == "cover") cover();
else {
  color("orange", 0.35) shell();
  ghosts();
  translate([0, H, D + cover_t]) rotate([180, 0, 0]) color("tomato", 0.5) cover();
}
