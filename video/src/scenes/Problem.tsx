import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, MONO, SANS} from '../theme';
import {Backdrop, Big, Dim, FadeUp, Label} from '../ui';

export const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const strike = interpolate(frame, [150, 175], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{padding: 120, justifyContent: 'center'}}>
      <Backdrop />
      <div style={{zIndex: 1}}>
        <FadeUp><Label color={C.violet}>the problem</Label></FadeUp>
        <FadeUp delay={8} style={{marginTop: 18}}>
          <Big size={72}>"Fetch the prices and cache them."</Big>
        </FadeUp>
        <FadeUp delay={30} style={{marginTop: 28, maxWidth: 1250}}>
          <Dim size={34}>
            …has <span style={{color: C.amber}}>hundreds of valid implementations</span> — and no way
            to check which one the AI gave you.
          </Dim>
        </FadeUp>
        <FadeUp delay={70} style={{marginTop: 60, display: 'flex', gap: 28}}>
          {[
            ['Natural language', 'optimized for ambiguity'],
            ['Mainstream code', 'throws the intent away'],
            ['AI review', 'hopes someone notices'],
          ].map(([t, d], i) => (
            <div
              key={t}
              style={{
                flex: 1,
                background: C.panel,
                border: `1px solid ${C.line}`,
                borderRadius: 20,
                padding: 34,
                position: 'relative',
              }}
            >
              <div style={{fontFamily: SANS, fontSize: 30, fontWeight: 700, color: C.txt}}>{t}</div>
              <div style={{fontFamily: SANS, fontSize: 24, color: C.dim, marginTop: 8}}>{d}</div>
              <div
                style={{
                  position: 'absolute',
                  left: '5%',
                  top: '50%',
                  height: 4,
                  width: `${(strike > i * 33 ? Math.min(90, (strike - i * 33) * 3) : 0)}%`,
                  background: C.red,
                  borderRadius: 2,
                }}
              />
            </div>
          ))}
        </FadeUp>
        <FadeUp delay={185} style={{marginTop: 60}}>
          <Big size={56}>
            Sigil's bet: make <span style={{color: C.cyan}}>intent</span>,{' '}
            <span style={{color: C.amber}}>effects</span> and{' '}
            <span style={{color: C.violet}}>verification</span> part of the language.
          </Big>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
