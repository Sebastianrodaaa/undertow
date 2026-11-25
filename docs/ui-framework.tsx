/* Partial verbatim recovery from DEV team room transcript (2026-11-25 18:23 Europe/Paris).
 * The pasted message exceeded transcript display limits, so two middle sections (responsive media
 * queries at <=767px / <=520px + `.card` base rule, and the rest of `CSS` / `markup` / `mount`)
 * are marked as truncated below. Every other line is verbatim as recovered.
 */
"use client";
// @ts-nocheck
/* The charts are drawn with plain DOM + SVG inside an effect, so this file
   is checked as JavaScript. No dependencies. */

import * as React from "react";

/* ------------------------------------------------------------------ */
/*  Finance Bento: a pro personal-finance dashboard for fiat, stocks  */
/*  and crypto. Net-worth stream, allocation gauge, KPI tiles, cash   */
/*  flow, crypto candles and weekly stocks. Responsive, dark.         */
/* ------------------------------------------------------------------ */

export interface FinanceBentoData {
  /** Month-end balances by asset class, oldest first (24+ months for "All"). */
  history: { date: string; fiat: number; stocks: number; crypto: number }[];
  payments: { name: string; date: string; amount: number }[];
  goals: { name: string; progress: number; target: number }[];
  /** Six months of income and spending, in thousands; first row is the latest year. */
  cashflow: { months: string[]; income: number[][]; spending: number[][] };
  /** Each asset: share of the crypto pot, 24h change and 7 daily candles [open, high, low, close]. */
  crypto: { name: string; symbol: string; share: number; change: string; ohlc: number[][] }[];
  /** Weekly trading volume, in thousands. */
  stocks: { days: string[]; values: number[] };
}

export interface FinanceBentoProps {
  data: FinanceBentoData;
  title?: string;
  subtitle?: string;
  avatar?: string;
  avatarAlt?: string;
  /** The "by vasnev.art" badge under the grid. */
  credit?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const CSS = `.fpb{font-family:Geist,ui-sans-serif,system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased;color:#fff;width:100%}
.fpb *{box-sizing:border-box}
.fpb .fpb-c{border-radius:28px}
.fpb .vbrow{display:flex;justify-content:flex-end;margin-top:16px}
.fpb{--acc:#E8FF1F;--t1:#fff;--t2:rgba(255,255,255,.56);--t3:rgba(255,255,255,.38);--hair:rgba(255,255,255,.14);--ease:cubic-bezier(.32,.72,0,1);
    --fiat:#FFFFFF;--stocks:#A9B2FF;--crypto:#FFB37A}
.fpb *{box-sizing:border-box}
.fpb .fpb-c{position:relative;padding:20px 22px 22px;background:#000;color:#fff}
.fpb .top{display:flex;align-items:center;gap:14px;height:44px;margin-bottom:16px}
.fpb .top h1{margin:0;font-size:28px;font-weight:700;letter-spacing:-.03em;flex:1}
.fpb .top h1 span{font-weight:500;color:var(--t3);font-size:15px;letter-spacing:-.01em;margin-left:12px}
.fpb .seg{display:flex;padding:3px;gap:2px;border-radius:14px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12)}
.fpb .seg button{border:0;height:28px;min-width:44px;padding:0 12px;border-radius:11px;background:transparent;color:var(--t2);font:600 12.5px Geist,sans-serif;cursor:pointer;transition:background .25s,color .25s}
.fpb .seg button[aria-pressed="true"]{background:#fff;color:#0b0b0c}
.fpb .seg button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.fpb .ctrls{display:flex;gap:10px}
.fpb .ava{width:40px;height:40px;border-radius:50%;object-fit:cover;box-shadow:0 0 0 2px rgba(255,255,255,.18);flex:0 0 auto}
.fpb .grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}
.fpb .h1{height:376px}
.fpb .h2{height:168px}
.fpb .h3{height:330px}
.fpb #nw{grid-column:span 8}
.fpb #alloc{grid-column:span 4}
.fpb .kpi{grid-column:span 3}
.fpb #flow{grid-column:span 5}
.fpb #crypto{grid-column:span 4}
.fpb #stocks{grid-column:span 3}
@media (max-width:1199px){.fpb #nw{grid-column:span 12}
.fpb #alloc{grid-column:span 6;grid-row:span 2;height:auto}
.fpb .kpi{grid-column:span 6}
.fpb #flow{grid-column:span 12}
.fpb #crypto,.fpb #stocks{grid-column:span 6}}
@media (m
/* ... [TRUNCATED IN TRANSCRIPT: ~698 chars omitted between @media (m and city:0;...] */
city:0;transform:translateY(14px) scale(.985);transition:opacity .7s ease,transform .9s var(--ease)}
.fpb .in .card{opacity:1;transform:none}
.fpb .card .rim{position:absolute;inset:0;border-radius:inherit;box-shadow:inset 0 1px 0 rgba(255,255,255,.2),inset 0 0 0 1px rgba(255,255,255,.06);pointer-events:none;z-index:9}
.fpb .g{position:absolute;inset:0}
.fpb .core{position:absolute;left:10%;right:10%;top:16%;bottom:-6%;border-radius:90px;filter:blur(60px)}
.fpb .glass{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(20px)}
.fpb .glass .rim{display:none}
.fpb .solid{background:var(--acc);color:#0b0b0c}
.fpb .solid .rim{box-shadow:inset 0 1px 0 rgba(255,255,255,.5)}
.fpb .in-c{position:absolute;inset:0;padding:22px 24px;z-index:2}
.fpb .ttl{font-size:18px;font-weight:600;letter-spacing:-.02em;display:flex;align-items:center;gap:8px}
.fpb .cap{font-size:11.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--t2)}
.fpb .solid .cap{color:rgba(0,0,0,.55)}
.fpb .big{font-size:40px;font-weight:200;letter-spacing:-.04em;line-height:1;font-variant-numeric:tabular-nums}
.fpb .delta{font:600 12.5px "Geist Mono",monospace;color:var(--acc);letter-spacing:-.02em}
.fpb .muted{font-size:12.5px;color:var(--t3);font-weight:500;letter-spacing:-.01em}
.fpb .chip{display:inline-flex;align-items:center;height:22px;padding:0 9px;border-radius:11px;background:rgba(0,0,0,.85);color:#fff;font:600 11px "Geist Mono",monospace;letter-spacing:-.02em}
.fpb .legend{display:flex;gap:16px;font-size:12px;font-weight:500;color:var(--t2)}
.fpb .legend span{display:inline-flex;align-items:center;gap:6px}
.fpb .legend i{width:8px;height:8px;border-radius:50%}
.fpb .row{display:flex;align-items:center;gap:12px}
.fpb .mono{font-family:"Geist Mono",monospace;font-variant-numeric:tabular-nums}
.fpb .dots circle{transition:opacity .26s,transform .26s;transform-box:fill-box;transform-origin:center}
.fpb .tip{position:fixed;z-index:50;pointer-events:none;background:rgba(14,14,16,.92);color:#fff;border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:9px 11px;font-size:12px;
    backdrop-filter:blur(16px);box-shadow:0 12px 30px -10px rgba(0,0,0,.6);opacity:0;transform:translateY(4px);transition:opacity .15s,transform .15s;white-space:nowrap;min-width:150px}
.fpb .tip.on{opacity:1;transform:none}
.fpb .tip .t{color:var(--t2);margin-bottom:5px;font-weight:500}
.fpb .tip .r{display:flex;justify-content:space-between;gap:14px;align-items:center;line-height:19px}
.fpb .tip .r span{display:inline-flex;align-items:center;gap:6px;color:var(--t2)}
.fpb .tip i{width:7px;height:7px;border-radius:50%}
.fpb .tip b{font:500 12px "Geist Mono",monospace}
.fpb .vb-badge{--vb-on:#6a5cff;display:inline-flex;align-items:center;gap:9px;height:34px;padding:0 12px 0 11px;border-radius:17px;background:#111113;border:1px solid rgba(255,255,255,.1);color:#fff;text-decoration:none;font:500 13px/1 Geist,sans-serif;letter-spacing:-.02em;box-shadow:0 8px 24px -14px rgba(0,0,0,.25);transition:border-color .25s}
.fpb .vb-badge:hover{border-color:color-mix(in oklab,var(--vb-on) 45%,transparent)}
.fpb .vb-mark{display:grid;grid-template-columns:repeat(5,3px);grid-template-rows:repeat(3,3px);gap:2px}
.fpb .vb-mark i{width:3px;height:3px;border-radius:50%;background:rgba(255,255,255,.16);transition:background .3s}
.fpb .vb-mark i.on{background:var(--vb-on)}
.fpb .vb-badge:h
/* ... [TRUNCATED IN TRANSCRIPT: rest of CSS, markup(), and start of mount() omitted] */
.innerHTML=items.map(k=>`<button type="button" aria-pressed="${S[key]===k}">${k}</button>`).join('');
  host.querySelectorAll('button').forEach(b=>b.onclick=()=>{S[key]=b.textContent;host.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));updateAll()})}
seg($id('period'),['1M','3M','1Y','All'],'period');
seg($id('ccy'),['USD','EUR'],'ccy');
function updateAll(){updateNW();updateAlloc();updateRet();updateCash();updatePay();updateGoals();updateFlow();updateCrypto();updateStocks()}

let rz;const ro=new ResizeObserver(()=>{clearTimeout(rz);rz=setTimeout(()=>{if(!nwData)return;cancelAnimationFrame(nwRaf);nwGrow=1;drawNW();updateFlow(true);updateStocks(true);updateCash();updateGoals()},120)});
['nw','flow','stocks','cash'].forEach(id=>ro.observe($id(id)));
const vbm=$id('vbm');const ON=new Set(['0,0','4,0','1,1','3,1','2,2']);
if(vbm)for(let i=0;i<15;i++){const x=i%5,y=Math.floor(i/5),e=document.createElement('i');if(ON.has(x+','+y))e.className='on';e.style.setProperty('--x',x);vbm.appendChild(e)}
(document.fonts?document.fonts.ready:Promise.resolve()).then(()=>{if(!alive)return;$id('grid').classList.add('in');
  root.querySelectorAll('.card').forEach((c,i)=>c.style.transitionDelay=(i*60)+'ms');updateAll()});

  return () => { alive = false; frames.forEach((f) => cancelAnimationFrame(f)); ro.disconnect(); clearTimeout(rz); };
}

export function FinanceBento({ data, title = "Overview", subtitle = "", avatar, avatarAlt = "Profile", credit = true, className = "", style }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.innerHTML = markup({ title, subtitle, avatar, avatarAlt, credit });
    const stop = mount(el, data);
    return () => { stop(); el.innerHTML = ""; };
  }, [data, title, subtitle, avatar, avatarAlt, credit]);
  return (
    <>
      <style>{CSS}</style>
      <div ref={ref} className={`fpb ${className}`} style={style} />
    </>
  );
}

export default FinanceBento;
