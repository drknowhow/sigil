import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, MONO, SANS} from './theme';

export const FadeUp: React.FC<{
  delay?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({delay = 0, children, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - delay, fps, config: {damping: 200}});
  return (
    <div style={{opacity: p, transform: `translateY(${(1 - p) * 36}px)`, ...style}}>
      {children}
    </div>
  );
};

export const Type: React.FC<{
  text: string;
  start?: number;
  cps?: number; // chars per frame
  style?: React.CSSProperties;
}> = ({text, start = 0, cps = 1.6, style}) => {
  const frame = useCurrentFrame();
  const n = Math.max(0, Math.floor((frame - start) * cps));
  const shown = text.slice(0, n);
  const done = n >= text.length;
  return (
    <span style={{fontFamily: MONO, whiteSpace: 'pre-wrap', ...style}}>
      {shown}
      {!done && <span style={{color: C.cyan}}>▍</span>}
    </span>
  );
};

export const Term: React.FC<{
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({title, children, style}) => (
  <div
    style={{
      background: '#070b12',
      border: `1px solid ${C.line}`,
      borderRadius: 18,
      overflow: 'hidden',
      boxShadow: '0 30px 80px rgba(0,0,0,0.55)',
      ...style,
    }}
  >
    <div
      style={{
        display: 'flex',
        gap: 9,
        alignItems: 'center',
        padding: '14px 20px',
        borderBottom: `1px solid ${C.line}`,
        background: 'rgba(255,255,255,0.025)',
      }}
    >
      {[C.red, C.amber, '#34d399'].map((c) => (
        <div key={c} style={{width: 14, height: 14, borderRadius: 7, background: c}} />
      ))}
      <span style={{fontFamily: MONO, fontSize: 17, color: C.dim, marginLeft: 12}}>{title}</span>
    </div>
    <div style={{padding: '26px 30px', fontFamily: MONO, fontSize: 24, lineHeight: 1.75}}>
      {children}
    </div>
  </div>
);

export const Label: React.FC<{children: React.ReactNode; color?: string}> = ({
  children,
  color = C.cyan,
}) => (
  <span
    style={{
      fontFamily: MONO,
      fontSize: 19,
      letterSpacing: '0.18em',
      textTransform: 'uppercase',
      color,
    }}
  >
    {children}
  </span>
);

export const Big: React.FC<{children: React.ReactNode; size?: number}> = ({children, size = 64}) => (
  <h2 style={{fontFamily: SANS, fontSize: size, fontWeight: 800, letterSpacing: '-0.02em', color: C.txt, margin: 0}}>
    {children}
  </h2>
);

export const Dim: React.FC<{children: React.ReactNode; size?: number}> = ({children, size = 28}) => (
  <p style={{fontFamily: SANS, fontSize: size, color: C.dim, margin: 0, lineHeight: 1.55}}>{children}</p>
);

export const Counter: React.FC<{
  to: number;
  start?: number;
  dur?: number;
  suffix?: string;
  decimals?: number;
}> = ({to, start = 0, dur = 40, suffix = '', decimals = 0}) => {
  const frame = useCurrentFrame();
  const v = interpolate(frame, [start, start + dur], [0, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return <>{v.toFixed(decimals)}{suffix}</>;
};

export const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 90) * 40;
  return (
    <div style={{position: 'absolute', inset: 0, background: C.bg, overflow: 'hidden'}}>
      <div
        style={{
          position: 'absolute',
          width: 1400,
          height: 1400,
          left: 1100 + drift,
          top: -500,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(94,234,212,0.07), transparent 60%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: 1200,
          height: 1200,
          left: -400 - drift,
          top: 400,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(167,139,250,0.07), transparent 60%)',
        }}
      />
    </div>
  );
};
