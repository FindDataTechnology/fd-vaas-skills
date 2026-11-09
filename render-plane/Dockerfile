# VAAS 渲染面镜像（adopt-hyperframes-video-renderer W1）
#
# 独立平面：只做 composition -> MP4。不含 VAAS 业务代码，不碰账本。
# 隔离：部署时接 internal-only 网络（无外网）；作业进程 env 白名单由 server.mjs 保证。
# 引擎：hyperframes 0.9.26（钉死，见 package.json），复用系统 chromium/ffmpeg。

FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# 国内镜像换源 + 系统依赖（chromium/ffmpeg/CJK 字体/unzip）
# 兼容 deb822（debian.sources）与 classic（sources.list）两种布局
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i 's|http://deb.debian.org|http://mirrors.ustc.edu.cn|g; s|http://security.debian.org|http://mirrors.ustc.edu.cn|g' "$f" || true; \
    done; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      chromium ffmpeg fonts-noto-cjk unzip iproute2 ca-certificates curl; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖层（先装依赖，代码变更不失效缓存）
COPY package.json package-lock.json ./
RUN PUPPETEER_SKIP_DOWNLOAD=1 npm ci --omit=dev \
      --registry=https://registry.npmmirror.com --no-audit --no-fund

COPY server.mjs ./

# 引擎与运行时定位（全部指向镜像内既有二进制；禁 CDN、禁遥测、禁自动安装）
ENV HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium \
    HYPERFRAMES_FFMPEG_PATH=/usr/bin/ffmpeg \
    HYPERFRAMES_FFPROBE_PATH=/usr/bin/ffprobe \
    HYPERFRAMES_NO_TELEMETRY=1 \
    HYPERFRAMES_NO_AUTO_INSTALL=1 \
    HYPERFRAMES_NO_OPTIONAL_INSTALL=1 \
    HYPERFRAMES_NO_UPDATE_CHECK=1 \
    HYPERFRAMES_CACHE_DIR=/tmp/hf-cache \
    HYPERFRAMES_MEDIA_HOME=/tmp/hf-media \
    VAAS_RENDER_PORT=8099 \
    VAAS_RENDER_WORKDIR=/tmp/vaas-render

# 构建期门禁：引擎可执行（版本不符即构建失败）
RUN ./node_modules/.bin/hyperframes --version

EXPOSE 8099

# 专用渲染面：以 root 运行（Chrome 沙箱在本环境不依赖 user namespace；
# 隔离由 internal 网络 + 作业级 env 白名单 + 独立 tmpdir 保证）。
CMD ["node", "server.mjs"]
