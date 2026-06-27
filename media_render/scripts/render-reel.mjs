#!/usr/bin/env node
/** CLI helper — invoked by apps/media/remotion_bridge.py */
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'fs';
import path from 'path';

const propsPath = process.argv.find((a) => a.startsWith('--props='))?.slice(8)
  || process.argv[process.argv.indexOf('--props') + 1];
const outPath = process.argv[2] || 'out/reel.mp4';

async function main() {
  const props = propsPath && fs.existsSync(propsPath)
    ? JSON.parse(fs.readFileSync(propsPath, 'utf8'))
    : {};
  const entry = path.join(process.cwd(), 'src', 'index.ts');
  const bundled = await bundle(entry);
  const composition = await selectComposition({
    serveUrl: bundled,
    id: 'ProductReel',
    inputProps: props,
  });
  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: 'h264',
    outputLocation: outPath,
    inputProps: props,
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
