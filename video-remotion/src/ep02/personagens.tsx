import React from "react";

/** Crianças originais (estilo cartoon flat com volume). Nada de Pokémon desenhado. */
type Kid = {
  pele: string;
  camisa: string;
  camisaSombra: string;
  cabelo: string;
  bone?: string;
  olhar?: number; // -1..1
  boca?: "grito" | "sorriso" | "bravo" | "o";
  bracoFrente?: number; // ângulo do braço que puxa (graus)
  inclina?: number;
  espelhar?: boolean;
  piscar?: boolean;
};

export const Crianca: React.FC<Kid & { x: number; y: number; escala?: number }> = ({
  x,
  y,
  escala = 1,
  pele,
  camisa,
  camisaSombra,
  cabelo,
  bone,
  olhar = 0,
  boca = "sorriso",
  bracoFrente = 0,
  inclina = 0,
  espelhar = false,
  piscar = false,
}) => {
  const contorno = "#14141f";
  const ox = olhar * 10;
  return (
    <g transform={`translate(${x} ${y}) scale(${espelhar ? -escala : escala} ${escala}) rotate(${inclina})`}>
      {/* sombra no chão */}
      <ellipse cx={0} cy={0} rx={150} ry={26} fill="rgba(0,0,0,0.35)" />
      {/* pernas */}
      <path d="M-50 -20 L-58 -230 L-8 -230 L-12 -20 Z" fill="#2c3550" stroke={contorno} strokeWidth={8} strokeLinejoin="round" />
      <path d="M12 -20 L8 -230 L58 -230 L50 -20 Z" fill="#2c3550" stroke={contorno} strokeWidth={8} strokeLinejoin="round" />
      <rect x={-80} y={-36} width={78} height={40} rx={18} fill="#f4f4f4" stroke={contorno} strokeWidth={8} />
      <rect x={10} y={-36} width={78} height={40} rx={18} fill="#f4f4f4" stroke={contorno} strokeWidth={8} />
      {/* braço de trás */}
      <path d="M-70 -470 Q-130 -380 -110 -300" fill="none" stroke={contorno} strokeWidth={56} strokeLinecap="round" />
      <path d="M-70 -470 Q-130 -380 -110 -300" fill="none" stroke={camisaSombra} strokeWidth={42} strokeLinecap="round" />
      <circle cx={-110} cy={-292} r={26} fill={pele} stroke={contorno} strokeWidth={7} />
      {/* tronco */}
      <path
        d="M-95 -520 Q0 -560 95 -520 L105 -230 Q0 -205 -105 -230 Z"
        fill={camisa}
        stroke={contorno}
        strokeWidth={9}
        strokeLinejoin="round"
      />
      <path d="M20 -540 Q90 -520 98 -470 L105 -235 Q60 -222 30 -222 Z" fill={camisaSombra} opacity={0.55} />
      {/* braço da frente (puxando) */}
      <g transform={`rotate(${bracoFrente} 70 -480)`}>
        <path d="M70 -480 Q170 -470 250 -470" fill="none" stroke={contorno} strokeWidth={56} strokeLinecap="round" />
        <path d="M70 -480 Q170 -470 250 -470" fill="none" stroke={camisa} strokeWidth={42} strokeLinecap="round" />
        <circle cx={262} cy={-470} r={28} fill={pele} stroke={contorno} strokeWidth={7} />
      </g>
      {/* pescoço */}
      <rect x={-26} y={-585} width={52} height={60} rx={14} fill={pele} stroke={contorno} strokeWidth={7} />
      {/* cabeça */}
      <g transform="translate(0 -720)">
        <ellipse cx={0} cy={0} rx={150} ry={158} fill={pele} stroke={contorno} strokeWidth={9} />
        <ellipse cx={-150} cy={20} rx={24} ry={34} fill={pele} stroke={contorno} strokeWidth={8} />
        {bone ? (
          <>
            <path d="M-150 -30 Q-140 -170 0 -172 Q140 -170 152 -30 Z" fill={bone} stroke={contorno} strokeWidth={9} />
            <path d="M40 -40 Q160 -52 230 -24 Q160 -8 40 -18 Z" fill={bone} stroke={contorno} strokeWidth={8} />
            <path d="M-118 -40 Q0 -70 118 -40" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth={10} />
          </>
        ) : (
          <path
            d="M-158 10 Q-170 -150 -40 -168 Q40 -200 120 -150 Q175 -110 160 0 Q140 -60 80 -90 Q20 -60 -60 -100 Q-120 -60 -158 10 Z"
            fill={cabelo}
            stroke={contorno}
            strokeWidth={9}
            strokeLinejoin="round"
          />
        )}
        {/* sobrancelhas */}
        <path
          d={boca === "bravo" ? `M${-80 + ox} -38 L${-28 + ox} -22 M${28 + ox} -22 L${80 + ox} -38` : `M${-82 + ox} -40 Q${-55 + ox} -52 ${-28 + ox} -40 M${28 + ox} -40 Q${55 + ox} -52 ${82 + ox} -40`}
          stroke={contorno}
          strokeWidth={10}
          strokeLinecap="round"
          fill="none"
        />
        {/* olhos */}
        {piscar ? (
          <path d={`M${-75 + ox} 6 Q${-55 + ox} 18 ${-35 + ox} 6 M${35 + ox} 6 Q${55 + ox} 18 ${75 + ox} 6`} stroke={contorno} strokeWidth={9} fill="none" strokeLinecap="round" />
        ) : (
          <>
            <ellipse cx={-55 + ox} cy={4} rx={26} ry={32} fill="white" stroke={contorno} strokeWidth={6} />
            <ellipse cx={55 + ox} cy={4} rx={26} ry={32} fill="white" stroke={contorno} strokeWidth={6} />
            <circle cx={-55 + ox * 1.6} cy={8} r={14} fill={contorno} />
            <circle cx={55 + ox * 1.6} cy={8} r={14} fill={contorno} />
            <circle cx={-50 + ox * 1.6} cy={2} r={5} fill="white" />
            <circle cx={60 + ox * 1.6} cy={2} r={5} fill="white" />
          </>
        )}
        {/* bochechas */}
        <ellipse cx={-92} cy={60} rx={24} ry={14} fill="#ff8a8a" opacity={0.45} />
        <ellipse cx={92} cy={60} rx={24} ry={14} fill="#ff8a8a" opacity={0.45} />
        {/* boca */}
        {boca === "grito" || boca === "o" ? (
          <ellipse cx={ox} cy={84} rx={boca === "o" ? 20 : 34} ry={boca === "o" ? 24 : 30} fill="#5a1b1b" stroke={contorno} strokeWidth={7} />
        ) : boca === "bravo" ? (
          <path d={`M${-36 + ox} 92 Q${ox} 70 ${36 + ox} 92`} stroke={contorno} strokeWidth={9} fill="none" strokeLinecap="round" />
        ) : (
          <path d={`M${-40 + ox} 74 Q${ox} 112 ${40 + ox} 74`} stroke={contorno} strokeWidth={9} fill="#5a1b1b" strokeLinecap="round" />
        )}
      </g>
    </g>
  );
};

/** Professora/diretora (adulta), original. */
export const Diretora: React.FC<{ x: number; y: number; escala?: number; braco?: number }> = ({ x, y, escala = 1, braco = 0 }) => {
  const c = "#14141f";
  return (
    <g transform={`translate(${x} ${y}) scale(${escala})`}>
      <ellipse cx={0} cy={0} rx={170} ry={28} fill="rgba(0,0,0,0.35)" />
      <path d="M-110 -20 L-130 -330 L130 -330 L110 -20 Z" fill="#3b2a4a" stroke={c} strokeWidth={9} />
      <path d="M-100 -640 Q0 -680 100 -640 L120 -320 L-120 -320 Z" fill="#7c3a52" stroke={c} strokeWidth={9} strokeLinejoin="round" />
      <g transform={`rotate(${braco} 90 -600)`}>
        <path d="M90 -600 Q200 -640 260 -760" fill="none" stroke={c} strokeWidth={56} strokeLinecap="round" />
        <path d="M90 -600 Q200 -640 260 -760" fill="none" stroke="#7c3a52" strokeWidth={42} strokeLinecap="round" />
        <circle cx={266} cy={-772} r={28} fill="#e9b892" stroke={c} strokeWidth={7} />
      </g>
      <rect x={-26} y={-705} width={52} height={70} rx={14} fill="#e9b892" stroke={c} strokeWidth={7} />
      <g transform="translate(0 -840)">
        <path d="M-150 60 Q-175 -160 0 -170 Q175 -160 150 60 Z" fill="#2a1d18" stroke={c} strokeWidth={9} />
        <ellipse cx={0} cy={0} rx={132} ry={148} fill="#e9b892" stroke={c} strokeWidth={9} />
        <path d="M-132 -20 Q-110 -150 0 -150 Q110 -150 132 -20 Q90 -90 0 -96 Q-90 -90 -132 -20 Z" fill="#2a1d18" stroke={c} strokeWidth={8} />
        <circle cx={-50} cy={6} r={30} fill="none" stroke={c} strokeWidth={7} />
        <circle cx={50} cy={6} r={30} fill="none" stroke={c} strokeWidth={7} />
        <path d="M-20 6 L20 6" stroke={c} strokeWidth={7} />
        <circle cx={-50} cy={8} r={10} fill={c} />
        <circle cx={50} cy={8} r={10} fill={c} />
        <path d="M-80 -42 L-22 -30 M22 -30 L80 -42" stroke={c} strokeWidth={10} strokeLinecap="round" />
        <path d="M-34 84 Q0 66 34 84" stroke={c} strokeWidth={9} fill="none" strokeLinecap="round" />
      </g>
    </g>
  );
};
