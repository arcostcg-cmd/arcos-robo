import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  random,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const LARANJA = "#FF9900";
export const OURO = "#FFC93C";
export const NOITE = "#0B0E24";

export const fontes = `
@font-face { font-family: 'Montserrat'; src: url('${staticFile("Montserrat.ttf")}'); font-weight: 100 900; }
@font-face { font-family: 'Anton'; src: url('${staticFile("Anton-Regular.ttf")}'); }
`;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Fundo: a própria carta enorme e desfocada + vinheta + grão (cinema). */
export const FundoCarta: React.FC<{ escuro?: number; cor?: string }> = ({ escuro = 0.55, cor }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: NOITE, overflow: "hidden" }}>
      <Img
        src={staticFile("charizard.png")}
        style={{
          position: "absolute",
          width: "160%",
          left: "-30%",
          top: "-10%",
          filter: "blur(60px) saturate(1.5)",
          opacity: 0.85,
          scale: interpolate(f, [0, 300], [1, 1.15], clamp),
        }}
      />
      {cor ? <AbsoluteFill style={{ background: cor, mixBlendMode: "multiply" }} /> : null}
      <AbsoluteFill
        style={{ background: `radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 20%, rgba(0,0,0,${escuro + 0.3}) 80%)` }}
      />
      <AbsoluteFill style={{ background: `rgba(5,6,16,${escuro * 0.5})` }} />
      <Grao />
    </AbsoluteFill>
  );
};

export const Grao: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: 0.07, pointerEvents: "none" }}>
      <svg width="100%" height="100%">
        <filter id={`g${f % 4}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" seed={f % 4} numOctaves={2} />
        </filter>
        <rect width="100%" height="100%" filter={`url(#g${f % 4})`} />
      </svg>
    </AbsoluteFill>
  );
};

/** Poeira/brasa subindo (dá vida ao quadro parado). */
export const Brasas: React.FC<{ n?: number; cor?: string }> = ({ n = 40, cor = "255,180,80" }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {new Array(n).fill(0).map((_, i) => {
        const x = random(`x${i}`) * 1080;
        const vel = 1 + random(`v${i}`) * 3;
        const y = 1920 - ((f * vel + random(`y${i}`) * 1920) % 2100);
        const s = 3 + random(`s${i}`) * 7;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x + Math.sin(f / 20 + i) * 20,
              top: y,
              width: s,
              height: s,
              borderRadius: s,
              background: `rgba(${cor},${0.35 + random(`o${i}`) * 0.5})`,
              boxShadow: `0 0 ${s * 3}px rgba(${cor},0.8)`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/** A carta oficial com brilho holográfico passando, inclinação 3D e sombra. */
export const CartaHolo: React.FC<{
  largura?: number;
  entrada?: "slam" | "sobe" | "nenhuma";
  inclina?: number;
  zoom?: [number, number];
  origem?: string;
}> = ({ largura = 760, entrada = "sobe", inclina = 8, zoom = [1, 1.06], origem = "50% 50%" }) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const sp = spring({ frame: f, fps, config: { damping: entrada === "slam" ? 11 : 18, stiffness: 140 } });
  const escalaEntrada =
    entrada === "slam" ? interpolate(sp, [0, 1], [1.9, 1]) : entrada === "sobe" ? interpolate(sp, [0, 1], [0.85, 1]) : 1;
  const yEntrada = entrada === "sobe" ? interpolate(sp, [0, 1], [180, 0]) : 0;
  const brilho = interpolate(f % 75, [0, 75], [-60, 160]);
  const alt = largura * 1.396;
  return (
    <div
      style={{
        position: "absolute",
        left: (1080 - largura) / 2,
        top: 960 - alt / 2 - 230,
        width: largura,
        height: alt,
        perspective: 1400,
        translate: `0px ${yEntrada}px`,
        scale: escalaEntrada * interpolate(f, [0, durationInFrames], zoom, clamp),
        transformOrigin: origem,
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          borderRadius: largura * 0.045,
          overflow: "hidden",
          rotate: `y ${Math.sin(f / 28) * inclina}deg`,
          boxShadow: `0 60px 120px rgba(0,0,0,0.65), 0 0 120px rgba(255,140,40,${0.25 + 0.15 * Math.sin(f / 9)})`,
          position: "relative",
        }}
      >
        <Img src={staticFile("charizard.png")} style={{ width: "100%", height: "100%", display: "block" }} />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(115deg, rgba(255,255,255,0) ${brilho - 20}%, rgba(255,255,255,0.55) ${brilho}%, rgba(170,220,255,0.25) ${brilho + 6}%, rgba(255,255,255,0) ${brilho + 22}%)`,
            mixBlendMode: "screen",
          }}
        />
      </div>
    </div>
  );
};

/** Texto de impacto (Anton, caixa alta) com palavras destacadas. */
export const Titulo: React.FC<{ texto: string; destaques?: string[]; top?: number; tam?: number; atraso?: number }> = ({
  texto,
  destaques = [],
  top = 150,
  tam = 104,
  atraso = 0,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ frame: f - atraso, fps, config: { damping: 14 } });
  const d = new Set(destaques.map((x) => x.toUpperCase()));
  return (
    <div
      style={{
        position: "absolute",
        top,
        left: 70,
        right: 70,
        textAlign: "center",
        fontFamily: "Anton",
        fontSize: tam,
        lineHeight: 1.02,
        color: "white",
        textTransform: "uppercase",
        opacity: sp,
        translate: `0px ${interpolate(sp, [0, 1], [40, 0])}px`,
        textShadow: "0 6px 0 rgba(0,0,0,0.9), 0 0 40px rgba(0,0,0,0.6)",
      }}
    >
      {texto.split(" ").map((p, i) => (
        <span key={i} style={{ color: d.has(p.replace(/[^\wÀ-ÿ$]/g, "").toUpperCase()) ? OURO : "white" }}>
          {p}{" "}
        </span>
      ))}
    </div>
  );
};

export const Credito: React.FC<{ texto: string }> = ({ texto }) => (
  <div
    style={{
      position: "absolute",
      bottom: 48,
      left: 60,
      fontFamily: "Montserrat",
      fontWeight: 600,
      fontSize: 24,
      color: "rgba(255,255,255,0.55)",
    }}
  >
    {texto}
  </div>
);

export const Marca: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 70,
      left: 60,
      fontFamily: "Montserrat",
      fontWeight: 900,
      fontSize: 30,
      letterSpacing: 3,
      color: "white",
      opacity: 0.85,
      padding: "8px 18px",
      borderRadius: 12,
      background: "rgba(0,0,0,0.35)",
    }}
  >
    MONTOP<span style={{ color: OURO }}>TCG</span>
  </div>
);

export const Flash: React.FC<{ em: number }> = ({ em }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [em, em + 2, em + 9], [0, 0.75, 0], clamp);
  return <AbsoluteFill style={{ background: "white", opacity: o, pointerEvents: "none" }} />;
};

export const Tremor: React.FC<{ em: number; children: React.ReactNode }> = ({ em, children }) => {
  const f = useCurrentFrame();
  const k = interpolate(f, [em, em + 14], [1, 0], clamp) * (f >= em ? 1 : 0);
  return (
    <AbsoluteFill style={{ translate: `${Math.sin(f * 2.3) * 22 * k}px ${Math.cos(f * 3.1) * 18 * k}px` }}>
      {children}
    </AbsoluteFill>
  );
};

export const entra = (f: number, de: number, dur = 12) =>
  interpolate(f, [de, de + dur], [0, 1], { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) });
