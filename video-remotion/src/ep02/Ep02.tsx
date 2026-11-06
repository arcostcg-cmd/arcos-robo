import React, { useMemo } from "react";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  interpolate,
  random,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Crianca, Diretora } from "./personagens";
import {
  Brasas,
  CartaHolo,
  Credito,
  entra,
  Flash,
  fontes,
  FundoCarta,
  Grao,
  LARANJA,
  Marca,
  NOITE,
  OURO,
  Titulo,
  Tremor,
} from "./ui";

export type Cena = { tipo: string; inicioMs: number };
export type DadosEp = { audio: string; duracaoMs: number; legendas: Caption[]; cenas: Cena[] };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const CRED = "Imagem: The Pokémon Company (Coleção Clássica, 2021)";

// ---------------------------------------------------------------- cenas

const Gancho: React.FC = () => (
  <Tremor em={2}>
    <FundoCarta escuro={0.6} />
    <Brasas />
    <div style={{ position: "absolute", inset: 0, translate: "0px 120px" }}>
      <CartaHolo entrada="slam" largura={700} />
    </div>
    <Titulo texto="Essa carta fez escolas proibirem Pokémon" destaques={["ESCOLAS", "PROIBIREM"]} top={150} tam={92} atraso={4} />
    <Flash em={2} />
    <Credito texto={CRED} />
  </Tremor>
);

const Ano: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ frame: f, fps, config: { damping: 9 } });
  return (
    <AbsoluteFill style={{ background: "#120f1e" }}>
      <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0 2px, transparent 2px 6px)" }} />
      <div style={{ position: "absolute", top: 120, left: 70, fontFamily: "Montserrat", fontWeight: 800, fontSize: 34, color: "#ff5555", letterSpacing: 4 }}>
        ● REC <span style={{ color: "white", opacity: 0.8 }}>ESTADOS UNIDOS</span>
      </div>
      <div
        style={{
          position: "absolute",
          top: 520,
          width: "100%",
          textAlign: "center",
          fontFamily: "Anton",
          fontSize: 360,
          color: OURO,
          scale: interpolate(sp, [0, 1], [2.2, 1]),
          opacity: sp,
          textShadow: `${Math.sin(f) * 6}px 0 0 rgba(255,0,80,0.6), ${-Math.sin(f) * 6}px 0 0 rgba(0,200,255,0.6), 0 20px 0 #000`,
        }}
      >
        1999
      </div>
      <Grao />
    </AbsoluteFill>
  );
};

const Recreio: React.FC<{ brigaEm: number }> = ({ brigaEm }) => {
  const f = useCurrentFrame();
  const briga = f >= brigaEm;
  const puxa = briga ? Math.sin(f / 2.2) * 26 : Math.sin(f / 9) * 8;
  return (
    <Tremor em={brigaEm}>
      <AbsoluteFill style={{ background: "linear-gradient(#8fd3ff 0%, #c8ecff 45%, #6db56a 45%, #4e9a4c 100%)" }}>
        {/* escola ao fundo */}
        <svg width={1080} height={1920} style={{ position: "absolute" }}>
          <rect x={60} y={360} width={960} height={520} fill="#d96b4a" stroke="#14141f" strokeWidth={8} />
          <rect x={60} y={320} width={960} height={60} fill="#a94c33" stroke="#14141f" strokeWidth={8} />
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={120 + i * 230} y={440} width={150} height={160} fill="#bfe7ff" stroke="#14141f" strokeWidth={8} />
          ))}
          <rect x={460} y={660} width={160} height={220} fill="#6b3b2a" stroke="#14141f" strokeWidth={8} />
          <text x={540} y={410} textAnchor="middle" fontFamily="Montserrat" fontWeight={900} fontSize={44} fill="white">ESCOLA</text>
          {/* linhas de movimento na briga */}
          {briga
            ? new Array(10).fill(0).map((_, i) => (
                <line key={i} x1={540 + Math.cos(i) * 300} y1={1180 + Math.sin(i * 2) * 260} x2={540 + Math.cos(i) * 420} y2={1180 + Math.sin(i * 2) * 360}
                  stroke="white" strokeWidth={10} strokeLinecap="round" opacity={0.6 + 0.4 * Math.sin(f + i)} />
              ))
            : null}
          <Crianca x={250 - puxa} y={1720} escala={0.95} pele="#f0c39b" camisa="#3d7be0" camisaSombra="#2a58a8" cabelo="#2a1d18" bone="#e84a3c"
            olhar={1} boca={briga ? "bravo" : "sorriso"} bracoFrente={-6} inclina={briga ? -6 : 0} />
          <Crianca x={830 - puxa} y={1720} escala={0.95} pele="#a86d4a" camisa="#f2b51c" camisaSombra="#c48a0c" cabelo="#1d120c"
            olhar={1} boca={briga ? "grito" : "sorriso"} bracoFrente={-6} inclina={briga ? -6 : 0} espelhar />
          {/* a carta disputada (verso genérico) */}
          <g transform={`translate(${540 - puxa} 1250) rotate(${puxa / 3})`}>
            <rect x={-58} y={-80} width={116} height={160} rx={12} fill="#1f4fb5" stroke="#14141f" strokeWidth={7} />
            <circle cx={0} cy={0} r={34} fill="#e84a3c" stroke="#14141f" strokeWidth={6} />
            <rect x={-34} y={-4} width={68} height={8} fill="#14141f" />
          </g>
        </svg>
      </AbsoluteFill>
      <Grao />
    </Tremor>
  );
};

const Queria: React.FC<{ nomeEm: number }> = ({ nomeEm }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <FundoCarta escuro={0.5} />
      <Brasas n={60} />
      <CartaHolo entrada="sobe" largura={780} inclina={12} />
      {f >= nomeEm ? <Titulo texto="O Charizard" destaques={["CHARIZARD"]} top={1300} tam={150} /> : null}
      {f >= nomeEm ? <Flash em={nomeEm} /> : null}
      <Credito texto={CRED} />
    </AbsoluteFill>
  );
};

const Numeros: React.FC<{ danoEm: number }> = ({ danoEm }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const l = 960;
  const a = l * 1.396;
  // zoom no topo da carta (HP) e depois no ataque
  const foco = interpolate(f, [danoEm - 6, danoEm + 8], [0, 1], clamp);
  const ty = interpolate(foco, [0, 1], [a * 0.42, -a * 0.28]);
  const b1 = spring({ frame: f - 4, fps, config: { damping: 10 } });
  const b2 = spring({ frame: f - danoEm, fps, config: { damping: 10 } });
  return (
    <AbsoluteFill style={{ background: NOITE, overflow: "hidden" }}>
      <FundoCarta escuro={0.7} />
      <div style={{ position: "absolute", left: (1080 - l) / 2, top: 0, width: l, height: a, translate: `0px ${ty}px`, scale: 1.25 }}>
        <Img src={staticFile("charizard.png")} style={{ width: "100%", borderRadius: 40 }} />
        <div style={{ position: "absolute", left: "60%", top: "3.2%", width: "26%", height: "6.5%", border: `10px solid ${LARANJA}`, borderRadius: 20, scale: b1, boxShadow: `0 0 40px ${LARANJA}` }} />
        <div style={{ position: "absolute", left: "5%", top: "66%", width: "90%", height: "10%", border: `10px solid ${LARANJA}`, borderRadius: 20, scale: f >= danoEm ? b2 : 0, boxShadow: `0 0 40px ${LARANJA}` }} />
      </div>
      <div style={{ position: "absolute", top: 1250, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 190, color: "white", textShadow: "0 10px 0 #000" }}>
        {f < danoEm ? (
          <span style={{ scale: b1, display: "inline-block" }}>120 <span style={{ color: OURO }}>HP</span></span>
        ) : (
          <span style={{ scale: b2, display: "inline-block" }}>100 <span style={{ color: OURO }}>DANO</span></span>
        )}
      </div>
      <Credito texto={CRED} />
    </AbsoluteFill>
  );
};

const Proibido: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const carimbo = spring({ frame: f - 14, fps, config: { damping: 8, stiffness: 200 } });
  return (
    <Tremor em={14}>
      <AbsoluteFill style={{ background: "linear-gradient(#e9e2cf 0%, #d6ccb2 62%, #8d7d64 62%, #77684f 100%)" }}>
        <svg width={1080} height={1920} style={{ position: "absolute" }}>
          {[0, 1, 2].map((i) => (
            <rect key={i} x={40 + i * 350} y={420} width={300} height={760} fill="#4f7c8c" stroke="#14141f" strokeWidth={8} />
          ))}
          <rect x={150} y={250} width={780} height={300} rx={20} fill="white" stroke="#14141f" strokeWidth={10} />
          <text x={540} y={360} textAnchor="middle" fontFamily="Anton" fontSize={92} fill="#14141f">CARTAS POKÉMON</text>
          <text x={540} y={470} textAnchor="middle" fontFamily="Montserrat" fontWeight={800} fontSize={54} fill="#14141f">NO PÁTIO</text>
          <Diretora x={540} y={1800} escala={1.05} braco={Math.sin(f / 5) * 10} />
        </svg>
        <div
          style={{
            position: "absolute",
            top: 300,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: "Anton",
            fontSize: 210,
            color: "#e0242c",
            rotate: "-12deg",
            scale: interpolate(carimbo, [0, 1], [3, 1]),
            opacity: f >= 14 ? 1 : 0,
            textShadow: "0 0 0 #000",
          }}
        >
          <span style={{ border: "16px solid #e0242c", padding: "0 30px", borderRadius: 24, background: "rgba(255,255,255,0.75)" }}>PROIBIDO</span>
        </div>
      </AbsoluteFill>
      <Grao />
    </Tremor>
  );
};

const Valor: React.FC<{ numeroEm: number }> = ({ numeroEm }) => {
  const f = useCurrentFrame();
  const v = Math.round(interpolate(f, [numeroEm, numeroEm + 24], [0, 420000], clamp));
  const mostra = f >= numeroEm;
  return (
    <Tremor em={numeroEm}>
      <AbsoluteFill style={{ background: "#050508" }}>
        <div style={{ position: "absolute", top: 120, left: 70, fontFamily: "Montserrat", fontWeight: 800, fontSize: 34, color: OURO, letterSpacing: 4 }}>
          LEILÃO · 2022
        </div>
        {/* carta dentro de uma "cápsula" de nota 10 (genérica) */}
        <div style={{ position: "absolute", left: 300, top: 260, width: 480, height: 820, borderRadius: 36, background: "linear-gradient(160deg, rgba(255,255,255,0.35), rgba(255,255,255,0.08))", border: "6px solid rgba(255,255,255,0.6)", boxShadow: mostra ? "0 0 160px rgba(255,190,60,0.55)" : "none" }}>
          <div style={{ margin: 24, height: 110, borderRadius: 16, background: "#c8102e", color: "white", fontFamily: "Anton", fontSize: 64, textAlign: "center", lineHeight: "110px" }}>
            NOTA 10
          </div>
          <Img src={staticFile("charizard.png")} style={{ width: 400, marginLeft: 34, borderRadius: 18, opacity: interpolate(f, [0, 12], [0, 1], clamp) }} />
        </div>
        {mostra ? (
          <div style={{ position: "absolute", top: 1180, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 200, color: OURO, textShadow: "0 12px 0 #000" }}>
            US$ {v.toLocaleString("pt-BR")}
          </div>
        ) : null}
        {mostra ? <Brasas n={50} cor="255,210,90" /> : null}
        <Flash em={numeroEm} />
        <Credito texto={CRED} />
      </AbsoluteFill>
    </Tremor>
  );
};

const Grade: React.FC<{ destaqueEm: number }> = ({ destaqueEm }) => {
  const f = useCurrentFrame();
  const cols = 64;
  const n = 4993;
  const cheio = Math.round(interpolate(f, [0, 30], [0, n], clamp));
  const ouro = f >= destaqueEm;
  const dourados = useMemo(() => new Set(new Array(124).fill(0).map((_, i) => Math.floor(random(`d${i}`) * n))), []);
  return (
    <AbsoluteFill style={{ background: NOITE }}>
      <svg width={1080} height={1920} style={{ position: "absolute" }}>
        {new Array(cheio).fill(0).map((_, i) => {
          const x = 60 + (i % cols) * 15.2;
          const y = 380 + Math.floor(i / cols) * 15.2;
          const d = dourados.has(i);
          return <rect key={i} x={x} y={y} width={11} height={11} rx={2} fill={ouro ? (d ? OURO : "rgba(255,255,255,0.12)") : "rgba(255,255,255,0.55)"} />;
        })}
      </svg>
      <div style={{ position: "absolute", top: 190, width: "100%", textAlign: "center", fontFamily: "Anton", fontSize: 120, color: ouro ? OURO : "white", textShadow: "0 8px 0 #000" }}>
        {ouro ? "SÓ 124 NOTA 10" : `${cheio.toLocaleString("pt-BR")} AVALIADAS`}
      </div>
    </AbsoluteFill>
  );
};

const Final: React.FC = () => (
  <AbsoluteFill>
    <FundoCarta escuro={0.6} />
    <Brasas />
    <CartaHolo entrada="nenhuma" largura={720} zoom={[1.06, 1]} />
    <div style={{ position: "absolute", top: 1780, width: "100%", textAlign: "center", fontFamily: "Montserrat", fontWeight: 800, fontSize: 36, color: "rgba(255,255,255,0.8)" }}>
      Comenta aqui 👇
    </div>
    <Credito texto={CRED} />
  </AbsoluteFill>
);

// ---------------------------------------------------------------- legendas

const Legendas: React.FC<{ legendas: Caption[] }> = ({ legendas }) => {
  const { fps } = useVideoConfig();
  const { pages } = useMemo(() => createTikTokStyleCaptions({ captions: legendas, combineTokensWithinMilliseconds: 900 }), [legendas]);
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

const Pagina: React.FC<{ pagina: ReturnType<typeof createTikTokStyleCaptions>["pages"][number] }> = ({ pagina }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const agoraMs = pagina.startMs + (f / fps) * 1000;
  const sp = spring({ frame: f, fps, config: { damping: 14, stiffness: 220 } });
  return (
    <div style={{ position: "absolute", top: 1560, left: 60, right: 60, textAlign: "center", scale: interpolate(sp, [0, 1], [0.8, 1]) }}>
      {pagina.tokens.map((t, i) => {
        const ativo = t.fromMs <= agoraMs && agoraMs < t.toMs;
        return (
          <span
            key={i}
            style={{
              fontFamily: "Montserrat",
              fontWeight: 900,
              fontSize: 92,
              textTransform: "uppercase",
              color: ativo ? LARANJA : "white",
              WebkitTextStroke: "14px #000",
              paintOrder: "stroke fill",
              display: "inline-block",
              scale: ativo ? 1.08 : 1,
              margin: "0 16px",
            }}
          >
            {t.text.trim()}
          </span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- montagem

export const Ep02: React.FC<{ dados: DadosEp }> = ({ dados }) => {
  const { fps } = useVideoConfig();
  const fr = (ms: number) => Math.round((ms / 1000) * fps);
  const total = fr(dados.duracaoMs);
  const cenas = dados.cenas;
  const evento = (palavra: string, depoisMs: number) => {
    const w = dados.legendas.find((c) => c.startMs >= depoisMs && c.text.toLowerCase().includes(palavra));
    return w ? w.startMs : depoisMs;
  };
  const render = (c: Cena, dur: number) => {
    const rel = (ms: number) => Math.max(0, fr(ms - c.inicioMs));
    switch (c.tipo) {
      case "gancho":
        return <Gancho />;
      case "ano":
        return <Ano />;
      case "recreio":
        return <Recreio brigaEm={rel(evento("briga", c.inicioMs))} />;
      case "queria":
        return <Queria nomeEm={rel(evento("charizard", c.inicioMs))} />;
      case "numeros":
        return <Numeros danoEm={rel(evento("ataque", c.inicioMs))} />;
      case "proibido":
        return <Proibido />;
      case "valor":
        return <Valor numeroEm={rel(evento("420", c.inicioMs))} />;
      case "grade":
        return <Grade destaqueEm={rel(evento("124", c.inicioMs))} />;
      default:
        return <Final />;
    }
  };
  return (
    <AbsoluteFill style={{ background: NOITE }}>
      <style>{fontes}</style>
      {cenas.map((c, i) => {
        const de = fr(c.inicioMs);
        const ate = i + 1 < cenas.length ? fr(cenas[i + 1].inicioMs) : total;
        return (
          <Sequence key={i} from={de} durationInFrames={Math.max(1, ate - de)}>
            {render(c, ate - de)}
            {i > 0 ? <Audio src={staticFile("whoosh.wav")} volume={0.35} /> : null}
          </Sequence>
        );
      })}
      <Marca />
      <Legendas legendas={dados.legendas} />
      <Audio src={staticFile(dados.audio)} />
      <Audio src={staticFile("impacto.wav")} volume={0.9} />
      {(() => {
        const em = fr(evento("420", 0));
        return (
          <Sequence from={em}>
            <Audio src={staticFile("impacto.wav")} volume={0.9} />
          </Sequence>
        );
      })()}
      {(() => {
        const em = fr(evento("124", 0));
        return (
          <Sequence from={em}>
            <Audio src={staticFile("brilho.wav")} volume={0.5} />
          </Sequence>
        );
      })()}
    </AbsoluteFill>
  );
};
