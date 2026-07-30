#!/usr/bin/env python3
import os
import json
import http.server
import socketserver
import urllib.parse
from pathlib import Path

PORT = 8765
ROOT = Path(__file__).parent.parent.parent.parent.parent  # VAAS/
DOWNLOADS = ROOT / "downloads"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        elif self.path.startswith("/api/files"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            only_final = params.get("mode", ["all"])[0] == "final"
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(scan_files(only_final), ensure_ascii=False).encode("utf-8"))
        else:
            # Serve static files (videos, images)
            super().do_GET()

    def log_message(self, format, *args):
        pass  # suppress logs

def is_final_video(name):
    """判断是否为最终视频：不含版本标识、不在 _archive"""
    keywords = ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "old", "archive", "timing", "fixed", "perfect", "-temp-"]
    return not any(k in name.lower() for k in keywords)

def is_final_article(name):
    """判断是否为最终文章：排除 history, manifest, script 等中间文件"""
    if name in ["history.md", "manifest.md", "script.md", "org-script.txt", "notes.md"]:
        return False
    if name.startswith("_"):
        return False
    return True

def is_final_image(name):
    """判断是否为最终封面图"""
    keywords = ["bg-", "background", "screenshot", "temp"]
    return not any(k in name.lower() for k in keywords)

def scan_files(only_final=False):
    projects = {}
    for root, dirs, files in os.walk(DOWNLOADS):
        root_path = Path(root)
        rel_root = root_path.relative_to(DOWNLOADS)

        if "_archive" in str(rel_root):
            continue

        parts = rel_root.parts
        if len(parts) < 2:
            continue

        category = parts[0]  # fd-docs, fd-videos
        project = parts[1]

        key = f"{category}/{project}"
        if key not in projects:
            projects[key] = {
                "category": category,
                "project": project,
                "videos": [],
                "articles": [],
                "images": [],
                "adapted": {}
            }

        # Skip .adapted in scan, handle separately
        if ".adapted" in str(rel_root):
            continue

        for f in files:
            full_path = root_path / f
            rel_path = f"downloads/{rel_root}/{f}"

            if f.endswith(".mp4"):
                if only_final and not is_final_video(f):
                    continue
                projects[key]["videos"].append({
                    "name": f,
                    "path": rel_path,
                    "size": format_size(full_path.stat().st_size),
                    "is_final": is_final_video(f)
                })
            elif f.endswith(".md"):
                if only_final and not is_final_article(f):
                    continue
                projects[key]["articles"].append({
                    "name": f,
                    "path": rel_path,
                    "size": format_size(full_path.stat().st_size),
                    "is_final": is_final_article(f)
                })
            elif f.endswith((".jpg", ".jpeg", ".png", ".webp")):
                if only_final and not is_final_image(f):
                    continue
                projects[key]["images"].append({
                    "name": f,
                    "path": rel_path,
                    "size": format_size(full_path.stat().st_size),
                    "is_final": is_final_image(f)
                })

        # Check for .adapted versions
        adapted_dir = root_path / ".adapted"
        if adapted_dir.exists():
            for platform in os.listdir(adapted_dir):
                platform_dir = adapted_dir / platform
                if platform_dir.is_dir():
                    body_file = platform_dir / "body.md"
                    if body_file.exists():
                        projects[key]["adapted"][platform] = {
                            "path": f"downloads/{rel_root}/.adapted/{platform}/body.md"
                        }

    # Filter empty projects
    result = []
    for p in projects.values():
        if only_final:
            if not p["videos"] and not p["articles"] and not p["images"]:
                continue
        result.append(p)
    return result

def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VAAS 作品集</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #050505; color: #e5e7eb; padding: 32px; max-width: 1400px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; flex-wrap: wrap; gap: 16px; }
h1 { font-size: 32px; font-weight: 700; letter-spacing: -0.5px; }
.subtitle { color: #6b7280; margin-top: 4px; }
.view-tabs { display: flex; gap: 4px; background: #1a1a1a; padding: 4px; border-radius: 10px; }
.view-tab { padding: 10px 16px; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
.view-tab.active { background: #2563eb; color: white; }
.hero { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 40px; }
.hero-card { background: #111; padding: 24px; border-radius: 16px; border: 1px solid #1f1f1f; }
.hero-value { font-size: 36px; font-weight: 700; line-height: 1; }
.hero-label { font-size: 12px; color: #6b7280; margin-top: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; }
.portfolio-card { background: #111; border-radius: 20px; overflow: hidden; border: 1px solid #1f1f1f; transition: transform 0.2s; }
.portfolio-card:hover { transform: translateY(-4px); }
.card-cover { height: 240px; background: #1a1a1a; position: relative; overflow: hidden; }
.card-cover img { width: 100%; height: 100%; object-fit: cover; }
.card-overlay { position: absolute; bottom: 0; left: 0; right: 0; padding: 20px; background: linear-gradient(transparent, rgba(0,0,0,0.8)); }
.card-title { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.card-meta { font-size: 12px; color: #9ca3af; }
.card-content { padding: 20px; }
.section-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #6b7280; margin-bottom: 10px; }
.asset-list { display: flex; flex-direction: column; gap: 6px; }
.asset { display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: #1a1a1a; border-radius: 10px; font-size: 13px; }
.asset-icon { width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
.asset-icon.video { background: #3b82f620; color: #60a5fa; }
.asset-icon.article { background: #10b98120; color: #34d399; }
.asset-icon.image { background: #f59e0b20; color: #fbbf24; }
.asset-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-size { color: #6b7280; font-size: 11px; }
.asset a { color: inherit; text-decoration: none; display: flex; align-items: center; gap: 10px; flex: 1; }
.asset a:hover { color: #60a5fa; }
.platforms { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.platform-badge { padding: 6px 10px; background: #8b5cf620; color: #a78bfa; border-radius: 8px; font-size: 11px; cursor: pointer; font-weight: 500; }
.platform-badge:hover { background: #8b5cf630; }
.type-badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; margin-bottom: 12px; }
.type-badge.video { background: #3b82f620; color: #60a5fa; }
.type-badge.article { background: #10b98120; color: #34d399; }
.draft-badge { opacity: 0.5; border: 1px dashed #333; }
#loading { text-align: center; padding: 80px; }
.spinner { width: 40px; height: 40px; border: 3px solid #1a1a1a; border-top-color: #3b82f6; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty { text-align: center; padding: 80px; color: #6b7280; }
@media (max-width: 900px) {
    .hero { grid-template-columns: repeat(2, 1fr); }
    .grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>✨ VAAS 作品集</h1>
        <div class="subtitle">所有生成的内容作品</div>
    </div>
    <div class="view-tabs">
        <div class="view-tab active" data-mode="final">最终作品</div>
        <div class="view-tab" data-mode="all">全部文件</div>
    </div>
</div>

<div class="hero">
    <div class="hero-card">
        <div class="hero-value" id="total-projects">-</div>
        <div class="hero-label">项目</div>
    </div>
    <div class="hero-card">
        <div class="hero-value" id="total-videos">-</div>
        <div class="hero-label">视频</div>
    </div>
    <div class="hero-card">
        <div class="hero-value" id="total-articles">-</div>
        <div class="hero-label">文章</div>
    </div>
    <div class="hero-card">
        <div class="hero-value" id="total-platforms">-</div>
        <div class="hero-label">平台版本</div>
    </div>
</div>

<div id="loading">
    <div class="spinner"></div>
    <div>加载中...</div>
</div>

<div class="grid" id="grid" style="display: none;"></div>

<script>
let currentMode = 'final';

document.querySelectorAll('.view-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentMode = tab.dataset.mode;
        load();
    });
});

async function load() {
    const grid = document.getElementById('grid');
    grid.innerHTML = '';

    document.getElementById('loading').style.display = 'block';
    grid.style.display = 'none';

    const res = await fetch('/api/files?mode=' + currentMode);
    const data = await res.json();

    document.getElementById('loading').style.display = 'none';
    grid.style.display = 'grid';

    document.getElementById('total-projects').textContent = data.length;
    document.getElementById('total-videos').textContent = data.reduce((s, p) => s + p.videos.length, 0);
    document.getElementById('total-articles').textContent = data.reduce((s, p) => s + p.articles.length, 0);
    document.getElementById('total-platforms').textContent = data.reduce((s, p) => s + Object.keys(p.adapted || {}).length, 0);

    data.forEach(p => {
        const card = document.createElement('div');
        card.className = 'portfolio-card';

        const type = p.category.includes('videos') ? 'video' : 'article';
        const typeLabel = p.category.includes('videos') ? '视频项目' : '文章项目';

        // Find best cover
        let coverPath = null;
        const cover = p.images.find(i => i.name.includes('cover') && !i.name.includes('xhs'));
        if (cover) coverPath = cover.path;
        if (!coverPath && p.images.length) coverPath = p.images[0].path;

        let coverHtml = '';
        if (coverPath) {
            coverHtml = `<img src="${coverPath}" onclick="window.open('${coverPath}')" style="cursor: pointer">`;
        }

        let videosHtml = '';
        if (p.videos.length) {
            videosHtml = `<div><div class="section-label">视频</div><div class="asset-list">` +
                p.videos.map(v => `
                <div class="asset ${!v.is_final ? 'draft-badge' : ''}">
                    <div class="asset-icon video">🎞</div>
                    <a href="${v.path}" target="_blank">
                        <div class="asset-name">${v.name}</div>
                        <div class="asset-size">${v.size}</div>
                    </a>
                </div>`).join('') +
                '</div></div>';
        }

        let articlesHtml = '';
        if (p.articles.length) {
            articlesHtml = `<div style="margin-top: 16px"><div class="section-label">文章</div><div class="asset-list">` +
                p.articles.map(a => `
                <div class="asset ${!a.is_final ? 'draft-badge' : ''}">
                    <div class="asset-icon article">📄</div>
                    <a href="${a.path}" target="_blank">
                        <div class="asset-name">${a.name}</div>
                        <div class="asset-size">${a.size}</div>
                    </a>
                </div>`).join('') +
                '</div></div>';
        }

        let platformsHtml = '';
        if (p.adapted && Object.keys(p.adapted).length) {
            platformsHtml = `<div style="margin-top: 16px"><div class="section-label">平台版本</div><div class="platforms">` +
                Object.entries(p.adapted).map(([plat, info]) =>
                    `<span class="platform-badge" onclick="window.open('${info.path}')">${plat}</span>`
                ).join('') + '</div></div>';
        }

        card.innerHTML = `
            <div class="card-cover">
                ${coverHtml}
                <div class="card-overlay">
                    <span class="type-badge ${type}">${typeLabel}</span>
                    <div class="card-title">${p.project}</div>
                    <div class="card-meta">${p.videos.length} 视频 · ${p.articles.length} 文章</div>
                </div>
            </div>
            <div class="card-content">
                ${videosHtml}
                ${articlesHtml}
                ${platformsHtml}
            </div>
        `;
        grid.appendChild(card);
    });
}
load();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"🚀 VAAS 看板已启动: http://localhost:{PORT}")
    print(f"📂 扫描目录: {DOWNLOADS}")
    print("   Ctrl+C 停止\n")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 再见")
