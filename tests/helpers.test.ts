import { describe, expect, it } from 'vitest';
import { excerpt, filterTasks, formatNumber, formatPercent, formatRadius, histogram } from '@/lib/helpers';
import { atlas } from '@/lib/atlas';
import type { Task } from '@/lib/types';

const fixtures = [
  { instance_id: 'one__one-1', repo: 'one/one', problem_statement: 'Matrix inversion fails badly', edited_files: ['math/invert.py'], radius: 0, radius_status: 'reached' },
  { instance_id: 'two__two-2', repo: 'two/two', problem_statement: 'Parser cannot read input', edited_files: ['parser/read.py'], radius: 3, radius_status: 'reached' },
  { instance_id: 'one__one-3', repo: 'one/one', problem_statement: 'Matrix warning', edited_files: ['warn.py'], radius: null, radius_status: 'no_mentions' },
  { instance_id: 'one__one-4', repo: 'one/one', problem_statement: 'Disconnected import', edited_files: ['other.py'], radius: null, radius_status: 'unreachable' },
] as Task[];

describe('archive filters', () => {
  it('retains all tasks without filters', () => expect(filterTasks(fixtures)).toHaveLength(4));
  it('combines case-insensitive query terms', () => expect(filterTasks(fixtures, ' MATRIX  badly ')).toEqual([fixtures[0]]));
  it('searches edited file paths', () => expect(filterTasks(fixtures, 'parser/read.py')).toEqual([fixtures[1]]));
  it('combines repo and radius', () => expect(filterTasks(fixtures, '', 'one/one', '0')).toEqual([fixtures[0]]));
  it('keeps null distinct from zero', () => expect(filterTasks(fixtures, '', 'all', 'null')).toEqual([fixtures[2],fixtures[3]]));
  it('separates reasons for unresolved radii', () => expect(filterTasks(fixtures, '', 'all', 'unreachable')).toEqual([fixtures[3]]));
  it('groups long routes', () => expect(filterTasks(fixtures, '', 'all', '3+')).toEqual([fixtures[1]]));
  it('returns an empty search result', () => expect(filterTasks(fixtures, 'never-present')).toEqual([]));
});
describe('histograms and formatting', () => {
  it('bins long and null radii without conflating them', () => expect(histogram([0,0,1,2,3,8,null])).toEqual([{label:'0',count:2},{label:'1',count:1},{label:'2',count:1},{label:'3+',count:2},{label:'null',count:1}]));
  it('has stable empty bins', () => expect(histogram([]).map(b=>b.count)).toEqual([0,0,0,0,0]));
  it('formats estimated tokens and missing values', () => { expect(formatNumber(12345.75)).toBe('12,346'); expect(formatNumber(null)).toBe('—'); expect(formatNumber(0)).toBe('0'); });
  it('formats fractional recall', () => expect(formatPercent(.5633333)).toBe('56.3%'));
  it('pluralizes distances', () => { expect(formatRadius(1)).toBe('1 hop'); expect(formatRadius(0)).toBe('0 hops'); expect(formatRadius(null)).toBe('Unresolved'); });
  it('caps issue excerpts including the ellipsis', () => { expect(excerpt('x'.repeat(350))).toHaveLength(300); expect(excerpt('a\n b')).toBe('a b'); });
});
describe('generated atlas contract', () => {
  it('summaries and record counts agree', () => { expect(atlas.instances).toHaveLength(atlas.overall.instances); expect(atlas.repos.reduce((n,r)=>n+r.instances,0)).toBe(atlas.overall.instances); expect(new Set(atlas.instances.map(t=>t.instance_id)).size).toBe(atlas.instances.length); });
  it('histogram covers the complete split', () => expect(histogram(atlas.instances.map(t=>t.radius)).reduce((n,b)=>n+b.count,0)).toBe(atlas.overall.instances));
});
