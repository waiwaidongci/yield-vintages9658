import {esc,fmt} from '../utils/format.js';import {table} from './common/table.js';import {status} from './common/status.js';
function levelTable(title,rows,collapsed){
 if(!rows||!rows.length)return '';
 const keys=Object.keys(rows[0]);
 return `<details ${collapsed?'':'open'}><summary>${esc(title)}（${rows.length}${title.includes('批')?' 条':' 组'}）</summary><div class="table-wrap"><table><thead><tr>${keys.map(k=>`<th>${esc(k)}</th>`).join('')}</tr></thead><tbody>${
  rows.map(x=>`<tr>${keys.map(k=>`<td>${fmt(x[k])}</td>`).join('')}</tr>`).join('')
 }</tbody></table></div></details>`;
}
export function report(run){
 if(!run)return '<p class="empty">选择一个报告查看快照与结果。</p>';
 const isCustom=run.result?.kind==='custom';
 const failNote=run.status==='failed'?`<div class="pe-fail"><b>核算未发布：${esc(run.error||'未知原因')}</b><p class="pe-hint">整套三级结果不会部分发布；可修正口径后重新排队，重试不会重复发布已有报告。${run.error?.includes('超时')?'复杂公式超过20秒已被拒绝并释放资源，同队列普通核算照常推进。':''}</p></div>`:'';
 return `<section class="report"><div class="report-top"><h2>${esc(run.name)}</h2>${status(run.status)}</div><p>口径：${esc(run.snapshot.policy.version)}${isCustom?'（三级自定义）':''} · 来源 ${run.snapshot.sources.length} 行 · ${run.approved?'负责人已复核':'待复核'}</p><p class="checksum">SHA256 ${esc(run.checksum)}</p>${run.error&&run.status!=='completed'?failNote:''}${run.result?`<div class="metrics">${Object.entries(run.result.summary).map(([k,v])=>`<div><small>${esc(k)}</small><strong>${fmt(v)}</strong></div>`).join('')}</div><p class="method">${esc(run.result.method)}</p>${run.result.warnings?.length?'<p class="warning">'+run.result.warnings.map(esc).join('；')+'</p>':''}${isCustom?`${levelTable('全厂层结果',run.result.plant_rows)}${levelTable('线内层结果',run.result.line_rows)}${levelTable('逐批层结果（前20行）',(run.result.lot_rows||[]).slice(0,20),true)}`:table(run.result.rows)}${run.result.trace?'<details><summary>逐笔分摊追溯</summary>'+table(run.result.trace)+'</details>':''}`:''}<details><summary>冻结来源与口径快照</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px">${esc(JSON.stringify(run.snapshot,null,2))}</pre></details><p>${esc(run.review||'尚未填写复核说明')}</p></section>`}
