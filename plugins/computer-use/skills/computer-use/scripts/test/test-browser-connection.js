// Tests require Chrome running with --remote-debugging-port=9222
// Launch before running: open -a "Google Chrome" --args --remote-debugging-port=9222

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const BROWSER = resolve(import.meta.dirname, '..', 'browser');

function run(...args) {
  const result = execFileSync(BROWSER, args, {
    encoding: 'utf8',
    timeout: 15000,
  });
  return JSON.parse(result.trim());
}

function runRaw(...args) {
  return execFileSync(BROWSER, args, {
    encoding: 'utf8',
    timeout: 15000,
  });
}

describe('browser CLI connection', () => {
  it('returns error JSON to stderr when Chrome is not reachable on wrong port', () => {
    // Use a port that is almost certainly not running CDP
    try {
      execFileSync(BROWSER, ['tabs', '--port', '19222'], {
        encoding: 'utf8',
        timeout: 10000,
      });
      assert.fail('Should have thrown');
    } catch (e) {
      // Errors go to stderr per spec
      const output = JSON.parse(e.stderr.trim());
      assert.equal(output.ok, false);
      assert.match(output.error, /Cannot connect/i);
    }
  });

  it('lists tabs as JSON array', () => {
    const result = run('tabs');
    assert.equal(result.ok, true);
    assert(Array.isArray(result.tabs), 'tabs should be an array');
    if (result.tabs.length > 0) {
      assert(result.tabs[0].pageId, 'each tab should have pageId');
      assert(result.tabs[0].url, 'each tab should have url');
    }
  });

  it('navigate returns pageId, title, url', () => {
    const result = run('navigate', 'https://example.com');
    assert.equal(result.ok, true);
    assert(result.pageId, 'should return pageId');
    assert.equal(result.url, 'https://example.com/');
    assert.match(result.title, /Example Domain/i);
  });

  it('page targeting works with --page flag', () => {
    const nav = run('navigate', 'https://example.com');
    const snap = run('snapshot', '--page', nav.pageId);
    assert.equal(snap.ok, true);
    assert(snap.snapshot.length > 0, 'snapshot should have content');
  });
});
