// Build-time only: use the runtime's exact JSON/profile overlay semantics.
import {readFileSync, writeFileSync} from 'node:fs';
import {profileOverlay} from '../common/community-compose.mjs';
const [base, overlay, output] = process.argv.slice(2);
if (!base || !overlay || !output) throw Error('Expected base, overlay and output paths');
writeFileSync(output, profileOverlay(readFileSync(base), JSON.parse(readFileSync(overlay, 'utf8').replace(/^\uFEFF/, ''))));
