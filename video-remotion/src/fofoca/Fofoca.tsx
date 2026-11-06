// Formato "Fofoca TCG" (Montop): investigação curta com provas na tela.
// Tudo vem do JSON do episódio (public/<ep>.json): cenas, textos, áudio e legendas.
import React, { useMemo } from "react";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

export const AMARELO = "#FFD400";
const FUNDO = "#0a0a0c";
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const fontes = `
@font-face { font-family: 'Montserrat'; src: url('${staticFile("Montserrat.ttf")}'); font-weight: 100 900; }
@font-face { font-family: 'Anton'; src: url('${staticFile("Anton-Regular.ttf")}'); }
`;

type Linha = { rotulo: string; valor: string; destaque?: boolean };
export type CenaF = {
  tipo: "capa" | "linhas" | "duplo" | "citacao" | "numero" | "aviso" | "cta";
  inicioMs: number;
  kicker?: string;
  titulo?: string; // palavras entre *asteriscos* ganham faixa amarela
  sub?: string;
  carta?: string;
  linhas?: Linha[];
  esquerda?: Linha[];
  direita?: Linha[];
  numero?: string;
  autor?: string;
  selo?: string;
  palavra?: string;
  credito?: string;
};
export type DadosF = { audio: string; duracaoMs: number; legendas: Caption[]; cenas: CenaF[]; fontes: string };

const useEntrada = (atraso = 0, damping = 13) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: f - atraso, fps, config: { damping, stiffness: 160 } });
};

// ---------------------------------------------------------------- peças

const Fundo: React.FC = () => {
  const f = useCurrentFrame();
  const pulso = 0.85 + Math.sin(f / 18) * 0.15;
  return (
    <AbsoluteFill style={{ background: FUNDO }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 45% at 50% 42%, rgba(255,212,0,${0.22 * pulso}) 0%, rgba(255,212,0,0.05) 45%, transparent 70%)`,
        }}
      />
      <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0 2px, transparent 2px 5px)" }} />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.75) 100%)" }} />
    </AbsoluteFill>
  );
};

const Kicker: React.FC<{ texto: string; top?: number }> = ({ texto, top = 150 }) => {
  const e = useEntrada(0, 16);
  return (
    <div
      style={{
        position: "absolute",
        top,
        left: 70,
        fontFamily: "Montserrat",
        fontWeight: 900,
        fontSize: 40,
        letterSpacing: 5,
        color: AMARELO,
        opacity: e,
        translate: `${interpolate(e, [0, 1], [-40, 0])}px 0`,
      }}
    >
      • {texto.toUpperCase()}
    </div>
  );
};

/** Título grande; trechos entre *asteriscos* ficam numa faixa amarela. */
const Titulo: React.FC<{ texto: string; top: number; tam?: number }> = ({ texto, top, tam: t0 }) => {
  const tam = t0 ?? (texto.length > 22 ? 86 : 104);
  const partes = texto.split("*");
  const e = useEntrada(2, 11);
  return (
    <div
      style={{
        position: "absolute",
        top,
        left: 60,
        right: 60,
        textAlign: "center",
        fontFamily: "Anton",
        fontSize: tam,
        lineHeight: 1.22,
        color: "white",
        textTransform: "uppercase",
        scale: interpolate(e, [0, 1], [1.25, 1]),
        opacity: e,
        textShadow: "0 8px 0 rgba(0,0,0,0.6)",
      }}
    >
      {partes.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} style={{ background: AMARELO, color: "#000", padding: "0 18px", borderRadius: 10, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone", textShadow: "none" }}>
            {p.replace(/ /g, "\u00a0")}
          </span>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </div>
  );
};

const Carta: React.FC<{ src: string; top: number; largura: number; atraso?: number }> = ({ src, top, largura, atraso = 0 }) => {
  const f = useCurrentFrame();
  const e = useEntrada(atraso, 10);
  const brilho = ((f * 9) % 1400) - 300;
  return (
    <div
      style={{
        position: "absolute",
        top,
        left: (1080 - largura) / 2,
        width: largura,
        aspectRatio: "245 / 342",
        borderRadius: 26,
        overflow: "hidden",
        boxShadow: `0 0 80px rgba(255,212,0,0.35), 0 40px 80px rgba(0,0,0,0.8)`,
        scale: interpolate(e, [0, 1], [0.6, 1]),
        opacity: e,
        rotate: `${Math.sin(f / 30) * 1.5}deg`,
      }}
    >
      <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <div
        style={{
          position: "absolute",
          top: 0,
          left: brilho,
          width: 160,
          height: "100%",
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.28), transparent)",
          rotate: "18deg",
        }}
      />
    </div>
  );
};

const Pilula: React.FC<{ texto: string; tam?: number }> = ({ texto, tam = 64 }) => (
  <span style={{ display: "inline-block", background: AMARELO, color: "#000", fontFamily: "Anton", fontSize: tam, padding: "6px 26px", borderRadius: 14, letterSpacing: 2 }}>
    {texto}
  </span>
);

/** Painel de prova: etiqueta escura com linhas rótulo/valor. */
const Painel: React.FC<{ linhas: Linha[]; titulo?: string; largura: number; atraso?: number; marca?: boolean }> = ({ linhas, titulo, largura, atraso = 0, marca }) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        width: largura,
        background: "linear-gradient(180deg, #1b1b20, #121216)",
        border: `3px solid ${marca ? AMARELO : "rgba(255,255,255,0.14)"}`,
        borderRadius: 26,
        padding: "34px 38px",
        boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
      }}
    >
      {titulo ? (
        <div style={{ fontFamily: "Montserrat", fontWeight: 900, fontSize: 30, letterSpacing: 4, color: AMARELO, marginBottom: 18 }}>{titulo.toUpperCase()}</div>
      ) : null}
      {linhas.map((l, i) => {
        const e = interpolate(f - atraso - i * 9, [0, 10], [0, 1], clamp);
        return (
          <div key={i} style={{ opacity: e, translate: `0 ${(1 - e) * 30}px`, padding: "16px 0", borderTop: i ? "2px solid rgba(255,255,255,0.08)" : "none" }}>
            <div style={{ fontFamily: "Montserrat", fontWeight: 700, fontSize: 34, color: "rgba(255,255,255,0.65)" }}>{l.rotulo}</div>
            <div style={{ fontFamily: "Anton", fontSize: l.destaque ? 92 : 66, color: l.destaque ? AMARELO : "white", lineHeight: 1.1 }}>{l.valor}</div>
          </div>
        );
      })}
    </div>
  );
};

const Credito: React.FC<{ texto?: string }> = ({ texto }) =>
  texto ? (
    <div style={{ position: "absolute", bottom: 70, left: 60, right: 60, textAlign: "center", fontFamily: "Montserrat", fontWeight: 600, fontSize: 24, color: "rgba(255,255,255,0.5)" }}>{texto}</div>
  ) : null;

const Selo: React.FC<{ texto: string; top: number }> = ({ texto, top }) => {
  const e = useEntrada(6, 8);
  return (
    <div style={{ position: "absolute", top, width: "100%", textAlign: "center", scale: interpolate(e, [0, 1], [1.8, 1]), opacity: e, rotate: "-3deg" }}>
      <span style={{ display: "inline-block", border: `5px solid ${AMARELO}`, color: AMARELO, background: "rgba(0,0,0,0.75)", fontFamily: "Montserrat", fontWeight: 900, fontSize: 40, letterSpacing: 3, padding: "14px 30px", borderRadius: 12 }}>
        {texto.toUpperCase()}
      </span>
    </div>
  );
};

// ---------------------------------------------------------------- cenas

const Cena: React.FC<{ c: CenaF }> = ({ c }) => {
  const f = useCurrentFrame();
  switch (c.tipo) {
    case "capa":
      return (
        <>
          {c.kicker ? <Kicker texto={c.kicker} /> : null}
          {c.titulo ? <Titulo texto={c.titulo} top={230} /> : null}
          {c.carta ? <Carta src={c.carta} top={560} largura={600} atraso={4} /> : null}
          {c.numero ? (
            <div style={{ position: "absolute", top: 1420, width: "100%", textAlign: "center", opacity: interpolate(f, [10, 18], [0, 1], clamp) }}>
              <Pilula texto={c.numero} tam={80} />
            </div>
          ) : null}
        </>
      );
    case "linhas":
      return (
        <>
          {c.kicker ? <Kicker texto={c.kicker} /> : null}
          {c.titulo ? <Titulo texto={c.titulo} top={230} tam={88} /> : null}
          <div style={{ position: "absolute", top: c.titulo ? 520 : 300, left: 90 }}>
            <Painel linhas={c.linhas ?? []} largura={900} atraso={6} />
          </div>
          {c.selo ? <Selo texto={c.selo} top={1330} /> : null}
        </>
      );
    case "duplo":
      return (
        <>
          {c.kicker ? <Kicker texto={c.kicker} /> : null}
          {c.titulo ? <Titulo texto={c.titulo} top={230} tam={92} /> : null}
          <div style={{ position: "absolute", top: 600, left: 30, right: 30, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Painel linhas={c.esquerda ?? []} largura={440} atraso={4} />
            <Painel linhas={c.direita ?? []} largura={440} atraso={14} marca />
          </div>
          {c.carta ? <Carta src={c.carta} top={900} largura={300} atraso={20} /> : null}
          <div style={{ position: "absolute", top: 560, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 150, color: AMARELO, opacity: interpolate(f, [20, 26], [0, 1], clamp), textShadow: "0 0 40px rgba(0,0,0,0.9)" }}>=</div>
          {c.selo ? <Selo texto={c.selo} top={1380} /> : null}
        </>
      );
    case "citacao": {
      const e = interpolate(f, [4, 14], [0, 1], clamp);
      return (
        <>
          {c.kicker ? <Kicker texto={c.kicker} /> : null}
          <div style={{ position: "absolute", top: 420, left: 70, right: 70, opacity: e, translate: `0 ${(1 - e) * 40}px` }}>
            <div style={{ background: "#16161b", border: "2px solid rgba(255,255,255,0.14)", borderRadius: 26, padding: "48px 50px" }}>
              <div style={{ fontFamily: "Anton", fontSize: 120, color: AMARELO, lineHeight: 0.7 }}>“</div>
              <div style={{ fontFamily: "Montserrat", fontWeight: 800, fontSize: 60, color: "white", lineHeight: 1.25 }}>{c.titulo}</div>
              {c.autor ? <div style={{ marginTop: 34, fontFamily: "Montserrat", fontWeight: 700, fontSize: 32, color: "rgba(255,255,255,0.6)" }}>— {c.autor}</div> : null}
            </div>
          </div>
          {c.carta ? <Carta src={c.carta} top={1080} largura={260} atraso={12} /> : null}
          {c.selo ? <Selo texto={c.selo} top={940} /> : null}
        </>
      );
    }
    case "numero": {
      const e = useEntrada(0, 7);
      return (
        <>
          {c.kicker ? <Kicker texto={c.kicker} /> : null}
          <div style={{ position: "absolute", top: 560, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 300, color: AMARELO, scale: interpolate(e, [0, 1], [2.4, 1]), opacity: e, textShadow: "0 0 80px rgba(255,212,0,0.45)" }}>
            {c.numero}
          </div>
          {c.titulo ? <Titulo texto={c.titulo} top={960} tam={84} /> : null}
        </>
      );
    }
    case "aviso":
      return (
        <>
          <div style={{ position: "absolute", top: 200, width: "100%", textAlign: "center", fontFamily: "Montserrat", fontWeight: 800, fontSize: 34, letterSpacing: 8, color: "rgba(255,255,255,0.7)" }}>{(c.kicker ?? "").toUpperCase()}</div>
          {c.carta ? <Carta src={c.carta} top={330} largura={470} /> : null}
          {c.titulo ? (
            <div style={{ position: "absolute", top: 1010, left: 70, right: 70, textAlign: "center", opacity: interpolate(f, [6, 14], [0, 1], clamp), rotate: "-2deg" }}>
              <span style={{ display: "inline-block", background: AMARELO, color: "#000", fontFamily: "Anton", fontSize: 76, lineHeight: 1.1, padding: "16px 32px", borderRadius: 14, textTransform: "uppercase" }}>{c.titulo}</span>
            </div>
          ) : null}
          {c.sub ? <div style={{ position: "absolute", top: 1260, left: 80, right: 80, textAlign: "center", fontFamily: "Montserrat", fontWeight: 700, fontSize: 40, color: "white", lineHeight: 1.3 }}>{c.sub}</div> : null}
        </>
      );
    default: {
      const e = useEntrada(0, 8);
      return (
        <>
          <div style={{ position: "absolute", top: 380, width: "100%", textAlign: "center", fontFamily: "Montserrat", fontWeight: 900, fontSize: 56, letterSpacing: 10, color: "white" }}>COMENTA</div>
          <div style={{ position: "absolute", top: 470, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 230, color: AMARELO, scale: interpolate(e, [0, 1], [2, 1]), opacity: e, textShadow: "0 0 70px rgba(255,212,0,0.5)" }}>
            {c.palavra}
          </div>
          {c.sub ? <div style={{ position: "absolute", top: 790, left: 80, right: 80, textAlign: "center", fontFamily: "Montserrat", fontWeight: 800, fontSize: 48, color: "white", lineHeight: 1.3 }}>{c.sub}</div> : null}
          {c.carta ? <Carta src={c.carta} top={980} largura={340} atraso={8} /> : null}
        </>
      );
    }
  }
};

// ---------------------------------------------------------------- legendas (2 palavras, 1 amarela)

const Legendas: React.FC<{ legendas: Caption[] }> = ({ legendas }) => {
  const { fps } = useVideoConfig();
  const { pages } = useMemo(() => createTikTokStyleCaptions({ captions: legendas, combineTokensWithinMilliseconds: 600 }), [legendas]);
  return (
    <AbsoluteFill>
      {pages.map((pg, i) => {
        const prox = pages[i + 1];
        const de = Math.round((pg.startMs / 1000) * fps);
        const ate = Math.round(((prox ? prox.startMs : pg.startMs + 1500) / 1000) * fps);
        if (ate <= de) return null;
        return (
          <Sequence key={i} from={de} durationInFrames={ate - de} layout="none">
            <Pagina pagina={pg} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const limpa = (t: string) => {
  const x = t.trim().replace(/[.,;:]+$/, "");
  return x === x.toUpperCase() && x.length > 2 && /[A-Z]/.test(x) ? x : x.toLowerCase();
};

const Pagina: React.FC<{ pagina: ReturnType<typeof createTikTokStyleCaptions>["pages"][number] }> = ({ pagina }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const agoraMs = pagina.startMs + (f / fps) * 1000;
  const sp = spring({ frame: f, fps, config: { damping: 15, stiffness: 240 } });
  return (
    <div style={{ position: "absolute", top: 1600, left: 50, right: 50, textAlign: "center", scale: interpolate(sp, [0, 1], [0.85, 1]) }}>
      {pagina.tokens.map((t, i) => {
        const ativo = t.fromMs <= agoraMs && agoraMs < t.toMs;
        return (
          <span key={i} style={{ fontFamily: "Montserrat", fontWeight: 900, fontSize: 82, color: ativo ? AMARELO : "white", WebkitTextStroke: "12px #000", paintOrder: "stroke fill", display: "inline-block", margin: "0 12px" }}>
            {limpa(t.text)}
          </span>
        );
      })}
    </div>
  );
};

const Marca: React.FC = () => (
  <div style={{ position: "absolute", top: 70, right: 60, fontFamily: "Montserrat", fontWeight: 900, fontSize: 30, letterSpacing: 3, color: "rgba(255,255,255,0.75)" }}>
    @MONTOPTCG · <span style={{ color: AMARELO }}>FOFOCA TCG</span>
  </div>
);

// ---------------------------------------------------------------- montagem

export const Fofoca: React.FC<{ dados: DadosF }> = ({ dados }) => {
  const { fps } = useVideoConfig();
  const fr = (ms: number) => Math.round((ms / 1000) * fps);
  const total = fr(dados.duracaoMs);
  return (
    <AbsoluteFill style={{ background: FUNDO }}>
      <style>{fontes}</style>
      <Fundo />
      {dados.cenas.map((c, i) => {
        const de = fr(c.inicioMs);
        const ate = i + 1 < dados.cenas.length ? fr(dados.cenas[i + 1].inicioMs) : total;
        return (
          <Sequence key={i} from={de} durationInFrames={Math.max(1, ate - de)}>
            <Cena c={c} />
            <Credito texto={c.credito} />
            <Audio src={staticFile(i === 0 || c.tipo === "numero" || c.tipo === "cta" ? "impacto.wav" : "whoosh.wav")} volume={i === 0 ? 0.8 : 0.4} />
          </Sequence>
        );
      })}
      <Marca />
      <Legendas legendas={dados.legendas} />
      <Audio src={staticFile(dados.audio)} />
    </AbsoluteFill>
  );
};
