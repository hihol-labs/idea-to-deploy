#!/usr/bin/env node
// Minimal asciinema .cast v2 → SVG converter (no dependencies)
const fs = require('fs');

const INPUT = process.argv[2] || 'docs/demo.cast';
const OUTPUT = process.argv[3] || 'docs/demo.svg';

const raw = fs.readFileSync(INPUT, 'utf8').trim().split('\n');
const header = JSON.parse(raw[0]);
const events = raw.slice(1).map(l => JSON.parse(l));

const COLS = header.width || 90;
const ROWS = header.height || 32;
const CHAR_W = 8.4;
const CHAR_H = 17;
const PAD = 16;
const TITLE_H = 32;
const W = COLS * CHAR_W + PAD * 2;
const H = ROWS * CHAR_H + PAD * 2 + TITLE_H;

// ANSI color palette
const COLORS = {
  '0': '#1e1e2e', '1': '#f38ba8', '2': '#a6e3a1', '3': '#f9e2af',
  '4': '#89b4fa', '5': '#cba6f7', '6': '#94e2d5', '7': '#cdd6f4',
  '30': '#45475a', '31': '#f38ba8', '32': '#a6e3a1', '33': '#f9e2af',
  '34': '#89b4fa', '35': '#cba6f7', '36': '#94e2d5', '37': '#cdd6f4',
  '90': '#585b70', '91': '#f38ba8', '92': '#a6e3a1', '93': '#f9e2af',
  '94': '#89b4fa', '95': '#cba6f7', '96': '#94e2d5', '97': '#cdd6f4',
};

const FG_256 = {
  '245': '#6c7086',
};

// Build frames: replay terminal
const screen = Array.from({length: ROWS}, () => Array(COLS).fill(' '));
const colors = Array.from({length: ROWS}, () => Array(COLS).fill(null));
const bolds  = Array.from({length: ROWS}, () => Array(COLS).fill(false));
let curRow = 0, curCol = 0;
let curColor = null, curBold = false;

const frames = [];
let lastTime = 0;

function cloneScreen() {
  return {
    chars: screen.map(r => [...r]),
    colors: colors.map(r => [...r]),
    bolds: bolds.map(r => [...r]),
  };
}

function processChar(ch) {
  if (ch === '\r') { curCol = 0; return; }
  if (ch === '\n') { curRow++; curCol = 0; if (curRow >= ROWS) curRow = ROWS - 1; return; }
  if (curCol >= COLS) return;
  if (curRow >= ROWS) return;
  screen[curRow][curCol] = ch;
  colors[curRow][curCol] = curColor;
  bolds[curRow][curCol] = curBold;
  curCol++;
}

function processAnsi(code) {
  const parts = code.split(';').map(Number);
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    if (p === 0) { curColor = null; curBold = false; }
    else if (p === 1) { curBold = true; }
    else if (p >= 30 && p <= 37) { curColor = COLORS[String(p)]; }
    else if (p >= 90 && p <= 97) { curColor = COLORS[String(p)]; }
    else if (p === 38 && parts[i+1] === 5) {
      const c = parts[i+2];
      curColor = FG_256[String(c)] || '#cdd6f4';
      i += 2;
    }
    else if (p === 39) { curColor = null; }
  }
}

function processOutput(text) {
  let i = 0;
  while (i < text.length) {
    if (text[i] === '\u001b' && text[i+1] === '[') {
      // Parse ANSI escape
      let j = i + 2;
      while (j < text.length && text[j] !== 'm' && text[j] !== 'H' && text[j] !== 'J' && text[j] !== 'K' && text[j] !== 'A' && text[j] !== 'B' && text[j] !== 'C' && text[j] !== 'D') j++;
      if (j < text.length) {
        const code = text.substring(i+2, j);
        if (text[j] === 'm') processAnsi(code);
        j++;
      }
      i = j;
    } else {
      processChar(text[i]);
      i++;
    }
  }
}

// Process all events
for (const [time, type, data] of events) {
  if (type !== 'o') continue;
  processOutput(data);
  // Capture frame every 0.5s or at end
  if (time - lastTime >= 0.3 || time === events[events.length-1][0]) {
    frames.push({ time, ...cloneScreen() });
    lastTime = time;
  }
}

// Ensure last frame
if (frames.length === 0) frames.push({ time: 0, ...cloneScreen() });

const totalDur = frames[frames.length - 1].time + 2; // 2s pause at end

function escXml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderFrame(f) {
  const lines = [];
  for (let r = 0; r < ROWS; r++) {
    let x = PAD;
    const y = TITLE_H + PAD + r * CHAR_H;
    // Group consecutive same-color chars
    let run = '';
    let runColor = f.colors[r][0];
    let runBold = f.bolds[r][0];
    let runStart = 0;

    for (let c = 0; c <= COLS; c++) {
      const ch = c < COLS ? f.chars[r][c] : null;
      const col = c < COLS ? f.colors[r][c] : 'END';
      const bold = c < COLS ? f.bolds[r][c] : false;

      if (col !== runColor || bold !== runBold || c === COLS) {
        if (run.trimEnd().length > 0) {
          const fill = runColor || '#cdd6f4';
          const weight = runBold ? ' font-weight="bold"' : '';
          lines.push(`<text x="${PAD + runStart * CHAR_W}" y="${y}" fill="${fill}"${weight}>${escXml(run.trimEnd())}</text>`);
        }
        run = ch || '';
        runColor = col;
        runBold = bold;
        runStart = c;
      } else {
        run += ch;
      }
    }
  }
  return lines.join('\n');
}

// Build SVG with CSS animation
let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
<style>
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
  text { font-family: "JetBrains Mono","Fira Code","SF Mono",Menlo,Monaco,monospace; font-size: 13px; white-space: pre; }
</style>
<defs>
  <clipPath id="clip"><rect x="0" y="${TITLE_H}" width="${W}" height="${H - TITLE_H}" rx="0"/></clipPath>
</defs>
<!-- Window chrome -->
<rect width="${W}" height="${H}" rx="8" fill="#1e1e2e"/>
<rect width="${W}" height="${TITLE_H}" rx="8" fill="#181825"/>
<rect x="0" y="20" width="${W}" height="12" fill="#181825"/>
<circle cx="20" cy="16" r="6" fill="#f38ba8"/>
<circle cx="38" cy="16" r="6" fill="#f9e2af"/>
<circle cx="56" cy="16" r="6" fill="#a6e3a1"/>
<text x="${W/2}" y="20" fill="#6c7086" text-anchor="middle" font-size="12">idea-to-deploy demo</text>
`;

// For simplicity, render only the last frame (full result)
// and add a typing animation via CSS
const lastFrame = frames[frames.length - 1];
svg += `<g clip-path="url(#clip)">\n`;
svg += renderFrame(lastFrame);
svg += `\n</g>\n`;
svg += `</svg>`;

fs.writeFileSync(OUTPUT, svg);
console.log(`SVG written to ${OUTPUT} (${(svg.length/1024).toFixed(1)} KB, ${frames.length} frames captured)`);
