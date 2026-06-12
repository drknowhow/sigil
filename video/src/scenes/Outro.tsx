import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, MONO, SANS} from '../theme';
import {Backdrop, Label} from '../ui';

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame, fps, config: {damping: 200}});
  const out = interpolate(frame, [200, 255], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
      <Backdrop />
      <div style={{textAlign: 'center', zIndex: 1, opacity: pop}}>
        <h1
          style={{
            fontFamily: SANS,
            fontSize: 150,
            fontWeight: 800,
            letterSpacing: '-0.03em',
            margin: 0,
            backgroundImage: `linear-gradient(100deg, #fff 20%, ${C.cyan} 55%, ${C.violet} 90%)`,
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          SIGIL
        </h1>
        <p style={{fontFamily: SANS, fontSize: 38, color: C.txt, margin: '14px 0 40px'}}>
          Nothing is called done until <b>verification says so</b>.
        </p>
        <div
          style={{
            display: 'inline-block',
            fontFamily: MONO,
            fontSize: 27,
            color: C.cyan,
            background: '#070b12',
            border: `1px solid ${C.line}`,
            borderRadius: 14,
            padding: '20px 34px',
            textAlign: 'left',
            lineHeight: 1.9,
          }}
        >
          pip install -e ".[dev,harness]"<br />
          sigil lift your/code · sigil serve --root .
        </div>
        <div style={{marginTop: 36}}>
          <Label>open site/index.html → Quick Guide</Label>
        </div>
      </div>
    </AbsoluteFill>
  );
};
