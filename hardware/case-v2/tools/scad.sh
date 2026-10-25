#!/usr/bin/env bash
# OpenSCAD 를 원격 Docker 호스트(기본 zepawork)에서 실행한다.
# Homebrew openscad cask 가 Gatekeeper 문제로 막혀 있어서, 공식 이미지 openscad/openscad 를 씀.
#
# 사용: tools/scad.sh <part> <출력파일(.stl|.png)> [추가 openscad 인자...]
#   예: tools/scad.sh print_front out/front.stl
#       tools/scad.sh assembly out/assembly.png --camera=0,0,0,60,0,30,320 --autocenter --viewall
set -euo pipefail
HOST="${SCAD_HOST:-zepawork}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
part="$1"; out="$2"; shift 2
ext="${out##*.}"
remote=/tmp/roomdisplay_scad
ssh "$HOST" "mkdir -p $remote"
scp -q "$HERE/roomdisplay_case_v2.scad" "$HOST:$remote/case.scad"
pre=""
[ "$ext" = "png" ] && pre="xvfb-run -a"
ssh "$HOST" "rm -f $remote/out.$ext"
ssh "$HOST" "docker run --rm -v $remote:/w -w /w openscad/openscad:latest $pre openscad -D 'part=\"$part\"' $* -o /w/out.$ext case.scad 2>&1 | grep -vE '^(Geometries|Rendering|Compiling|Total|Normalized|CGAL|   |Geometry cache)' || true"
mkdir -p "$(dirname "$out")"
if ssh "$HOST" "test -s $remote/out.$ext"; then
  scp -q "$HOST:$remote/out.$ext" "$out"; echo "→ $out"
else
  rm -f "$out"; echo "→ (결과 없음: 형상이 비어 있음)"
fi
