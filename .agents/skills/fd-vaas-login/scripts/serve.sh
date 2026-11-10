#!/usr/bin/env bash
# 登录管理页启停（VAAS/.agents/skills/fd-vaas-login/scripts/serve.sh）
#
# 为什么需要它：这页是个前台 Python 进程，会话被中断/终端关掉就一起没了，
# 用户那边表现成「页面打不开」。用「监听端口的真实进程」做唯一判据，把它变成
# 一次命令启停，而不是每次让 agent 手动 nohup 拉起。
#
# 用法：
#   bash .agents/skills/fd-vaas-login/scripts/serve.sh start|stop|restart|status
#
# 解释器：VAAS_PYTHON > 仓内 .venv > PATH（与 login-manager 自身的解析同口径）。
# 为什么不用裸 python3：本页只需 stdlib，但它 spawn 的登录子进程要
# playwright/patchright/cv2/segno，系统 python 换 major 后这些会整片消失，
# 子进程秒死、二维码永不出现（2026-11-10 现场）。
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
PID_FILE="$HERE/.login-manager.pid"
LOG_FILE="${VAAS_LOGIN_LOG:-/tmp/vaas-login.log}"
PORT=8766
URL="http://127.0.0.1:${PORT}/"

resolve_python() {
  if [ -n "${VAAS_PYTHON:-}" ]; then echo "$VAAS_PYTHON"
  elif [ -x "$ROOT/.venv/bin/python" ]; then echo "$ROOT/.venv/bin/python"
  elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then echo "$ROOT/.venv/Scripts/python.exe"
  else echo "python3"; fi
}

# 唯一判据 = 谁在监听端口。
# 为什么不信 pid 文件：`$!` 拿到的是包装子 shell 的 pid，实测与真正的 python
# 差一位（11278 vs 11279）→ stop 杀掉包装壳、python 成孤儿，status 报「未运行」
# 而 HTTP 仍 200。两个口径不一致时，以端口为准（2026-11-10 实测）。
running_pid() {
  local pid
  pid="$(lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null | head -1)"
  if [ -n "$pid" ]; then echo "$pid"; return 0; fi
  # 端口没监听时再看 pid 文件（启动中/未就绪的窗口期）
  [ -f "$PID_FILE" ] || return 1
  pid="$(cat "$PID_FILE" 2>/dev/null)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  # 只认确实是 login-manager 的进程，避免 pid 复用误判
  ps -p "$pid" -o command= 2>/dev/null | grep -q "login-manager.py" || return 1
  echo "$pid"
}

http_ok() { curl -s -o /dev/null --max-time 3 --noproxy '*' "$URL"; }

do_start() {
  local pid
  # 注意：变量后紧跟全角标点时必须用 ${var}。bash 会把多字节字符首字节并进
  # 变量名，勾出 `py?: unbound variable`（2026-11-10 踩到）。
  if pid="$(running_pid)"; then
    echo "已在运行（pid=${pid}）：${URL}"
  else
    local py; py="$(resolve_python)"
    ( cd "$ROOT" && exec "$py" -u "$HERE/login-manager.py" ) \
      > "$LOG_FILE" 2>&1 < /dev/null &
    echo $! > "$PID_FILE"
    sleep 1
    echo "启动中：${py}（日志 ${LOG_FILE}）"
  fi
  # 就绪探测：预检要逐个 import 六个依赖，通常 5-15s
  local i
  for i in $(seq 1 40); do
    if http_ok; then
      # 就绪后用端口反查校正 pid 文件，保证后续 stop 杀的是真进程
      local real; real="$(lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null | head -1)"
      [ -n "$real" ] && echo "$real" > "$PID_FILE"
      echo "✅ 就绪：${URL}（pid=${real:-unknown}）"
      return 0
    fi
    sleep 1
  done
  echo "❌ 30s 内未就绪，看日志：${LOG_FILE}" >&2
  tail -20 "$LOG_FILE" >&2 2>/dev/null
  return 1
}

do_stop() {
  local pid
  if pid="$(running_pid)"; then
    kill "$pid" 2>/dev/null
    local i
    for i in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.3; done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "已停止（pid=${pid}）"
  else
    rm -f "$PID_FILE"
    echo "未在运行"
  fi
}

do_status() {
  local pid
  if pid="$(running_pid)"; then echo "进程：运行中（pid=${pid}）"; else echo "进程：未运行"; fi
  if http_ok; then echo "HTTP：✅ ${URL}"; else echo "HTTP：❌ ${URL} 不可达"; fi
}

case "${1:-start}" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_stop; do_start ;;
  status)  do_status ;;
  *) echo "用法: $0 start|stop|restart|status" >&2; exit 2 ;;
esac
