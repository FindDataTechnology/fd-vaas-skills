#!/usr/bin/env bash
# VAAS 托管实例存活兜底（release-verification）：healthcheck 标 unhealthy 时重启容器。
# docker/compose 自身不做 unhealthy→restart，本脚本挂部署节点 cron（建议每 5 分钟）。
#
# 安装（部署节点，root crontab）：
#   */5 * * * * bash /opt/vaas/deploy/health-watch.sh >> /var/log/vaas-health-watch.log 2>&1
#
# 可调：容器名（默认 vaas-wanxing）、连续失败阈值（默认 2 次，防抖）。
set -u
CONTAINER="${VAAS_CONTAINER:-vaas-wanxing}"
THRESHOLD="${VAAS_UNHEALTHY_THRESHOLD:-2}"
STAMP_FILE="${VAAS_WATCH_STAMP:-/tmp/vaas-health-watch.unhealthy}"

status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>/dev/null || echo missing)"

case "$status" in
  healthy)
    rm -f "$STAMP_FILE"
    ;;
  unhealthy)
    n=1
    [ -f "$STAMP_FILE" ] && n=$(( $(cat "$STAMP_FILE") + 1 ))
    echo "$n" > "$STAMP_FILE"
    echo "$(date -Is) $CONTAINER unhealthy（连续 $n/$THRESHOLD）"
    if [ "$n" -ge "$THRESHOLD" ]; then
      echo "$(date -Is) restart $CONTAINER"
      docker restart "$CONTAINER"
      rm -f "$STAMP_FILE"
    fi
    ;;
  missing)
    echo "$(date -Is) 容器 $CONTAINER 不存在——检查部署栈（restart 策略应已拉起，若持续缺失查 docker events）"
    ;;
  *)
    : # starting/none：静默观察
    ;;
esac
