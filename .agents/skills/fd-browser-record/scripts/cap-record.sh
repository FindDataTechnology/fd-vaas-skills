#!/usr/bin/env bash
# cap-record.sh — cap 录屏/截屏的封装脚本
# 用法见 SKILL.md 或执行 --help
set -euo pipefail

CAP_BIN="${CAP_BIN:-cap}"

err() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[cap-record] $*"; }

usage() {
  cat <<'EOF'
cap-record.sh — cap 录屏 / 截屏封装

用法:
  cap-record.sh list-windows
  cap-record.sh record-screen   [--duration N] [--detach] [--output PATH] [--quality Q] [--fps N]
  cap-record.sh record-window   (--window-id ID | --match NAME) [--duration N] [--detach] [--output PATH] [--quality Q]
  cap-record.sh screenshot-screen --output PATH
  cap-record.sh screenshot-window (--window-id ID | --match NAME) --output PATH
  cap-record.sh stop --cap-file PATH.cap [--export PATH.mp4]

参数:
  --duration N       录制时长（秒），默认 10
  --detach           后台录制，返回后用 stop 结束
  --output PATH      输出文件（.mp4 / .png / .cap）
  --quality Q        导出质量：maximum / social / web / potato，默认 web
  --window-id ID     窗口 ID（从 list-windows 获取）
  --match NAME       按应用名/标题模糊匹配窗口
  --fps N            帧率，默认 30
  --cap-file PATH    .cap 工程文件路径（stop 时用）
  --help             显示帮助

输出:
  默认输出到当前目录。成功后打印最终文件路径。
EOF
}

# ========== 公共函数 ==========

# 列出所有窗口，打印 JSON 数组
list_windows_json() {
  "$CAP_BIN" targets --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data.get('windows', []), ensure_ascii=False))
"
}

# 按匹配词找窗口，返回窗口 ID。匹配到多个时报错列出候选。
match_window() {
  local match="$1"
  local result
  result=$(list_windows_json | python3 -c "
import json, sys
match = '$match'.lower()
windows = json.load(sys.stdin)
hits = []
for w in windows:
    name = (w.get('name') or '').lower()
    owner = (w.get('ownerName') or '').lower()
    if match in name or match in owner:
        hits.append(w)
if len(hits) == 0:
    print('__NONE__')
elif len(hits) == 1:
    print(hits[0]['id'])
else:
    print('__MULTI__')
    for i, w in enumerate(hits):
        print(f'  [{i}] id={w[\"id\"]}  app={w[\"ownerName\"]}  title={w[\"name\"][:60]}')
")
  echo "$result"
}

# ========== 命令实现 ==========

cmd_list_windows() {
  list_windows_json | python3 -c "
import json, sys
windows = json.load(sys.stdin)
for i, w in enumerate(windows):
    print(f'[{i:2d}] id={w[\"id\"]:>6}  app={w[\"ownerName\"]:20s}  title={w[\"name\"][:60]}')
"
}

cmd_record_screen() {
  local duration=10 detach=0 output="" quality="web" fps=30
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --duration) duration="$2"; shift 2 ;;
      --detach) detach=1; shift ;;
      --output) output="$2"; shift 2 ;;
      --quality) quality="$2"; shift 2 ;;
      --fps) fps="$2"; shift 2 ;;
      *) err "未知参数: $1" ;;
    esac
  done

  local cap_file
  if [[ -n "$output" && "$output" == *.cap ]]; then
    cap_file="$output"
  elif [[ -n "$output" ]]; then
    cap_file="${output%.mp4}.cap"
  else
    cap_file="browser-record-$(date +%Y%m%d-%H%M%S).cap"
  fi

  local args=(--screen 1 --path "$cap_file" --fps "$fps")
  if [[ $detach -eq 1 ]]; then
    args+=(--detach)
  else
    args+=(--duration "$duration")
  fi

  info "开始录制主屏: duration=${duration}s, output=${cap_file}"
  "$CAP_BIN" record start "${args[@]}" --json 2>&1 | tail -5

  if [[ $detach -eq 0 ]]; then
    # 等录制完成（duration 模式会自己停，但给点 buffer）
    sleep $((duration + 2))
    # 导出 mp4
    local mp4_file
    if [[ -n "$output" && "$output" != *.cap ]]; then
      mp4_file="$output"
    else
      mp4_file="${cap_file%.cap}.mp4"
    fi
    info "导出视频: $mp4_file"
    "$CAP_BIN" export "$cap_file" -o "$mp4_file" --quality "$quality" --json 2>&1 | tail -3
    info "完成: $mp4_file"
    echo "$mp4_file"
  else
    info "后台录制中，用 stop 命令停止。cap 文件: $cap_file"
    echo "$cap_file"
  fi
}

cmd_record_window() {
  local window_id="" match="" duration=10 detach=0 output="" quality="web"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --window-id) window_id="$2"; shift 2 ;;
      --match) match="$2"; shift 2 ;;
      --duration) duration="$2"; shift 2 ;;
      --detach) detach=1; shift ;;
      --output) output="$2"; shift 2 ;;
      --quality) quality="$2"; shift 2 ;;
      *) err "未知参数: $1" ;;
    esac
  done

  # 解析窗口 ID
  if [[ -z "$window_id" && -n "$match" ]]; then
    local match_result
    match_result=$(match_window "$match")
    if [[ "$match_result" == __NONE__ ]]; then
      err "没找到匹配 '$match' 的窗口"
    elif [[ "$match_result" == __MULTI__* ]]; then
      echo "匹配到多个窗口，请用 --window-id 指定：" >&2
      echo "$match_result" | tail -n +2 >&2
      exit 1
    else
      window_id="$match_result"
      info "匹配到窗口: id=$window_id"
    fi
  fi

  [[ -z "$window_id" ]] && err "必须指定 --window-id 或 --match"

  local cap_file
  if [[ -n "$output" && "$output" == *.cap ]]; then
    cap_file="$output"
  elif [[ -n "$output" ]]; then
    cap_file="${output%.mp4}.cap"
  else
    cap_file="browser-record-$(date +%Y%m%d-%H%M%S).cap"
  fi

  local args=(--window "$window_id" --path "$cap_file")
  if [[ $detach -eq 1 ]]; then
    args+=(--detach)
  else
    args+=(--duration "$duration")
  fi

  info "开始录制窗口 $window_id: duration=${duration}s, output=${cap_file}"
  "$CAP_BIN" record start "${args[@]}" --json 2>&1 | tail -5

  if [[ $detach -eq 0 ]]; then
    sleep $((duration + 2))
    local mp4_file
    if [[ -n "$output" && "$output" != *.cap ]]; then
      mp4_file="$output"
    else
      mp4_file="${cap_file%.cap}.mp4"
    fi
    info "导出视频: $mp4_file"
    "$CAP_BIN" export "$cap_file" -o "$mp4_file" --quality "$quality" --json 2>&1 | tail -3
    info "完成: $mp4_file"
    echo "$mp4_file"
  else
    info "后台录制中，用 stop 命令停止。cap 文件: $cap_file"
    echo "$cap_file"
  fi
}

cmd_screenshot_screen() {
  local output=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output) output="$2"; shift 2 ;;
      *) err "未知参数: $1" ;;
    esac
  done
  [[ -z "$output" ]] && output="browser-shot-$(date +%Y%m%d-%H%M%S).png"

  info "截屏（主屏）: $output"
  "$CAP_BIN" screenshot --screen 1 --path "$output" --json 2>&1
  echo "$output"
}

cmd_screenshot_window() {
  local window_id="" match="" output=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --window-id) window_id="$2"; shift 2 ;;
      --match) match="$2"; shift 2 ;;
      --output) output="$2"; shift 2 ;;
      *) err "未知参数: $1" ;;
    esac
  done

  if [[ -z "$window_id" && -n "$match" ]]; then
    local match_result
    match_result=$(match_window "$match")
    if [[ "$match_result" == __NONE__ ]]; then
      err "没找到匹配 '$match' 的窗口"
    elif [[ "$match_result" == __MULTI__* ]]; then
      echo "匹配到多个窗口，请用 --window-id 指定：" >&2
      echo "$match_result" | tail -n +2 >&2
      exit 1
    else
      window_id="$match_result"
      info "匹配到窗口: id=$window_id"
    fi
  fi

  [[ -z "$window_id" ]] && err "必须指定 --window-id 或 --match"
  [[ -z "$output" ]] && output="browser-shot-$(date +%Y%m%d-%H%M%S).png"

  info "截屏（窗口 $window_id）: $output"
  "$CAP_BIN" screenshot --window "$window_id" --path "$output" --json 2>&1
  echo "$output"
}

cmd_stop() {
  local cap_file="" export_file="" quality="web"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cap-file) cap_file="$2"; shift 2 ;;
      --export) export_file="$2"; shift 2 ;;
      --quality) quality="$2"; shift 2 ;;
      *) err "未知参数: $1" ;;
    esac
  done
  [[ -z "$cap_file" ]] && err "必须指定 --cap-file"

  info "停止录制: $cap_file"
  "$CAP_BIN" record stop --json 2>&1 | tail -3

  if [[ -n "$export_file" ]]; then
    info "导出视频: $export_file"
    "$CAP_BIN" export "$cap_file" -o "$export_file" --quality "$quality" --json 2>&1 | tail -3
    info "完成: $export_file"
    echo "$export_file"
  else
    info "录制已停止，未导出。cap 文件: $cap_file"
    echo "$cap_file"
  fi
}

# ========== 入口 ==========

if [[ $# -eq 0 ]]; then usage; exit 1; fi
case "$1" in
  -h|--help|help) usage; exit 0 ;;
  list-windows) shift; cmd_list_windows "$@" ;;
  record-screen) shift; cmd_record_screen "$@" ;;
  record-window) shift; cmd_record_window "$@" ;;
  screenshot-screen) shift; cmd_screenshot_screen "$@" ;;
  screenshot-window) shift; cmd_screenshot_window "$@" ;;
  stop) shift; cmd_stop "$@" ;;
  *) err "未知命令: $1 (用 --help 查看用法)" ;;
esac
