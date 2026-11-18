import {heading} from '../components/common/header.js';import {table} from '../components/common/table.js';import {time} from '../utils/format.js';
export function audit(c,d){return heading('PROCESS RECORD / 06','过程留痕','底稿、口径、复核与worker交付动作均记录操作者与时间。')+table(d.audits.map(a=>({时间:time(a.at),操作者:a.actor,动作:a.action,内容:a.detail}))) }
