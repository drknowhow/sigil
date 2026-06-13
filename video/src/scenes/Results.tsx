import React from 'react';
import {AbsoluteFill} from 'remotion';
import {C, MONO, SANS} from '../theme';
import {Backdrop, Big, Counter, Dim, FadeUp, Label} from '../ui';

const Stat: React.FC<{
  value: React.ReactNode;
  label: string;
  delay: number;
}> = ({value, label, delay}) => (
  <FadeUp
    delay={delay}
    style={{
      flex: 1,
      background: C.panel,
      border: `1px solid ${C.line}`,
      borderRadius: 22,
      padding: '40px 36px',
    }}
  >
    <div style={{fontFamily: MONO, fontSize: 76, fontWeight: 700, color: C.cyan}}>{value}</div>
    <div style={{fontFamily: SANS, fontSize: 23, color: C.dim, marginTop: 10, lineHeight: 1.5}}>{label}</div>
  </FadeUp>
);

export const Results: React.FC = () => (
  <AbsoluteFill style={{padding: 110, justifyContent: 'center'}}>
    <Backdrop />
    <div style={{zIndex: 1}}>
      <FadeUp><Label color={C.violet}>measured, not estimated</Label></FadeUp>
      <FadeUp delay={8} style={{marginTop: 14, marginBottom: 46}}>
        <Big>v2.0.1 — every number below is from the actual build</Big>
      </FadeUp>
      <div style={{display: 'flex', gap: 24}}>
        <Stat delay={20} value={<Counter to={185} start={25} />} label="tests green · 92% coverage on core / lift / transpile" />
        <Stat delay={35} value={<><Counter to={5.9} start={40} decimals={1} />×</>} label="measured context reduction — requests 2.34.2, real BPE tokenizer" />
        <Stat delay={50} value={<Counter to={0} start={55} />} label="effect under-reports across 33 hand-labeled fixtures" />
        <Stat delay={65} value="<50ms" label="verify cache hit on unchanged code — verdicts keyed by hash, forever" />
      </div>
      <FadeUp delay={130} style={{marginTop: 50}}>
        <Dim size={30}>
          Honest where it matters: the spec guessed 10×+ — measurement said{' '}
          <span style={{color: C.txt}}>5.9× at first contact</span>; the bigger wins compound
          per-iteration, and those are measured too.
        </Dim>
      </FadeUp>
    </div>
  </AbsoluteFill>
);
