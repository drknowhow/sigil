import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {C, MONO} from '../theme';
import {Backdrop, Big, FadeUp, Label, Term} from '../ui';

const Ann: React.FC<{top: number; color: string; text: string; delay: number}> = ({top, color, text, delay}) => {
  const frame = useCurrentFrame();
  const on = frame >= delay;
  return (
    <div
      style={{
        position: 'absolute',
        right: -440,
        top,
        width: 400,
        opacity: on ? 1 : 0,
        transform: `translateX(${on ? 0 : 20}px)`,
        fontFamily: MONO,
        fontSize: 21,
        color,
        borderLeft: `3px solid ${color}`,
        paddingLeft: 16,
        lineHeight: 1.45,
      }}
    >
      {text}
    </div>
  );
};

export const Goal: React.FC = () => {
  return (
    <AbsoluteFill style={{padding: 100, justifyContent: 'center'}}>
      <Backdrop />
      <div style={{zIndex: 1}}>
        <FadeUp><Label color={C.violet}>step 2 · write the contract, not the code</Label></FadeUp>
        <FadeUp delay={8} style={{marginTop: 14, marginBottom: 40}}>
          <Big>A goal is the entire human contribution</Big>
        </FadeUp>
        <FadeUp delay={20} style={{position: 'relative', width: 1080}}>
          <Term title="prices.sg">
            <div style={{fontSize: 25, lineHeight: 1.8}}>
              <div><span style={{color: C.violet}}>goal</span> fetch_prices {'{'}</div>
              <div>  intent: <span style={{color: C.cyan}}>"Daily OHLCV for the given tickers"</span></div>
              <div>  in: tickers [Str], start Str, end Str</div>
              <div>  out: Map</div>
              <div>  fx: <span style={{color: C.amber}}>!net(api.example.com)</span></div>
              <div>  verify:</div>
              <div>    <span style={{color: C.cyan}}>out.keys.set == tickers.set</span></div>
              <div>{'}'}</div>
            </div>
          </Term>
          <Ann top={88} color={C.cyan} text="intent — for humans, kept with the code" delay={55} />
          <Ann top={205} color={C.amber} text="effect BUDGET — the implementation may use at most this" delay={85} />
          <Ann top={290} color={C.violet} text="verify — the acceptance test, written before any code exists" delay={115} />
        </FadeUp>
        <FadeUp delay={160} style={{marginTop: 44, maxWidth: 1200}}>
          <Big size={44}>
            An implementation is only <span style={{color: C.cyan}}>accepted</span> if these clauses pass.
            The AI writes the body — <span style={{color: C.violet}}>the goal doesn't move.</span>
          </Big>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
