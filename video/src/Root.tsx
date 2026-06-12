import React from 'react';
import {Composition} from 'remotion';
import {SigilExplainer, TOTAL_FRAMES} from './SigilExplainer';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="SigilExplainer"
    component={SigilExplainer}
    durationInFrames={TOTAL_FRAMES}
    fps={30}
    width={1920}
    height={1080}
  />
);
