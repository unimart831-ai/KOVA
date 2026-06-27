import {Composition} from 'remotion';
import {ProductReel} from './ProductReel';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProductReel"
        component={ProductReel}
        durationInFrames={420}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          imageUrls: [],
          hookTexts: [],
          slideRoles: [],
          slideDurations: [],
          transitions: [],
          musicMood: 'upbeat',
        }}
      />
    </>
  );
};
