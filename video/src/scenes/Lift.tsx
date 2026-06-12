import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, MONO} from '../theme';
import {Backdrop, Big, Dim, FadeUp, Label, Term} from '../ui';

const SHEET: Array<[string, string, string, string]> = [
  ['#705b', 'get_config(key, default)', '!env', C.amber],
  ['#d939', 'read_cache(name, ttl)', '!clock !fs', C.amber],
  ['#d4b8', 'fetch_user(user_id)', '!clock !fs !net', C.amber],
  ['#9b4e', 'order_totals(orders)', 'pure?', C.cyan],
  ['#f574', 'jitter_sleep(attempt)', '!clock !rand', C.amber],
  ['#e70b', 'dispatch(event)', '!unsafe?', C.red],
];

export const Lift: React.FC = () => {
  const frame = useCurrentFrame();
  const tokens = interpolate(frame, [210, 280], [52464, 8907], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{padding: 100, justifyContent: 'center'}}>
      <Backdrop />
      <div style={{zIndex: 1}}>
        <FadeUp><Label>step 1 · lift what you already have</Label></FadeUp>
        <FadeUp delay={8} style={{marginTop: 14, marginBottom: 40}}>
          <Big>Any Python repo → a one-page digest sheet</Big>
        </FadeUp>
        <div style={{display: 'flex', gap: 50, alignItems: 'stretch'}}>
          <FadeUp delay={20} style={{flex: 1}}>
            <Term title="your_repo/webapp.py — 767 tokens">
              <div style={{color: C.comment, fontSize: 21, lineHeight: 1.6}}>
                {'def fetch_user(user_id):\n    cached = read_cache(f"user-{user_id}")\n    if cached is not None:\n        return cached\n    r = requests.get(f"{API}/users/…")\n    r.raise_for_status()\n    write_cache(…)\n    return r.json()\n\n# …14 more functions…'}
              </div>
            </Term>
          </FadeUp>
          <div style={{display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
            <FadeUp delay={45}>
              <div style={{fontFamily: MONO, fontSize: 26, color: C.cyan, whiteSpace: 'nowrap'}}>
                sigil lift ⟶
              </div>
              <div style={{fontFamily: MONO, fontSize: 17, color: C.comment, textAlign: 'center'}}>
                parse only,<br />never executes
              </div>
            </FadeUp>
          </div>
          <FadeUp delay={50} style={{flex: 1.25}}>
            <Term title="digest sheet — one line per definition">
              {SHEET.map(([h, sig, fx, color], i) => {
                const on = frame >= 70 + i * 16;
                return (
                  <div key={h} style={{opacity: on ? 1 : 0.06, transition: 'none', fontSize: 22.5}}>
                    <span style={{color: C.violet}}>{h}</span>{' '}
                    <span style={{color: C.txt}}>{sig}</span>{' '}
                    <span style={{color}}>{fx}</span>
                  </div>
                );
              })}
              <div style={{color: C.comment, fontSize: 19, marginTop: 10, opacity: frame > 175 ? 1 : 0}}>
                ; '?' marks static guesses — over-approximate, never silent
              </div>
            </Term>
          </FadeUp>
        </div>
        <FadeUp delay={200} style={{marginTop: 44, display: 'flex', alignItems: 'baseline', gap: 24}}>
          <span style={{fontFamily: MONO, fontSize: 52, color: C.cyan, fontWeight: 700}}>
            {Math.round(tokens).toLocaleString('en-US')} tok
          </span>
          <Dim size={30}>
            measured on requests 2.34.2 — <span style={{color: C.txt}}>5.9× smaller</span>, hashes instead of bodies
          </Dim>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
