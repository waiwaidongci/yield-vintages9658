import {esc} from '../utils/format.js';

// 三级自定义口径编辑器：逐批/线内/全厂，命名中间量 + 公式 + 件数/比例类型
export const LEVELS=[
 {key:'lot',label:'逐批层',hint:'仅可引用底稿字段（投入/一次通过/返工合格/报废）与本层中间量；不可使用 SUM'},
 {key:'line',label:'线内层',hint:'按 日期×试制线 分组；仅可 SUM 逐批层中间量，或引用本层已聚合量'},
 {key:'plant',label:'全厂层',hint:'按 日期 分组；仅可 SUM 线内层中间量；至少产出一个比例(良率)'},
];
export const FIELD_HINTS=[
 ['input','投入数(件)'],['first_pass','一次通过数(件)'],
 ['reworked_good','返工合格数(件)'],['scrap','报废数(件)'],
];

const blankRow=()=>({name:'',expr:'',type:'count'});

export function defaultCustomPolicy(seedVersion){
 return {
  version:seedVersion+'-自定义',
  kind:'custom',
  description:'逐批命名中间量，线内/全厂以 SUM 低层聚合后求良率；零分母用 IF 兜底。',
  levels:{
   lot:[
    {name:'一次通过',expr:'first_pass',type:'count'},
    {name:'总合格',expr:'first_pass + reworked_good',type:'count'},
    {name:'净投入',expr:'input - scrap',type:'count'},
    {name:'批一次通过率',expr:'IF(input > 0, first_pass / input, 0)',type:'ratio'},
   ],
   line:[
    {name:'线一次通过',expr:'SUM(一次通过)',type:'count'},
    {name:'线总合格',expr:'SUM(总合格)',type:'count'},
    {name:'线净投入',expr:'SUM(净投入)',type:'count'},
    {name:'线一次通过良率',expr:'IF(SUM(线净投入) > 0, SUM(线一次通过) / SUM(线净投入), 0)',type:'ratio'},
   ],
   plant:[
    {name:'厂一次通过',expr:'SUM(线一次通过)',type:'count'},
    {name:'厂总合格',expr:'SUM(线总合格)',type:'count'},
    {name:'厂净投入',expr:'SUM(线净投入)',type:'count'},
    {name:'全厂一次通过良率',expr:'IF(SUM(厂净投入) > 0, SUM(厂一次通过) / SUM(厂净投入), 0)',type:'ratio'},
   ],
  },
 };
}

export function policyEditor(policy,periods,selectedPeriod){
 const p=policy||defaultCustomPolicy('');
 const periodOpts=['全部',...periods.map(x=>x.name)];
 return `<section class="policy-editor">
 <div class="form-grid">
  <label>口径版本名<input id="pe-version" value="${esc(p.version)}" required minlength="2" maxlength="120"></label>
  <label>口径说明<input id="pe-desc" value="${esc(p.description)}" required></label>
  <label>试算期间<select id="pe-period">${periodOpts.map(x=>`<option ${x===selectedPeriod?'selected':''}>${esc(x)}</option>`).join('')}</select></label>
 </div>
 <p class="method">可用底稿字段：${FIELD_HINTS.map(([k,v])=>`<code>${esc(k)}</code>${esc(v)}`).join('　')}。运算支持 + − × ÷ 与括号、<code>IF(条件, 成立, 不成立)</code>、<code>SUM(下层量)</code>、比较 &gt; &gt;= &lt; &lt;= = &lt;&gt;。件数(count)与比例(ratio)不可相加；未选中的 IF 分支不计算。</p>
 <div class="level-grid">
 ${LEVELS.map(l=>levelBlock(l,p.levels?.[l.key]||[blankRow()])).join('')}
 </div>
 <div class="pe-actions">
  <button type="button" id="pe-trial" class="pe-btn-trial">试算（不落库）</button>
  <button type="submit" id="pe-save">校验通过后登记口径</button>
 </div>
 <div id="pe-trial-out" class="pe-trial-out" aria-live="polite"></div>
 </section>`;
}

function levelBlock(level,rows){
 return `<fieldset class="level-block" data-level="${level.key}">
  <legend><b>${esc(level.label)}</b><span>${esc(level.hint)}</span></legend>
  <div class="pe-rows">
   ${rows.map((r,i)=>rowHtml(level.key,r,i)).join('')}
  </div>
  <button type="button" class="pe-add" data-level="${level.key}">＋ 添加中间量</button>
 </fieldset>`;
}

function rowHtml(level,r,idx){
 return `<div class="pe-row" data-level="${level}">
  <input class="pe-name" placeholder="中间量名（中文/字母数字）" value="${esc(r.name)}" maxlength="40">
  <input class="pe-expr" placeholder="公式，如 SUM(净投入)" value="${esc(r.expr)}" maxlength="400">
  <select class="pe-type">
   <option value="count" ${r.type==='count'?'selected':''}>件数 count</option>
   <option value="ratio" ${r.type==='ratio'?'selected':''}>比例 ratio</option>
  </select>
  <button type="button" class="pe-del" title="删除该行">×</button>
 </div>`;
}

// 从 DOM 读回口径对象；返回 {data, errors:[...]}
export function readEditor(){
 const version=document.getElementById('pe-version').value.trim();
 const description=document.getElementById('pe-desc').value.trim();
 const period=document.getElementById('pe-period').value;
 const levels={};const errors=[];
 document.querySelectorAll('.level-block').forEach(fs=>{
  const lvl=fs.dataset.level;levels[lvl]=[];
  fs.querySelectorAll('.pe-row').forEach(row=>{
   const name=row.querySelector('.pe-name').value.trim();
   const expr=row.querySelector('.pe-expr').value.trim();
   const type=row.querySelector('.pe-type').value;
   if(!name&&!expr)return; // 完全空行忽略
   if(!name)errors.push(`${lvl} 存在未命名公式`);
   if(!expr)errors.push(`中间量“${name}”缺少公式`);
   levels[lvl].push({name,expr,type});
  });
  if(!levels[lvl].length)errors.push(`${LEVELS.find(l=>l.key===lvl).label}至少需要一个中间量`);
 });
 if(!version)errors.push('口径版本名不能为空');
 if(!description)errors.push('口径说明不能为空');
 return {data:{version,kind:'custom',description,levels},period,errors};
}

export function bindPolicyEditor(onTrial,onSave){
 // 动态增删行
 document.querySelectorAll('.pe-add').forEach(btn=>{
  btn.onclick=()=>{
   const lvl=btn.dataset.level;
   const wrap=btn.previousElementSibling;
   const tmp=document.createElement('div');
   tmp.innerHTML=rowHtml(lvl,blankRow(),wrap.children.length);
   wrap.append(tmp.firstElementChild);
  };
 });
 document.querySelector('.policy-editor').addEventListener('click',e=>{
  if(e.target.classList.contains('pe-del'))e.target.closest('.pe-row').remove();
 });
 const trialBtn=document.getElementById('pe-trial');
 if(trialBtn)trialBtn.onclick=async()=>{
  const out=document.getElementById('pe-trial-out');
  out.innerHTML='<p class="pe-hint">正在试算…</p>';
  try{
   const reading=readEditor();
   if(reading.errors.length)throw new Error(reading.errors.join('；'));
   renderTrial(await onTrial(reading));
  }catch(e){renderTrial({error:e.message});}
 };
 const form=document.getElementById('policy-form');
 if(form)form.onsubmit=e=>{e.preventDefault();onSave(readEditor());};
}

export function renderTrial(out){
 const el=document.getElementById('pe-trial-out');
 if(!el)return;
 if(out.error){el.innerHTML=`<div class="pe-fail"><b>试算未通过 / 校验拒绝</b><p>${esc(out.error)}</p><p class="pe-hint">未通过校验的口径不能登记，也不能用于报告。</p></div>`;return;}
 const r=out.result;
 const tbl=rows=>{
  if(!rows||!rows.length)return '<p class="empty">无分组数据</p>';
  const keys=Object.keys(rows[0]);
  return `<div class="table-wrap"><table><thead><tr>${keys.map(k=>`<th>${esc(k)}</th>`).join('')}</tr></thead><tbody>${
   rows.map(x=>`<tr>${keys.map(k=>`<td>${esc(typeof x[k]==='number'?x[k].toLocaleString('zh-CN',{maximumFractionDigits:6}):String(x[k]))}</td>`).join('')}</tr>`).join('')
  }</tbody></table></div>`;
 };
 el.innerHTML=`<div class="pe-ok"><b>试算通过，校验有效（可登记）</b>
  <div class="metrics">${Object.entries(r.summary).map(([k,v])=>`<div><small>${esc(k)}</small><strong>${esc(typeof v==='number'?v.toLocaleString('zh-CN',{maximumFractionDigits:6}):String(v))}</strong></div>`).join('')}</div>
  <details open><summary>全厂层结果（${r.plant_rows.length} 组）</summary>${tbl(r.plant_rows)}</details>
  <details><summary>线内层结果（${r.line_rows.length} 组）</summary>${tbl(r.line_rows)}</details>
  <details><summary>逐批层结果（${r.lot_rows.length} 条，前 20 行）</summary>${tbl(r.lot_rows.slice(0,20))}</details>
  <p class="method">${esc(r.method)}</p>
 </div>`;
}
