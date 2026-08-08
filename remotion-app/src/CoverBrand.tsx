import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { COLORS, FONT_SANS } from "./theme";

/**
 * 寻数科技品牌封面 —— 极简风格
 * 对齐 GitHub-dark 设计系统，和品牌视频视觉一致
 */

export const BrandCover: React.FC<{
  title: string;
  subtitle: string;
  tags?: string;
  orientation?: "horizontal" | "vertical";
  logo?: string;
}> = ({ title, subtitle, tags = "开源 · 数据 · AI", orientation = "horizontal", logo = "icon.png" }) => {
  const isVertical = orientation === "vertical";

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, ${COLORS.surface} 0%, ${COLORS.bg1} 100%)`,
        fontFamily: FONT_SANS,
        color: COLORS.text,
        justifyContent: "center",
        alignItems: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 淡绿色光晕 —— 右下 */}
      <div
        style={{
          position: "absolute",
          width: isVertical ? "70%" : "55%",
          height: isVertical ? "40%" : "80%",
          right: isVertical ? "-10%" : "5%",
          top: isVertical ? "10%" : "10%",
          background: `radial-gradient(circle, ${COLORS.green}18 0%, transparent 65%)`,
          pointerEvents: "none",
        }}
      />

      {/* 左上角 logo + 品牌名 */}
      <div
        style={{
          position: "absolute",
          top: isVertical ? 48 : 40,
          left: isVertical ? 48 : 56,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <Img
          src={logo ? staticFile(logo) : staticFile("icon.png")}
          style={{ width: isVertical ? 44 : 40, height: isVertical ? 44 : 40 }}
        />
        <span
          style={{
            fontSize: isVertical ? 20 : 18,
            fontWeight: 500,
            color: COLORS.muted,
            letterSpacing: 0.5,
          }}
        >
          寻数科技 · FindDataTechnology
        </span>
      </div>

      {/* 中央主标题 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: isVertical ? 28 : 20,
          marginTop: isVertical ? -80 : -20,
        }}
      >
        <h1
          style={{
            fontSize: isVertical ? 96 : 108,
            fontWeight: 700,
            margin: 0,
            color: COLORS.text,
            letterSpacing: 4,
          }}
        >
          {title}
        </h1>

        {/* 分割线 */}
        <div
          style={{
            width: isVertical ? 80 : 100,
            height: 3,
            background: COLORS.green,
            borderRadius: 2,
            marginTop: isVertical ? 4 : 0,
          }}
        />

        {/* 副标题（竖版两行，横版一行） */}
        {isVertical ? (
          <>
            <p
              style={{
                fontSize: 34,
                fontWeight: 400,
                margin: 0,
                color: COLORS.green,
                lineHeight: 1.5,
              }}
            >
              探索更开放更公平的
            </p>
            <p
              style={{
                fontSize: 34,
                fontWeight: 400,
                margin: 0,
                color: COLORS.green,
                lineHeight: 1.5,
                marginTop: -8,
              }}
            >
              AI 未来
            </p>
          </>
        ) : (
          <p
            style={{
              fontSize: 42,
              fontWeight: 400,
              margin: 0,
              color: COLORS.green,
              letterSpacing: 1,
            }}
          >
            {subtitle}
          </p>
        )}

        {/* 标签 */}
        <p
          style={{
            fontSize: isVertical ? 22 : 24,
            fontWeight: 300,
            margin: 0,
            marginTop: isVertical ? 36 : 32,
            color: COLORS.dim,
            letterSpacing: 2,
          }}
        >
          {tags}
        </p>
      </div>

      {/* 底部版权 */}
      <div
        style={{
          position: "absolute",
          bottom: isVertical ? 40 : 32,
          left: isVertical ? 48 : 56,
          fontSize: isVertical ? 16 : 14,
          color: COLORS.dim,
          fontWeight: 300,
          opacity: 0.8,
        }}
      >
        © 2026 FindDataTechnology
      </div>
    </AbsoluteFill>
  );
};

// ─── Title-Only 模板（极简大字） ────────────────────────────────
export const BrandCoverTitleOnly: React.FC<{
  title: string;
  subtitle?: string;
  orientation?: "horizontal" | "vertical";
  logo?: string;
}> = ({ title, subtitle = "", orientation = "horizontal", logo = "icon.png" }) => {
  const isVertical = orientation === "vertical";

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg1,
        fontFamily: FONT_SANS,
        color: COLORS.text,
        justifyContent: "center",
        alignItems: "center",
        position: "relative",
      }}
    >
      {/* 底部 Logo + 品牌名（小字，低调） */}
      <div
        style={{
          position: "absolute",
          bottom: isVertical ? 48 : 40,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          opacity: 0.5,
        }}
      >
        {logo && (
          <Img
            src={staticFile(logo)}
            style={{ width: isVertical ? 28 : 24, height: isVertical ? 28 : 24 }}
          />
        )}
        <span style={{ fontSize: isVertical ? 16 : 14, color: COLORS.muted }}>
          寻数科技 · FindDataTechnology
        </span>
      </div>

      {/* 居中大字标题 */}
      <h1
        style={{
          fontSize: isVertical ? 120 : 140,
          fontWeight: 700,
          margin: 0,
          color: COLORS.text,
          letterSpacing: 6,
          textAlign: "center",
          maxWidth: isVertical ? "85%" : "80%",
          lineHeight: 1.2,
        }}
      >
        {title}
      </h1>

      {/* 副标题（可选，小字灰色） */}
      {subtitle && (
        <p
          style={{
            position: "absolute",
            bottom: isVertical ? 120 : 100,
            fontSize: isVertical ? 24 : 20,
            color: COLORS.dim,
            fontWeight: 300,
            letterSpacing: 2,
            maxWidth: isVertical ? "80%" : "70%",
            textAlign: "center",
          }}
        >
          {subtitle}
        </p>
      )}
    </AbsoluteFill>
  );
};

// ─── Gradient 模板（渐变大字，冲击力强） ─────────────────────
export const BrandCoverGradient: React.FC<{
  title: string;
  subtitle?: string;
  tags?: string;
  orientation?: "horizontal" | "vertical";
  logo?: string;
}> = ({ title, subtitle = "", tags = "", orientation = "horizontal", logo = "icon.png" }) => {
  const isVertical = orientation === "vertical";

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${COLORS.bg0} 0%, ${COLORS.surface2} 100%)`,
        fontFamily: FONT_SANS,
        color: COLORS.text,
        justifyContent: "center",
        alignItems: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 背景装饰：几何线条 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background: `
            linear-gradient(90deg, transparent 49.5%, ${COLORS.green}10 49.5%, ${COLORS.green}10 50.5%, transparent 50.5%),
            linear-gradient(0deg, transparent 49.5%, ${COLORS.green}08 49.5%, ${COLORS.green}08 50.5%, transparent 50.5%)
          `,
          backgroundSize: "120px 120px",
          pointerEvents: "none",
        }}
      />

      {/* 左上角 logo */}
      <div
        style={{
          position: "absolute",
          top: isVertical ? 48 : 40,
          left: isVertical ? 48 : 56,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        {logo && (
          <Img
            src={staticFile(logo)}
            style={{ width: isVertical ? 40 : 36, height: isVertical ? 40 : 36 }}
          />
        )}
        <span style={{ fontSize: isVertical ? 18 : 16, color: COLORS.muted, fontWeight: 500 }}>
          FindDataTechnology
        </span>
      </div>

      {/* 渐变大标题 */}
      <h1
        style={{
          fontSize: isVertical ? 100 : 128,
          fontWeight: 800,
          margin: 0,
          background: `linear-gradient(135deg, ${COLORS.green} 0%, ${COLORS.cyan} 100%)`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          letterSpacing: 3,
          textAlign: "center",
          maxWidth: isVertical ? "90%" : "85%",
          lineHeight: 1.15,
        }}
      >
        {title}
      </h1>

      {/* 副标题 */}
      {subtitle && (
        <p
          style={{
            fontSize: isVertical ? 28 : 32,
            fontWeight: 400,
            color: COLORS.text,
            marginTop: 24,
            letterSpacing: 1,
            maxWidth: isVertical ? "85%" : "75%",
            textAlign: "center",
          }}
        >
          {subtitle}
        </p>
      )}

      {/* 标签 */}
      {tags && (
        <p
          style={{
            fontSize: isVertical ? 20 : 22,
            fontWeight: 300,
            color: COLORS.dim,
            marginTop: 32,
            letterSpacing: 3,
          }}
        >
          {tags}
        </p>
      )}
    </AbsoluteFill>
  );
};
