import {heading} from '../components/common/header.js';
import {esc} from '../utils/format.js';
import {table} from '../components/common/table.js';
import {policyEditor,defaultCustomPolicy} from '../components/policy-editor.js';

export function policies(c,d){
 const seed=defaultCustomPolicy(c.policy.version);
 return heading('DEFINITION REGISTER / 03',c.policy_label,'登记三级自定义口径（逐批／线内／全厂）。支持命名中间量、四则、IF 条件与低层 SUM 聚合；件数与比例不可相加，循环引用与越级取值在登记时拒绝。先试算、通过校验才可登记用于报告。历史版本与旧固定口径保留可读。')
 +`<form id="policy-form">${policyEditor(seed,d.periods,'全部')}</form>
 <h2>已登记口径（版本只增不改）</h2>`
 +table(d.policies.map(p=>({
   编号:p.id,版本:p.version,
   类型:p.data.kind==='custom'?'三级自定义':'固定分子分母',
   业务口径:p.data.kind==='custom'?summarizeCustom(p.data):(`${p.data.numerator} / ${p.data.denominator}`),
   说明:p.data.description||'',
 })));
}

function summarizeCustom(data){
 const parts=Object.entries(data.levels).map(([k,arr])=>`${{lot:'逐批',line:'线内',plant:'全厂'}[k]} ${arr.length}量`);
 return parts.join('；');
}
