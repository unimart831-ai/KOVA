import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export type ProductReelProps = {
  imageUrls: string[];
  hookTexts: string[];
  slideRoles: string[];
  slideDurations: number[];
  transitions: string[];
  musicMood: string;
};

const BRAND = {
  primary: '#1E3A8A',
  secondary: '#10B981',
  accent: '#F59E0B',
};

const HookCard: React.FC<{text: string}> = ({text}) => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(165deg, ${BRAND.primary} 0%, ${BRAND.secondary} 100%)`,
      justifyContent: 'center',
      alignItems: 'center',
      padding: 64,
    }}
  >
    <div
      style={{
        color: 'white',
        fontSize: 72,
        fontWeight: 800,
        textAlign: 'center',
        lineHeight: 1.15,
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      {text}
    </div>
    <div
      style={{
        marginTop: 32,
        width: 120,
        height: 6,
        borderRadius: 3,
        background: BRAND.accent,
      }}
    />
  </AbsoluteFill>
);

const CtaCard: React.FC<{text: string}> = ({text}) => {
  const lines = text.split('\n').filter(Boolean);
  const price = lines[0] || '';
  const cta = lines[1] || lines[0] || 'Shop on WhatsApp';
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, #080c18 0%, ${BRAND.primary} 100%)`,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 48,
      }}
    >
      <div
        style={{
          background: 'white',
          borderRadius: 28,
          padding: '48px 56px',
          width: '84%',
          boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
        }}
      >
        {price && price !== cta ? (
          <div style={{fontSize: 56, fontWeight: 800, color: BRAND.primary, marginBottom: 24}}>
            {price}
          </div>
        ) : null}
        <div
          style={{
            background: BRAND.secondary,
            color: 'white',
            fontSize: 36,
            fontWeight: 700,
            padding: '20px 32px',
            borderRadius: 14,
            textAlign: 'center',
          }}
        >
          {cta}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const ProductReel: React.FC<ProductReelProps> = ({
  imageUrls,
  hookTexts,
  slideRoles,
  slideDurations,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const urls = imageUrls.length ? imageUrls : [''];
  const roles = slideRoles.length ? slideRoles : urls.map(() => 'hero');
  const texts = hookTexts.length ? hookTexts : urls.map(() => '');
  const durs =
    slideDurations.length >= urls.length
      ? slideDurations
      : urls.map(() => 3.5);

  let elapsed = 0;
  let active = 0;
  for (let i = 0; i < durs.length; i++) {
    const slideFrames = Math.max(1, Math.round(durs[i] * fps));
    if (frame < elapsed + slideFrames) {
      active = i;
      break;
    }
    elapsed += slideFrames;
    active = i;
  }

  const role = roles[active] || 'hero';
  const text = texts[active] || '';
  const localFrame = frame - elapsed;
  const slideFrames = Math.max(1, Math.round((durs[active] || 3.5) * fps));
  const scale = interpolate(localFrame, [0, slideFrames], [1.04, 1.0], {
    extrapolateRight: 'clamp',
  });

  if (role === 'hook' && text.trim()) {
    return <HookCard text={text.split('\n')[0]} />;
  }
  if (role === 'cta' && text.trim()) {
    return <CtaCard text={text} />;
  }

  const src = urls[active];
  return (
    <AbsoluteFill style={{backgroundColor: '#0c1222'}}>
      <Img
        src={src}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
