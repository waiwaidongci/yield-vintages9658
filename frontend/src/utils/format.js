export const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt=v=>typeof v==='number'?v.toLocaleString('zh-CN',{maximumFractionDigits:4}):esc(typeof v==='object'?JSON.stringify(v):v);
export const time=v=>new Date(v*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'});
