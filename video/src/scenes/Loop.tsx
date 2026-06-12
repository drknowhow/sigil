import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, MONO, SANS} from '../theme';
import {Backdrop, Big, FadeUp, Label, Term, Type} from '../ui';

const STEPS = [
  ['sheet()', 'read digests, not files', 20],
  ['expand(#6e01)', 'only the code you will change', 95],
  ['patch(…)', 'edit ops, not rewritten files', 170],
  ['verify ✓', 'auto-checked before "done"', 280],
] as const;

export const Loop: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{padding: 100, justifyContent: 'center'}}>
      <Backdrop />
      <div style={{zIndex: 1}}>
        <FadeUp><Label>step 4 · how an agent works on it (MCP harness)</Label></FadeUp>
        <FadeUp delay={8} style={{marginTop: 14, marginBottom: 34}}>
          <Big>sheet → expand → patch → verify</Big>
        </FadeUp>

        <div style={{display: 'flex', gap: 18, marginBottom: 38}}>
          {STEPS.map(([name, desc, at], i) => {
            const on = spring({frame: frame - at, fps, config: {damping: 16}});
            const active = frame >= at;
            return (
              <React.Fragment key={name}>
                <div
                  style={{
                    flex: 1,
                    background: active ? 'rgba(94,234,212,0.08)' : C.panel,
                    border: `2px solid ${active ? C.cyan : C.line}`,
                    borderRadius: 18,
                    padding: '22px 26px',
                    transform: `scale(${0.92 + on * 0.08})`,
                  }}
                >
                  <div style={{fontFamily: MONO, fontSize: 27, color: active ? C.cyan : C.dim, fontWeight: 700}}>
                    {name}
                  </div>
                  <div style={{fontFamily: SANS, fontSize: 20, color: C.dim, marginTop: 6}}>{desc}</div>
                </div>
                {i < 3 && (
                  <div style={{alignSelf: 'center', fontFamily: MONO, fontSize: 30, color: frame >= STEPS[i + 1][2] ? C.cyan : C.comment}}>
                    →
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        <FadeUp delay={40} style={{width: 1560}}>
          <Term title="agent session — seeded bug, fixed via one patch, zero file reads">
            <div style={{fontSize: 23, lineHeight: 1.8}}>
              <div style={{opacity: frame > 50 ? 1 : 0}}>
                <span style={{color: C.comment}}>verify:</span>{' '}
                <span style={{color: C.red}}>fail</span> — out == n * 3 with{' '}
                <span style={{color: C.txt}}>out=8, n=4</span>
              </div>
              <div style={{opacity: frame > 110 ? 1 : 0}}>
                <span style={{color: C.comment}}>expand #6e01:</span>{' '}
                fn triple(n Int) {'{'} ret n * <span style={{color: C.red}}>2</span> {'}'}
              </div>
              <div style={{opacity: frame > 180 ? 1 : 0, minHeight: 42}}>
                {frame > 180 && (
                  <Type
                    text='patch #6e01 { body.stmts.0.value.right.val := "3" }   -- 18 tokens of output'
                    start={182}
                    cps={1.4}
                    style={{fontSize: 23, color: C.violet}}
                  />
                )}
              </div>
              <div style={{opacity: frame > 285 ? 1 : 0}}>
                ⇒ <span style={{color: C.violet}}>#a4c2</span> · verify:{' '}
                <span style={{color: C.cyan, fontWeight: 700}}>pass</span> · goal triple:{' '}
                <span style={{color: C.cyan, fontWeight: 700}}>verified</span>
              </div>
            </div>
          </Term>
        </FadeUp>

        <FadeUp delay={320} style={{marginTop: 34, display: 'flex', gap: 22}}>
          {[
            ['R1', 'context only grows — cache stays hot'],
            ['R2', 'expand beats regenerating from memory'],
            ['R3', 'failures come back as patch targets, never "try again"'],
          ].map(([r, d]) => (
            <div key={r} style={{display: 'flex', gap: 12, alignItems: 'baseline'}}>
              <span style={{fontFamily: MONO, color: C.violet, fontSize: 25, fontWeight: 700}}>{r}</span>
              <span style={{fontFamily: SANS, color: C.dim, fontSize: 21}}>{d}</span>
            </div>
          ))}
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
