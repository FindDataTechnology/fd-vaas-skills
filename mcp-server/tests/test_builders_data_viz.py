"""
data-viz builder 测试（add-typed-video-html-renderer W2.3）。


覆盖:
  - validate_inputs 结构数对照（1 hook + N 图表段 + 1 cta == data.charts 数，
    一次列全）与 data 形状校验（type/values/series/labels 长度、pie 非负非全零）
  - build 场景结构（hook / 图表卡×N / CTA）、echarts 内联（仅图表卡）、
    seek 契约、零外链（find_external_refs 同源）、palette 取色（theme 色板进
    DATA 岛 + idx 槽位色）、句级字幕岛、animS=40% 段时长、署名位、
    Python 侧 build 纯度（同输入两次 build 逐字节一致）
  - seek 纯函数（node + echarts 桩，option 级）：每次 seek 恰一次 setOption
    且 notMerge；同 t 跨调用历史同 option；animS 后收敛稳定；动画确实在动
  - build_typed_storyboard 走 type gate（renderer=html + builder 注册）、
    tailPad、landscape 画幅、结构违规先于 TTS（零产物）
  - 真渲染冒烟（chromium/ffmpeg 可用才跑，口径同 test_determinism W6.2）：
    ffmpeg 合成 3s voice → render_video(type=data-viz) 双跑（不同 slug）
    framemd5 帧级一致 + mp4 容器 md5 一致；图表段帧内有变化（动画在动）

playwright/ffmpeg/TTS 全部 mock（真渲染仅冒烟类实跑）。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
def _render_plane_available() -> bool:
    """渲染面可达性（W4 起真实出片必须经渲染面）。"""
    import os, socket
    from urllib.parse import urlparse
    url = os.getenv("VAAS_RENDER_URL", "http://127.0.0.1:8099")
    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname or "127.0.0.1", u.port or 80), 1):
            return True
    except OSError:
        return False


sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server.db.database as database
import mcp_server.utils.file_manager as file_manager
from mcp_server.db import init_schema
from mcp_server.tools import render as render_mod
from mcp_server.tools import typed_scenes as ts
from mcp_server.tools.typed_scenes import alignment as align_mod
from mcp_server.tools._scene_guard import find_external_refs


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every DB access at a throwaway database."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db)
    init_schema(db)
    return db


@pytest.fixture
def hermetic_fs(tmp_path, monkeypatch):
    """Redirect downloads/ 与 typed_scenes 的目录绑定到 tmp_path。"""
    root = tmp_path / "hermetic"
    downloads = root / "downloads"
    downloads.mkdir(parents=True)
    monkeypatch.setattr(render_mod, "VAAS_ROOT", root)
    monkeypatch.setattr(file_manager, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(ts, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(ts, "VAAS_ROOT", root)
    monkeypatch.setattr(ts, "ensure_directory_rel",
                        lambda *parts: _mkdir(downloads.joinpath(*parts)))
    monkeypatch.setattr(align_mod, "DOWNLOADS_DIR", downloads)
    monkeypatch.setattr(align_mod, "VAAS_ROOT", root)
    return {"root": root, "downloads": downloads}


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


SCRIPT = ("## 开场\n用三十秒看懂这组关键数据。\n"
          "## 营收柱状图\n先看柱状图，四个季度的营收逐季走高。\n"
          "## 增速折线图\n再看折线图，下半年增速明显放缓。\n"
          "## 结尾\n关注我们，下期再见。")
DATA = {"title": "三季度经营速览", "source": "FindData",
        "charts": [
            {"type": "bar", "title": "季度营收",
             "labels": ["Q1", "Q2", "Q3", "Q4"],
             "values": [120, 200, 150, 260], "unit": "万元"},
            {"type": "line", "title": "月度增速",
             "labels": ["1月", "2月", "3月"],
             "values": [3, 5, 4], "unit": "%"},
        ]}
DATA_PIE = {"title": "渠道构成", "source": "FindData",
            "charts": [
                {"type": "pie", "title": "流量渠道",
                 "labels": ["直投", "自然流", "搜索"],
                 "values": [45, 30, 25], "unit": "%"}]}
SCRIPT_PIE = "## 开场\n看渠道构成。\n## 渠道饼图\n直投占四成五。\n## 结尾\n下期见。"


def _aligned_segments(raw, durations):
    out = []
    for seg, d in zip(raw, durations):
        out.append({"name": seg["name"], "text": seg["text"],
                    "duration_s": d,
                    "sentences": align_mod._sentences_with_timings(
                        seg["text"], d)})
    return out


# ─── validate_inputs：结构数对照 + data 形状 ────────────────────────────────

class TestDataVizValidate:
    def setup_method(self):
        self.builder = ts.BUILDER_REGISTRY["data-viz"]
        self.raw = align_mod.split_script(SCRIPT)

    def test_valid_structure_passes(self):
        self.builder.validate_inputs(
            {"data": DATA}, align_mod.skeleton_segments(self.raw))

    def test_pie_data_passes(self):
        raw = align_mod.split_script(SCRIPT_PIE)
        self.builder.validate_inputs(
            {"data": DATA_PIE}, align_mod.skeleton_segments(raw))

    def test_count_mismatch_lists_both_sides(self):
        bad = {"title": "T", "charts": [DATA["charts"][0]]}
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"data": bad}, align_mod.skeleton_segments(self.raw))
        msg = str(exc.value)
        assert "口播图表段数 2" in msg and "data.charts 数 1" in msg
        assert "hook" in msg and "cta" in msg  # 对照面点名
        assert "渲染前零产物" in msg

    def test_all_violations_listed_at_once(self):
        bad = {"charts": [
            {"type": "scatter", "values": ["x"]},        # 类型 + values 元素
            {"type": "bar"},                              # bar 无 values/series
            {"type": "pie", "values": [-1, 0]},           # pie 负值
            {"type": "bar", "values": [1], "labels": ["a", "b"]},  # labels 数
        ]}
        with pytest.raises(ValueError) as exc:
            self.builder.validate_inputs(
                {"data": bad}, align_mod.skeleton_segments(self.raw[:2] + [{"name": "x", "text": "y"}]))
        msg = str(exc.value)
        assert "data.charts[0].type" in msg
        assert "data.charts[0].values[0]" in msg
        assert "data.charts[1]（bar）需要 values 或 series" in msg
        assert "data.charts[2]（pie）values 须非负" in msg
        assert "data.charts[3].labels 数 2 != 数据点数 1" in msg
        assert "data.title" in msg  # 顶层违规同屏列全

    def test_pie_all_zero_rejected(self):
        bad = {"title": "T", "charts": [{"type": "pie", "values": [0, 0]}]}
        with pytest.raises(ValueError, match="values 不能全为 0"):
            self.builder.validate_inputs(
                {"data": bad},
                align_mod.skeleton_segments(align_mod.split_script(
                    "## a\nx\n## b\ny\n## c\nz")))

    def test_pie_with_series_rejected(self):
        bad = {"title": "T", "charts": [
            {"type": "pie", "values": [1], "series": [{"name": "s", "values": [1]}]}]}
        with pytest.raises(ValueError, match="series 仅 bar/line 支持"):
            self.builder.validate_inputs(
                {"data": bad},
                align_mod.skeleton_segments(align_mod.split_script(
                    "## a\nx\n## b\ny\n## c\nz")))

    def test_multi_series_bar_accepted(self):
        bad = {"title": "T", "charts": [
            {"type": "bar", "labels": ["a", "b"],
             "series": [{"name": "s1", "values": [1, 2]},
                        {"name": "s2", "values": [3, 4]}]}]}
        self.builder.validate_inputs(
            {"data": bad},
            align_mod.skeleton_segments(align_mod.split_script(
                "## a\nx\n## b\ny\n## c\nz")))

    def test_series_length_mismatch_rejected(self):
        bad = {"title": "T", "charts": [
            {"type": "bar",
             "series": [{"name": "s1", "values": [1, 2]},
                        {"name": "s2", "values": [3]}]}]}
        with pytest.raises(ValueError, match="values 长度须一致"):
            self.builder.validate_inputs(
                {"data": bad},
                align_mod.skeleton_segments(align_mod.split_script(
                    "## a\nx\n## b\ny\n## c\nz")))

    def test_structure_needs_three_segments(self):
        with pytest.raises(ValueError, match=r"1 hook \+ N 图表段 \+ 1 cta"):
            self.builder.validate_inputs(
                {"data": DATA}, align_mod.skeleton_segments(self.raw[:1]))

    def test_missing_data_object(self):
        with pytest.raises(ValueError, match="inputs.data 必须是 JSON 对象"):
            self.builder.validate_inputs({}, align_mod.skeleton_segments(self.raw))


# ─── build：场景结构 / seek 契约 / palette / 字幕岛 ─────────────────────────

class TestDataVizBuild:
    @pytest.fixture
    def built(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.0, 2.0])
        theme = ts.load_theme()
        return builder.build(segs, {"data": DATA}, [1080, 1920], theme), segs

    def test_scene_structure(self, built):
        scenes, segs = built
        assert len(scenes) == 4
        assert [s["kind"] for s in scenes] == ["html_full"] * 4
        assert [s["name"] for s in scenes] == [g["name"] for g in segs]
        assert [s["duration_s"] for s in scenes] == [2.0, 3.0, 2.0, 2.0]

    def test_echarts_inlined_only_in_chart_cards(self, built):
        scenes, _ = built
        assert "echarts.init(" in scenes[1]["html"]
        assert "echarts.init(" in scenes[2]["html"]
        assert "echarts.init(" not in scenes[0]["html"]  # hook 不带图表内核
        assert "echarts.init(" not in scenes[3]["html"]  # CTA 同
        # vendor 单一来源：内联体积与盘上文件一致
        from mcp_server.tools.still_chart import ECHARTS_JS_PATH
        assert ECHARTS_JS_PATH.read_text(encoding="utf-8") in scenes[1]["html"]

    def test_seek_contract_and_zero_external_refs(self, built):
        scenes, _ = built
        for s in scenes:
            html = s["html"]
            assert "data-stage" in html
            assert "window.__DURATION__" in html
            assert "window.__SIZE__=[1080,1920]" in html
            assert "window.seek = function (t)" in html
            assert "window.seek(0)" in html
            assert find_external_refs(html) == []  # 零外链硬校验同源（含内联 echarts 面）

    def test_brand_wrapper_and_theme_palette(self, built):
        scenes, _ = built
        html = scenes[1]["html"]
        assert "--vaas-accent:" in html and "--vaas-font-sans:" in html
        # 配色 MUST 取 theme palette：色板 hex 注入 DATA 岛（canvas 面取色）
        assert '"palette":["#58a6ff","#3fb950"' in html
        # idx 序号槽位色：图表 1 → palette[0]，图表 2 → palette[1]
        assert 'style="color:#58a6ff"' in scenes[1]["html"]
        assert 'style="color:#3fb950"' in scenes[2]["html"]
        # 色值全部来自 theme，业务硬编码色不出现（island 面断言）
        assert '"#ff0000"' not in json.dumps(DATA, ensure_ascii=False)

    def test_anim_window_is_40pct_of_segment(self, built):
        scenes, _ = built
        # 段时长 3.0 → 动画窗 1.2s；2.0 → 0.8s（type.json desc：占段帧 40%）
        assert '"animS":1.2' in scenes[1]["html"]
        assert '"animS":0.8' in scenes[2]["html"]

    def test_anim_floor_for_degenerate_duration(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [0.0, 0.0, 0.0, 0.0])
        theme = ts.load_theme()
        scenes = builder.build(segs, {"data": DATA}, [1080, 1920], theme)
        assert '"animS":0.05' in scenes[1]["html"]  # 零时长退化下限

    def test_sentence_subtitle_island(self, built):
        scenes, segs = built
        chart_html = scenes[1]["html"]
        sents = segs[1]["sentences"]
        assert json.dumps(sents[0]["text"], ensure_ascii=False) in chart_html
        assert "SENTS[i].start" in chart_html  # seek 查表驱动
        assert "__DURATION__=3.0" in chart_html

    def test_chart_island_and_data_drivers(self, built):
        scenes, _ = built
        bar_html = scenes[1]["html"]
        line_html = scenes[2]["html"]
        assert '"kind":"bar"' in bar_html and "makeBarSeeker" in bar_html
        assert '"kind":"line"' in line_html and "makeLineSeeker" in line_html
        assert '"values":[120,200,150,260]' in bar_html
        assert '"unit":"万元"' in bar_html
        assert '"title":"季度营收"' in bar_html
        assert "animation: false" in bar_html and "animation: false" in line_html

    def test_source_attribution_on_hook_and_cta_only(self, built):
        scenes, _ = built
        assert '"source":"FindData"' in scenes[0]["html"]  # hook 署名位
        assert "'来源：' + DATA.source" in scenes[0]["html"]
        assert '"source":"FindData"' in scenes[3]["html"]  # CTA 署名位
        assert scenes[1]["html"].count("来源：") == 0      # 图表卡不重复署名
        # 图表卡 DATA 岛不注入 source（echarts vendor 源码本身含 "source" 字样，
        # 断言收窄到业务值）
        assert '"source":"FindData"' not in scenes[1]["html"]

    def test_cta_reveals_sentences_stepwise(self, built):
        scenes, segs = built
        cta = scenes[3]["html"]
        assert cta.count('class="line"') == len(segs[3]["sentences"])
        assert "DATA.sentences[i].start" in cta

    def test_pie_build_normalization_and_buffer(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT_PIE)
        segs = _aligned_segments(raw, [1.0, 2.0, 1.0])
        theme = ts.load_theme()
        scenes = builder.build(segs, {"data": DATA_PIE}, [1080, 1920], theme)
        pie_html = scenes[1]["html"]
        assert '"kind":"pie"' in pie_html and "makePieSeeker" in pie_html
        assert '"pieItems":[{"name":"直投","value":45}' in pie_html
        assert "transparent" in pie_html  # 扫描缓冲扇区
        assert '"animS":0.8' in pie_html

    def test_labels_fallback_when_absent(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [1.0, 1.0, 1.0, 1.0])
        theme = ts.load_theme()
        data = {"title": "T", "charts": [{"type": "bar", "values": [1, 2, 3]}]}
        scenes = builder.build(segs, {"data": data}, [1080, 1920], theme)
        assert '"labels":["1","2","3"]' in scenes[1]["html"]
        assert '"title":"图表 1"' in scenes[1]["html"]  # title 缺省

    def test_build_is_byte_deterministic(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.0, 2.0])
        theme = ts.load_theme()
        a = builder.build(segs, {"data": DATA}, [1080, 1920], theme)
        b = builder.build(segs, {"data": DATA}, [1080, 1920], theme)
        assert [s["html"] for s in a] == [s["html"] for s in b]

    def test_landscape_orientation(self):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [1.0, 1.0, 1.0, 1.0])
        theme = ts.load_theme()
        scenes = builder.build(segs, {"data": DATA}, [1920, 1080], theme)
        assert "window.__SIZE__=[1920,1080]" in scenes[1]["html"]

    def test_builder_contract_surface(self):
        """契约面稳定：type_id + validate_inputs/build 签名（W1.1 契约）。"""
        builder = ts.BUILDER_REGISTRY["data-viz"]
        assert builder.type_id == "data-viz"
        import inspect
        vp = list(inspect.signature(builder.validate_inputs).parameters)
        bp = list(inspect.signature(builder.build).parameters)
        assert vp == ["inputs", "segments"]
        assert bp == ["segments", "inputs", "size", "theme"]


# ─── seek 纯函数（node + echarts 桩，option 级确定性） ──────────────────────

_SEEK_PURITY_HARNESS = r"""
const fs = require('fs');
const html = fs.readFileSync(process.env.VAAS_HTML, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]);
if (scripts.length !== 3) {
  throw new Error('expected 3 scripts (duration/echarts/seek), got '
    + scripts.length);
}
const els = {};
function el(id) { if (!els[id]) { els[id] = { style: {}, textContent: '' }; }
  return els[id]; }
const setOptions = [];
global.document = { getElementById: el, querySelectorAll: () => [] };
global.echarts = { init: () => ({
  setOption: (o, m) => setOptions.push({ o: JSON.stringify(o),
                                         notMerge: m === true }) }) };
global.window = {};
eval(scripts[0]);                 // window.__DURATION__/__SIZE__
eval(scripts[2]);                 // SEEK_HELPERS + DATA + 驱动器 + 卡片 glue
function frame(t) { setOptions.length = 0; window.seek(t);
  return setOptions[0]; }
const D = window.__DURATION__;
const out = { scripts: scripts.length, D: D };
out.perSeek = (() => { setOptions.length = 0; window.seek(D * 0.2);
  return { count: setOptions.length,
           notMerge: setOptions[0] ? setOptions[0].notMerge : null }; })();
// 帧采样：0 → animS 内多点 → 收敛尾（easeOutCubic 前倾，扫描/生长在中段
// 即可能到终态，故用「状态数」断言动画推进而非单点不等）
out.frames = [0, D * 0.05, D * 0.1, D * 0.2, D * 0.4, D, D * 10]
  .map(frame).map(f => f.o);
// 打乱调用历史后再取同 t 帧：必须与首跑一致（seek 纯函数）
frame(D); frame(D * 0.5); frame(0); frame(D * 10);
out.historyA = frame(D * 0.2).o;
frame(D * 10); frame(D * 0.7);
out.historyB = frame(0).o;
process.stdout.write(JSON.stringify(out));
"""


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node unavailable "
                    "(seek-purity check runs the scene JS under node)")
class TestSeekPurity:
    """seek(t) 纯函数：同 t 同帧（option 级），历史无关；动画确实在动。"""

    def _run(self, html: str, tmp_path: Path) -> dict:
        page = tmp_path / "scene.html"
        page.write_text(html, encoding="utf-8")
        env = {**os.environ, "VAAS_HTML": str(page)}
        proc = subprocess.run(["node", "-e", _SEEK_PURITY_HARNESS],
                              capture_output=True, text=True, env=env,
                              timeout=60)
        assert proc.returncode == 0, f"node harness failed: {proc.stderr[-500:]}"
        return json.loads(proc.stdout)

    def _assert_pure(self, out: dict):
        assert out["scripts"] == 3
        assert out["perSeek"]["count"] == 1          # 每次 seek 恰一次 setOption
        assert out["perSeek"]["notMerge"] is True    # notMerge：渲染只依赖本帧 option
        frames = out["frames"]
        assert len(set(frames)) >= 3, "animation does not move (few states)"
        assert frames[-2] == frames[-1], "not converged after animS"
        assert out["historyA"] == frames[3], "seek(t) is history-dependent"
        assert out["historyB"] == frames[0], "seek(0) is history-dependent"

    def test_bar_seek_pure(self, tmp_path):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.0, 2.0])
        scenes = builder.build(segs, {"data": DATA}, [1080, 1920],
                               ts.load_theme())
        self._assert_pure(self._run(scenes[1]["html"], tmp_path))

    def test_line_seek_pure(self, tmp_path):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT)
        segs = _aligned_segments(raw, [2.0, 3.0, 2.0, 2.0])
        scenes = builder.build(segs, {"data": DATA}, [1080, 1920],
                               ts.load_theme())
        self._assert_pure(self._run(scenes[2]["html"], tmp_path))

    def test_pie_seek_pure(self, tmp_path):
        builder = ts.BUILDER_REGISTRY["data-viz"]
        raw = align_mod.split_script(SCRIPT_PIE)
        segs = _aligned_segments(raw, [1.0, 2.0, 1.0])
        scenes = builder.build(segs, {"data": DATA_PIE}, [1080, 1920],
                               ts.load_theme())
        self._assert_pure(self._run(scenes[1]["html"], tmp_path))


# ─── build_typed_storyboard：type gate / tailPad / 先校验后 TTS ─────────────

class TestDataVizStoryboard:
    def test_type_gate_passes_with_html_renderer(self, hermetic_fs, monkeypatch):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        storyboard, meta = ts.build_typed_storyboard(
            "data-viz", SCRIPT, {"data": DATA}, voice_path=str(wav))
        assert storyboard["size"] == [1080, 1920]
        assert len(storyboard["scenes"]) == 4
        assert meta["type"] == "data-viz" and meta["renderer"] == "html"
        assert meta["composition"] == "DataVizVideo"
        assert [s["name"] for s in meta["segments"]] == \
            ["开场", "营收柱状图", "增速折线图", "结尾"]
        assert meta["tail_pad_frames"] == 15

    def test_count_mismatch_fails_before_tts(self, hermetic_fs, monkeypatch):
        def _boom(*a, **kw):
            raise AssertionError("TTS must not run before validate_inputs")
        monkeypatch.setattr("mcp_server.generators.tts.synthesize", _boom)
        bad = {"title": "T", "charts": [DATA["charts"][0]]}
        with pytest.raises(ValueError, match="渲染前零产物"):
            ts.build_typed_storyboard("data-viz", SCRIPT, {"data": bad})

    def test_landscape_through_gate(self, hermetic_fs, monkeypatch):
        wav = hermetic_fs["downloads"] / "voice.wav"
        wav.write_bytes(b"fake-audio")
        monkeypatch.setattr(align_mod, "_ffprobe_seconds", lambda p: 8.0)
        storyboard, _ = ts.build_typed_storyboard(
            "data-viz", SCRIPT, {"data": DATA, "orientation": "1920x1080"},
            voice_path=str(wav))
        assert "window.__SIZE__=[1920,1080]" in storyboard["scenes"][1]["html"]


# ─── 真渲染冒烟（chromium + ffmpeg 实跑；口径同 test_determinism W6.2） ─────

def _chromium_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    import os
    pinned = os.getenv("VAAS_CHROMIUM_EXECUTABLE")
    if pinned and Path(pinned).is_file():
        return True
    if Path("/usr/bin/chromium").is_file():
        return True
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


def _md5(path: Path) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def _framemd5_hashes(path: Path) -> list:
    """ffmpeg 解码帧级 md5——只取视频流（首列 0；混流 mp4 还带音频帧，须滤除
    才能与 render_video 的帧数/场景帧区间对齐）。"""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "framemd5", "-"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"framemd5 failed: {proc.stderr[-300:]}")
    return [line.split(",")[-1].strip().lower()
            for line in proc.stdout.splitlines()
            if line.startswith("0,") and not line.startswith("#")]


@pytest.mark.real_render
@pytest.mark.skipif(not _render_plane_available(), reason="渲染面不可达（VAAS_RENDER_URL），真实出片冒烟跳过")
@pytest.mark.skipif(not _chromium_available(), reason="chromium unavailable "
                    "(data-viz real-render smoke needs real playwright+chromium)")
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg unavailable "
                    "(data-viz real-render smoke needs ffmpeg)")
class TestDataVizRealRenderSmoke:
    """真渲染冒烟：voice_path（ffmpeg 合成 3s）→ mp4；双跑确定性。

    确定性口径（同 W6.2）：帧级 framemd5 一致是契约本体；容器字节 md5
    一致是最强口径（本机 ffmpeg mov muxer 默认不写创建时间戳，实测可比）。
    图表动画确定性 = seek 纯函数（同 t 同帧）+ animation:false 纯 setOption
    逐帧重放；本冒烟另断言图表段帧内有变化（动画确实在动）。
    """

    FPS = 12

    @pytest.fixture
    def voice_3s(self, hermetic_fs):
        """ffmpeg 合成 3s 音频（sine 440Hz，不依赖 TTS/网络）。"""
        wav = hermetic_fs["downloads"] / "voice-smoke.wav"
        proc = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=3",
             "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
            capture_output=True, text=True)
        assert proc.returncode == 0, f"ffmpeg synth failed: {proc.stderr[-300:]}"
        return str(wav)

    def test_double_run_md5_and_chart_animation(self, hermetic_fs, monkeypatch,
                                                voice_3s):
        monkeypatch.delenv("VAAS_HOSTED", raising=False)  # 本地模式
        render = lambda slug: render_mod.render_video(
            type="data-viz", script=SCRIPT, inputs={"data": DATA},
            voice_path=voice_3s, slug=slug, fps=self.FPS)
        ra, rb = render("dv-smoke-a"), render("dv-smoke-b")

        assert ra["type"] == "data-viz" and ra["slug"] != rb["slug"]
        assert ra["frames"] == rb["frames"]
        assert ra["format"] == "mp4"
        fa = hermetic_fs["downloads"] / ra["file_path"]
        fb = hermetic_fs["downloads"] / rb["file_path"]
        assert fa.is_file() and fb.is_file()

        # 帧级口径（确定性契约本体）。帧数 = min(渲染帧, 音频秒×fps)：
        # compose 的 -shortest 以音频收尾，逐段 round(d*fps) 之和可略超
        ha, hb = _framemd5_hashes(fa), _framemd5_hashes(fb)
        rendered = ra["frames"]
        voice_s = render_mod._ffprobe_seconds(voice_3s)
        assert len(ha) == len(hb) == round(voice_s * self.FPS) <= rendered, \
            "decoded frame count off"
        assert ha == hb, "decoded frames differ between double runs"
        # 容器字节口径（最强；与 W6.2 同机实测可比）
        assert _md5(fa) == _md5(fb), "mp4 container bytes differ"

        # 图表段（bar = 场景 1）帧内有变化：柱状生长动画确实在动
        sb = json.loads(
            (fa.parent / "storyboard.json").read_text(encoding="utf-8"))
        fps, offset = self.FPS, 0
        for i, sc in enumerate(sb["scenes"]):
            n = int(round(float(sc["duration_s"]) * fps))
            if i == 1:  # bar 图表段
                seg_md5s = ha[offset:offset + n]
                assert len(set(seg_md5s)) >= 2, \
                    "chart segment frames are static — animation not driving"
                break
            offset += n
