import {STATUSES} from '../../constants/enums.js';import {esc} from '../../utils/format.js';
export const status=s=>'<span class="status '+esc(s)+'">'+(STATUSES[s]||esc(s))+'</span>';
