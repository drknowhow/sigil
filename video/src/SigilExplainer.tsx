import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame} from 'remotion';
import {C} from './theme';
import {Title} from './scenes/Title';
import {Problem} from './scenes/Problem';
import {Lift} from './scenes/Lift';
import {Goal} from './scenes/Goal';
import {Budget} from './scenes/Budget';
import {Loop} from './scenes/Loop';
import {Results} from './scenes/Results';
import {Outro} from './scenes/Outro';

// scene timing (frames @ 30fps) — total 2250 = 75s
const SCENES: Array<[React.FC, number]> = [
  [Title, 150],
  [Problem, 270],
  [Lift, 330],
  [Goal, 270],
  [Budget, 240],
  [Loop, 420],
  [Results, 300],
  [Outro, 270],
];

const FADE = 14;

const Scene: React.FC<{children: React.ReactNode; dur: number}> = ({children, dur}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, FADE, dur - FADE, dur],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

export const SigilExplainer: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {SCENES.map(([Comp, dur], i) => {
        const from = at;
        at += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <Scene dur={dur}>
              <Comp />
            </Scene>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const TOTAL_FRAMES = SCENES.reduce((a, [, d]) => a + d, 0);
