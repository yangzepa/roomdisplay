// ============================================================
//  roomdisplay 2.0 케이스 — WeAct 4.2" 3색 e-paper + FireBeetle 2 ESP32-C5-U + LiPo
//  좌표: X=가로, Y=세로(아래가 0), Z=깊이(앞면 0 → 문 쪽 +)
//
//  구성: 앞판(front)  — 표시 창, e-paper 스냅 탭, 안테나 칸, USB-C 구멍, 힌지 마디(짝수)
//        뒷판(cover)  — 자석 포켓, 보드 레일, 배터리 울타리, 스냅 훅, 힌지 마디(홀수)
//  힌지 핀: 1.75mm 필라멘트 토막(또는 펼친 클립)을 옆에서 끼움. 나사 없음.
//  잠금:   뒷판 스냅 훅 2개가 앞판 바닥벽 구멍에 걸림. 구멍으로 핀을 넣어 누르면 풀림.
//
//  [MEASURE] 표시는 실측해서 고칠 값. 1.0에서 실제 출력·장착이 확인된 전면부 치수는 그대로 이어받음.
// ============================================================

part = "assembly";   // "front" | "cover" | "assembly" | "open" | "exploded" | "print_front" | "print_cover"
open_angle = 100;    // "open" 미리보기의 뒷판 대비 앞판 열림 각도

// ---------- e-paper 모듈 (1.0과 동일) ----------
pcb_w   = 94.0;   pcb_h = 90.0;  pcb_t = 1.6;
panel_w = 91.0;   panel_h = 77.0; panel_t = 1.25;
tape_t  = 0.3;
panel_x = (pcb_w - panel_w) / 2;  panel_y = 2.0;
active_w = 84.8;  active_h = 63.6;
active_x = (panel_w - active_w) / 2;  active_y = 10.0;
win_margin = 0.6;

// ---------- 케이스 ----------
clr     = 0.5;    // 기판 둘레 여유
wall    = 4.0;    // 측벽
front_t = 1.6;    // 앞판 두께
chin_h  = 14.0;   // 표시부 아래 안테나 칸 높이 (e-paper 기판 뒤를 피해 안테나를 앞면에 붙이는 자리)
comp_d  = 13.5;   // e-paper 기판 뒷면 ~ 뒷판 안쪽면: 기판 뒤 부품 여유 3 + 배터리 두께 10 + 0.5
cover_t = 4.2;    // 뒷판 두께 (자석 3mm + 바닥 1.0 + 여유)

// ---------- 배터리 [MEASURE] ----------
bat_w = 50.0; bat_h = 70.0; bat_t = 10.0;   // 3500mAh 셀 실측값으로 교체 (가로 × 세로 × 두께)
bat_y = 22.0;                               // 뒷판에서 배터리 아래쪽 위치
fence_t = 1.6; fence_hgt = 5.0;

// ---------- 보드: FireBeetle 2 ESP32-C5-U (25.4 × 60) ----------
brd_w = 25.4; brd_h = 60.0; brd_t = 1.6;
brd_stand = 1.5;          // 보드 밑 받침 높이
rail_t = 1.6; rail_lip = 0.8;
usb_w = 12.5; usb_h = 7.0; // USB-C 구멍 (플러그 몸통까지 들어가게 넉넉히)
usb_skin = 1.6;           // USB 쪽 바닥벽 남은 두께 (플러그 삽입 깊이 확보)

// ---------- 안테나 (동봉 2.4GHz FPC) [MEASURE] ----------
ant_w = 45.0; ant_h = 12.0;   // FPC 안테나 크기에 맞춰 조정
ant_rim = 0.8; ant_rim_h = 0.8;

// ---------- 자석 ----------
mag_d = 10.0; mag_t = 3.0;            // 네오디뮴 Ø10 × 3
mag_cols = [16, 40, 63, 87];          // X 위치
mag_rows = [18, 44, 70, 96];          // Y 위치 (4 × 4 = 16개)

// ---------- 힌지 ----------
hr = 4.5;          // 힌지 마디 반지름
pin_d = 2.0;       // 1.75mm 필라멘트용 구멍
nseg = 5;          // 마디 수 (앞판 0,2,4 / 뒷판 1,3)
hgap = 0.5;        // 마디 사이 틈
hclr = 0.5;        // 회전 여유

// ---------- 스냅 훅 (뒷판 → 앞판 바닥벽) ----------
hook_x = [20, 52];    // 훅 X 중심
hook_w = 8.0; hook_t = 1.6; hook_L = 13.0; barb = 1.2; barb_len = 2.6;

// ---------- e-paper 스냅 탭 (앞판 좌우 옆벽) ----------
tab_w = 8.0; tab_t = 1.6; tab_gap = 0.6; tab_bump = 1.3;

$fn = 48;

// ---------- 파생 치수 ----------
in_w = pcb_w + 2*clr;
in_h = pcb_h + 2*clr + chin_h;
W = in_w + 2*wall;
H = in_h + 2*wall;
stack = panel_t + tape_t;
D = front_t + stack + pcb_t + comp_d;    // 앞판 깊이(뒷판 안쪽면까지)
ox = wall + clr;                        // e-paper 기판 좌하단
oy = wall + chin_h + clr;
pcb_back = front_t + stack + pcb_t;      // e-paper 기판 뒷면 z
ya = H - hr;                            // 힌지 축 y
za = D + cover_t - hr;                  // 힌지 축 z (뒷면과 같은 평면까지만)
seg = W / nseg;
function seg_x0(i) = i*seg + (i > 0 ? hgap/2 : 0);
function seg_x1(i) = (i+1)*seg - (i < nseg-1 ? hgap/2 : 0);

// 보드 위치(뒷판 기준): 오른쪽, USB 끝이 바닥벽 안으로 들어가 USB 쪽 벽은 usb_skin만 남김
rim_t = 1.2; rim_h = 2.5; rim_clr = 0.3;
rim_in_r = W - wall - rim_clr - rim_t;
brd_x1 = rim_in_r - 0.5 - rail_t - 0.3;
brd_x0 = brd_x1 - brd_w;
brd_y0 = usb_skin;
bat_x0 = wall + rim_clr + rim_t + 0.5 + fence_t + 0.4;

echo(str("외형 W×H×(D+cover) = ", W, " × ", H, " × ", D + cover_t, " mm"));

module rrect(w, h, t, r=2) { linear_extrude(t) offset(r) offset(-r) square([w, h]); }
module xcyl(x0, x1, r, y, z) { translate([x0, y, z]) rotate([0, 90, 0]) cylinder(r=r, h=x1-x0); }

// ================= 앞판 =================
module front() {
  difference() {
    union() {
      difference() {
        rrect(W, H, D, 3);
        translate([wall, wall, front_t]) cube([in_w, in_h, D]);
      }
      // 기판 받침 턱 (1.0과 동일: 기판 둘레 3mm 띠 중 패널이 없는 곳)
      translate([0, 0, front_t]) linear_extrude(stack) difference() {
        translate([wall, oy - clr]) square([in_w, pcb_h + 2*clr]);
        translate([ox + 3, oy + 3]) square([pcb_w - 6, pcb_h - 6]);
        translate([ox + panel_x - 0.5, oy + panel_y - 0.5]) square([panel_w + 1, panel_h + 1]);
      }
      // 안테나 칸: 앞판 안쪽면의 FPC 안테나 가이드 테두리
      translate([W/2 - ant_w/2 - ant_rim, wall + 1 - ant_rim, front_t - 0.01]) difference() {
        cube([ant_w + 2*ant_rim, ant_h + 2*ant_rim, ant_rim_h + 0.01]);
        translate([ant_rim, ant_rim, -1]) cube([ant_w, ant_h, ant_rim_h + 2]);
        translate([ant_rim + ant_w/2 - 4, -1, -1]) cube([8, ant_rim + 2, ant_rim_h + 2]);  // 케이블 출구
      }
      // 힌지 마디(앞판: 짝수) + 출력용 45° 받침
      for (i = [0 : 2 : nseg-1]) {
        xcyl(seg_x0(i), seg_x1(i), hr, ya, za);
        hull() {
          xcyl(seg_x0(i), seg_x1(i), hr, ya, za);
          translate([seg_x0(i), H - wall - 0.01, za - 2*hr]) cube([seg_x1(i) - seg_x0(i), 0.01, 0.01]);
        }
      }
    }
    // 표시 창 (앞쪽 45° 모따기) — 1.0과 동일
    wx = ox + panel_x + active_x - win_margin;
    wy = oy + panel_y + active_y - win_margin;
    ww = active_w + 2*win_margin;
    wh = active_h + 2*win_margin;
    translate([0, 0, -0.01]) hull() {
      translate([wx, wy, front_t]) cube([ww, wh, 0.02]);
      translate([wx - front_t, wy - front_t, 0]) cube([ww + 2*front_t, wh + 2*front_t, 0.02]);
    }
    // 힌지: 핀 구멍, 뒷판 마디 자리
    xcyl(-1, W + 1, pin_d/2, ya, za);
    for (i = [1 : 2 : nseg-1]) xcyl(seg_x0(i) - hgap/2, seg_x1(i) + hgap/2, hr + hclr, ya, za);
    // 스냅 훅이 걸리는 바닥벽 구멍 (바깥에서 핀으로 눌러 해제)
    for (hx = hook_x) translate([hx - hook_w/2 - 0.3, -1, D - hook_L - 0.2]) cube([hook_w + 0.6, wall + 2, barb_len + 0.6]);
    // 보드 USB 끝이 들어가는 바닥벽 홈 (뒤쪽으로 열림) + USB-C 구멍
    translate([brd_x0 - 0.3 - rail_t - 0.5, usb_skin, D - brd_stand - brd_t - 3.4]) cube([brd_w + 2*(rail_t + 0.8), wall, 10]);
    translate([(brd_x0 + brd_x1)/2 - usb_w/2, -1, D - brd_stand - brd_t - 1.6 - usb_h/2]) cube([usb_w, wall + 2, usb_h]);
    // e-paper 스냅 탭: 옆벽에 U자 홈 + 바깥쪽 얇게
    for (side = [0, 1]) for (ty = [oy + 22, oy + pcb_h - 22]) {
      xw = side == 0 ? 0 : W - wall;
      // U자 홈 (탭 끝은 앞쪽, 뿌리는 뒤쪽)
      translate([xw - 1, ty - tab_w/2 - tab_gap, pcb_back - 1.4]) cube([wall + 2, tab_gap, D - pcb_back - 1]);
      translate([xw - 1, ty + tab_w/2, pcb_back - 1.4]) cube([wall + 2, tab_gap, D - pcb_back - 1]);
      translate([xw - 1, ty - tab_w/2 - tab_gap, pcb_back - 1.4 - tab_gap]) cube([wall + 2, tab_w + 2*tab_gap, tab_gap]);
      // 탭을 tab_t 두께로 (바깥쪽을 깎음)
      translate([side == 0 ? -1 : W - wall + tab_t, ty - tab_w/2, pcb_back - 1.4]) cube([wall - tab_t + 1, tab_w, D - pcb_back - 1]);
    }
  }
  // 스냅 탭 돌기: 기판 뒷면 바로 뒤, 뒤쪽에 45° 경사(뒤에서 밀어 넣으면 걸림)
  for (side = [0, 1]) for (ty = [oy + 22, oy + pcb_h - 22]) {
    xi = side == 0 ? wall : W - wall;
    s = side == 0 ? 1 : -1;
    translate([xi, ty - tab_w/2, pcb_back + 0.05]) rotate([-90, 0, 0]) linear_extrude(tab_w)
      polygon([[0, 0], [s*tab_bump, 0], [s*tab_bump, -1.0], [0, -1.0 - tab_bump]]);
  }
}

// ================= 뒷판 =================
module cover_body() {
  difference() {
    union() {
      // 판: 윗변은 힌지 축 둘레로 둥글게(회전 시 앞판과 간섭 없음)
      intersection() {
        translate([0, 0, D]) rrect(W, H, cover_t, 3);
        union() {
          translate([-1, -1, D - 1]) cube([W + 2, ya + 1, cover_t + 2]);
          xcyl(-1, W + 1, hr, ya, za);
        }
      }
      // 힌지 마디(뒷판: 홀수)
      for (i = [1 : 2 : nseg-1]) xcyl(seg_x0(i), seg_x1(i), hr, ya, za);
      // 정렬 테두리(좌·우): 앞판 옆벽 안쪽에 들어가 벌어짐을 막음
      for (x = [wall + rim_clr, rim_in_r]) translate([x, wall + 2, D - rim_h]) cube([rim_t, H - 2*hr - wall - 4, rim_h + 0.01]);
      // 스냅 훅: 뒷판에서 앞쪽으로 솟은 외팔보 + 끝의 걸쇠
      for (hx = hook_x) {
        translate([hx - hook_w/2, wall + 0.3, D - hook_L]) cube([hook_w, hook_t, hook_L + 0.01]);
        translate([hx - hook_w/2, wall + 0.3, D - hook_L]) rotate([90, 0, 90]) linear_extrude(hook_w)
          polygon([[0, 0], [0, barb_len], [-barb, barb_len], [-barb, 0.8]]);
      }
      // 배터리 울타리 (모서리 트임 = 벨크로/케이블타이 통로)
      translate([bat_x0 - fence_t - 0.4, bat_y - fence_t - 0.4, D - fence_hgt]) difference() {
        cube([bat_w + 2*fence_t + 0.8, bat_h + 2*fence_t + 0.8, fence_hgt + 0.01]);
        translate([fence_t, fence_t, -1]) cube([bat_w + 0.8, bat_h + 0.8, fence_hgt + 2]);
        for (yy = [0.25, 0.75]) translate([-1, (bat_h + 2*fence_t) * yy - 5, -1]) cube([bat_w + 2*fence_t + 3, 10, 3.2]);
      }
      // 보드 레일: 받침 턱 + 옆벽 + 위쪽 걸림 립
      for (side = [0, 1]) {
        xr = side == 0 ? brd_x0 - 0.3 - rail_t : brd_x1 + 0.3;
        translate([xr, brd_y0, D - (brd_stand + brd_t + 0.8)]) cube([rail_t, brd_h, brd_stand + brd_t + 0.8 + 0.01]);
        translate([side == 0 ? xr + rail_t : xr - 1.2, brd_y0, D - brd_stand]) cube([1.2, brd_h, brd_stand + 0.01]);  // 받침
        translate([side == 0 ? xr + rail_t : xr - rail_lip, brd_y0 + 8, D - (brd_stand + brd_t + 0.8)])
          cube([rail_lip, brd_h - 16, 0.8]);  // 립
      }
      translate([brd_x0 - 0.3 - rail_t, brd_y0 + brd_h + 0.3, D - (brd_stand + brd_t)]) cube([brd_w + 0.6 + 2*rail_t, 1.6, brd_stand + brd_t + 0.01]);  // 위쪽 멈춤
    }
    // 힌지: 핀 구멍, 앞판 마디 자리
    xcyl(-1, W + 1, pin_d/2, ya, za);
    for (i = [0 : 2 : nseg-1]) xcyl(seg_x0(i) - hgap/2, seg_x1(i) + hgap/2, hr + hclr, ya, za);
    // 자석 포켓 (바깥면, 압입 + 순간접착제)
    for (x = mag_cols, y = mag_rows) translate([x, y, D + cover_t - mag_t - 0.2]) cylinder(d=mag_d + 0.3, h=mag_t + 1);
  }
}
module cover() { cover_body(); }

// ================= 미리보기용 부품 =================
module ghosts(z_off=0) {
  translate([ox + panel_x, oy + panel_y, front_t]) color("white", 0.9) cube([panel_w, panel_h, panel_t]);
  translate([ox, oy, front_t + stack]) color("darkgreen", 0.7) cube([pcb_w, pcb_h, pcb_t]);
  translate([W/2 - ant_w/2, wall + 1, front_t]) color("gold", 0.9) cube([ant_w, ant_h, 0.3]);
}
module cover_ghosts() {
  translate([bat_x0, bat_y, D - bat_t]) color("silver", 0.9) cube([bat_w, bat_h, bat_t]);
  translate([brd_x0, brd_y0, D - brd_stand - brd_t]) color("royalblue", 0.9) cube([brd_w, brd_h, brd_t]);
}

module rot_about_hinge(a) { translate([0, ya, za]) rotate([a, 0, 0]) translate([0, -ya, -za]) children(); }

if (part == "front") front();
else if (part == "cover") cover();
else if (part == "print_front") front();                                        // 앞면이 베드
else if (part == "print_cover") translate([0, 0, D + cover_t]) mirror([0, 0, 1]) cover();  // 바깥면(자석)이 베드
else if (part == "open") {
  color("tomato", 0.85) cover(); cover_ghosts();
  rot_about_hinge(open_angle) { color("orange", 0.85) front(); ghosts(); }
}
else if (part == "exploded") {
  color("orange", 0.85) front(); ghosts();
  translate([0, 0, 25]) { color("tomato", 0.85) cover(); cover_ghosts(); }
}
// 검사용: 조립 상태·열린 상태에서 앞판과 뒷판의 겹침(둘 다 비어 있어야 함)
else if (part == "check_overlap") intersection() { front(); cover(); }
else if (part == "check_pcb") intersection() { union() { front(); cover(); } translate([ox, oy, front_t + stack + 0.01]) cube([pcb_w, pcb_h, pcb_t - 0.02]); }
else if (part == "check_parts") intersection() { union() { front(); cover(); translate([ox, oy, front_t + stack]) cube([pcb_w, pcb_h, pcb_t]); }
  union() { translate([bat_x0 + 0.01, bat_y + 0.01, D - bat_t]) cube([bat_w - 0.02, bat_h - 0.02, bat_t - 0.01]);
            translate([brd_x0 + 0.01, brd_y0 + 0.01, D - brd_stand - brd_t]) cube([brd_w - 0.02, brd_h - 0.02, brd_t]); } }
else if (part == "check_open") intersection() { cover(); rot_about_hinge(open_angle) front(); }
else { color("orange", 0.6) front(); ghosts(); color("tomato", 0.85) cover(); cover_ghosts(); }

