import fs from 'node:fs';

const required = [
  'app/page.tsx',
  'components/Dashboard.tsx',
  'proof/million_cv_scan/README.md',
  'public/docs/proof/million_cv_scan/sample_report.md',
];

let ok = true;
for (const file of required) {
  if (!fs.existsSync(file)) {
    console.error(`missing: ${file}`);
    ok = false;
  }
}
const dashboard = fs.readFileSync('components/Dashboard.tsx', 'utf8');
for (const phrase of ['Executive Dashboard', 'Import Center', 'Trust Center', 'Million-CV Proof Report']) {
  if (!dashboard.includes(phrase)) {
    console.error(`dashboard missing phrase: ${phrase}`);
    ok = false;
  }
}
if (!ok) process.exit(1);
console.log('agent-browser verify passed: dashboard shell and proof docs are present.');
