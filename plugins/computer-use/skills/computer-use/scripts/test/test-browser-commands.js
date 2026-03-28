import { describe, it, before } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { existsSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';

const BROWSER = resolve(import.meta.dirname, '..', 'browser');

function run(...args) {
  const result = execFileSync(BROWSER, args, {
    encoding: 'utf8',
    timeout: 15000,
  });
  return JSON.parse(result.trim());
}

describe('browser CLI interaction commands', () => {
  let pageId;

  before(() => {
    const nav = run('navigate', 'https://example.com');
    pageId = nav.pageId;
  });

  it('click on a link', () => {
    const result = run('click', 'a', '--page', pageId);
    assert.equal(result.ok, true);
  });

  it('navigate back', () => {
    const result = run('back', '--page', pageId);
    assert.equal(result.ok, true);
  });

  it('screenshot saves file and returns path', () => {
    const result = run('screenshot', '--page', pageId);
    assert.equal(result.ok, true);
    assert(result.path, 'should return file path');
    assert(existsSync(result.path), 'screenshot file should exist');
    unlinkSync(result.path);
  });

  it('screenshot with custom path', () => {
    const customPath = '/tmp/test-browser-screenshot.png';
    const result = run('screenshot', '--page', pageId, '--path', customPath);
    assert.equal(result.ok, true);
    assert.equal(result.path, customPath);
    assert(existsSync(customPath), 'screenshot should exist at custom path');
    unlinkSync(customPath);
  });

  it('eval returns result', () => {
    run('navigate', 'https://example.com');
    const result = run('eval', 'document.title');
    assert.equal(result.ok, true);
    assert.match(result.result, /Example Domain/i);
  });

  it('scroll returns ok', () => {
    const result = run('scroll', 'down', '500', '--page', pageId);
    assert.equal(result.ok, true);
  });

  it('wait for existing element', () => {
    run('navigate', 'https://example.com');
    const result = run('wait', 'h1', '5');
    assert.equal(result.ok, true);
  });

  it('wait for missing element times out', () => {
    run('navigate', 'https://example.com');
    try {
      execFileSync(BROWSER, ['wait', '#nonexistent', '2'], {
        encoding: 'utf8',
        timeout: 10000,
      });
      assert.fail('Should have failed');
    } catch (e) {
      // fail() writes to stderr via writeFail
      const output = JSON.parse(e.stderr);
      assert.equal(output.ok, false);
    }
  });

  it('tab switching', () => {
    const tabs = run('tabs');
    assert(tabs.tabs.length > 0);
    const result = run('tab', '0');
    assert.equal(result.ok, true);
    assert(result.pageId);
  });

  it('pdf saves file (headed Chrome may not support this)', (t) => {
    run('navigate', 'https://example.com');
    const pdfPath = '/tmp/test-browser.pdf';
    try {
      const result = run('pdf', pdfPath);
      assert.equal(result.ok, true);
      assert(existsSync(pdfPath));
      unlinkSync(pdfPath);
    } catch (e) {
      // PDF generation fails with headed Chrome over CDP -- expected
      const output = JSON.parse(e.stderr);
      assert.equal(output.ok, false);
      assert.match(output.error, /PDF generation failed/);
      t.skip('PDF not supported with headed Chrome over CDP');
    }
  });
});
