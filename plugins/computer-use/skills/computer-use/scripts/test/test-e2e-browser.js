import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { existsSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';

const BROWSER = resolve(import.meta.dirname, '..', 'browser');

function run(...args) {
  return JSON.parse(
    execFileSync(BROWSER, args, { encoding: 'utf8', timeout: 15000 }).trim()
  );
}

describe('e2e browser workflow', () => {
  it('navigate -> snapshot -> click -> verify -> screenshot', () => {
    // 1. Navigate
    const nav = run('navigate', 'https://example.com');
    assert.equal(nav.ok, true);
    assert(nav.pageId);

    // 2. Snapshot
    const snap = run('snapshot', '--page', nav.pageId);
    assert.equal(snap.ok, true);
    assert(snap.snapshot.length > 50, 'snapshot should have content');

    // 3. Click the "More information..." link
    const click = run('click', 'a', '--page', nav.pageId);
    assert.equal(click.ok, true);

    // 4. Verify -- page URL should have changed after clicking the link
    const snap2 = run('snapshot', '--page', nav.pageId);
    assert.equal(snap2.ok, true);
    const evalResult = run('eval', 'window.location.href', '--page', nav.pageId);
    assert.notEqual(evalResult.result, 'https://example.com/', 'URL should have changed after click');

    // 5. Screenshot
    const shot = run('screenshot', '--page', nav.pageId);
    assert.equal(shot.ok, true);
    assert(existsSync(shot.path), 'screenshot file should exist');
    unlinkSync(shot.path);

    // 6. Navigate back
    const back = run('back', '--page', nav.pageId);
    assert.equal(back.ok, true);
  });
});
