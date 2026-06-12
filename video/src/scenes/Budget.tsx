import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, MONO} from '../theme';
import {Backdrop, Big, Dim, FadeUp, Label, Term} from '../ui';

export const Budget: React.FC = () => {
  const frame = useCurrentFrame();
  const flash = interpolate(frame, [95, 100, 130], [0, 0.16, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{padding: 100, justifyContent: 'center'}}>
      <Backdrop />
      <div style={{position: 'absolute', inset: 0, background: C.red, opacity: flash}} />
      <div style={{zIndex: 1}}>
        <FadeUp><Label color={C.red}>step 3 · the budget is enforced, statically</Label></FadeUp>
        <FadeUp delay={8} style={{marginTop: 14, marginBottom: 40}}>
          <Big>An AI sneaks in a cache write. The build says no.</Big>
        </FadeUp>
        <FadeUp delay={25} style={{width: 1500}}>
          <Term title="$ sigil build over_budget.sg">
            <div style={{fontSize: 24, lineHeight: 1.8}}>
              <div style={{color: C.comment}}>-- implementation calls save_cache() → open() — but fx: !net only</div>
              <div style={{opacity: frame > 60 ? 1 : 0, color: C.red, fontWeight: 700}}>
                sigil build: rejected.
              </div>
              <div style={{opacity: frame > 75 ? 1 : 0}}>
                effect budget exceeded for goal <span style={{color: C.txt}}>'fetch_prices'</span>:
              </div>
              <div style={{opacity: frame > 90 ? 1 : 0, paddingLeft: 28}}>
                fetch_prices → save_cache: <span style={{color: C.txt}}>open</span> requires{' '}
                <span style={{color: C.red, fontWeight: 700}}>!fs</span>; budget allows{' '}
                <span style={{color: C.amber}}>!net(api.example.com)</span>
              </div>
              <div style={{opacity: frame > 120 ? 1 : 0, color: C.cyan}}>
                Remedy: remove the call, or extend the goal's fx: budget if intended.
              </div>
            </div>
          </Term>
        </FadeUp>
        <FadeUp delay={150} style={{marginTop: 44}}>
          <Dim size={32}>
            No runtime sandbox needed — it's a <span style={{color: C.txt}}>call-graph check at build time</span>.
            Hidden I/O is the largest class of AI-generated risk, eliminated structurally.
          </Dim>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
