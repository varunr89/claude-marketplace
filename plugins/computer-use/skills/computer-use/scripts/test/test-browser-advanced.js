import { describe, it, before } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const BROWSER = resolve(import.meta.dirname, '..', 'browser');

function run(...args) {
  return JSON.parse(
    execFileSync(BROWSER, args, { encoding: 'utf8', timeout: 15000 }).trim()
  );
}

function runFail(...args) {
  const opts = { encoding: 'utf8', timeout: 20000 };
  try {
    execFileSync(BROWSER, args, opts);
    return null; // did not fail
  } catch (e) {
    return JSON.parse(e.stderr.trim());
  }
}

describe('browser CLI advanced commands', () => {
  before(() => {
    run('navigate', 'https://example.com');
  });

  it('upload fails gracefully with missing file input', () => {
    const result = runFail('upload', '#nonexistent', '/tmp/test.txt');
    assert(result, 'should have failed');
    assert.equal(result.ok, false);
  });

  it('click-and-download fails gracefully with non-download link', () => {
    const result = runFail('click-and-download', 'a');
    assert(result, 'should have failed (no download triggered)');
    assert.equal(result.ok, false);
  });

  it('click-and-dialog usage error without enough args', () => {
    const result = runFail('click-and-dialog', 'a');
    assert(result, 'should have failed');
    assert.equal(result.ok, false);
  });

  it('frame with nonexistent selector fails gracefully', () => {
    const result = runFail('frame', '#nonexistent-iframe');
    assert(result, 'should have failed');
    assert.equal(result.ok, false);
  });

  it('frame --parent returns ok on main frame', () => {
    const result = run('frame', '--parent');
    assert.equal(result.ok, true);
  });
});
