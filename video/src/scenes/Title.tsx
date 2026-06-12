import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, MONO, SANS} from '../theme';
import {Backdrop, Label} from '../ui';

export const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame, fps, config: {damping: 14, mass: 0.8}});
  const sub = spring({frame: frame - 22, fps, config: {damping: 200}});
  const tag = interpolate(frame, [45, 70], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <Backdrop />
      <div style={{textAlign: 'center', zIndex: 1}}>
        <h1
          style={{
            fontFamily: SANS,
            fontSize: 230,
            fontWeight: 800,
            letterSpacing: '-0.03em',
            margin: 0,
            transform: `scale(${0.8 + pop * 0.2})`,
            backgroundImage: `linear-gradient(100deg, #fff 20%, ${C.cyan} 55%, ${C.violet} 90%)`,
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          SIGIL
        </h1>
        <p
          style={{
            fontFamily: SANS,
            fontSize: 42,
            color: C.txt,
            margin: '10px 0 0',
            opacity: sub,
            transform: `translateY(${(1 - sub) * 30}px)`,
          }}
        >
          Code an AI can't quietly get wrong.
        </p>
        <div style={{marginTop: 36, opacity: tag}}>
          <Label>contract-first · content-addressed · effect-typed · verified</Label>
        </div>
      </div>
    </AbsoluteFill>
  );
};
