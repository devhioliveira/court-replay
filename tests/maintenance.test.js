// Tests for the DISABLE_PANEL maintenance switch
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { config } from '../server/src/config.js';
import { panelDisabled } from '../server/src/middleware/maintenance.js';

function makeRes() {
  const res = {
    statusCode: 200,
    headers: {},
    body: undefined,
    sentFile: undefined,
    status(code) { this.statusCode = code; return this; },
    set(key, value) { this.headers[key] = value; return this; },
    json(payload) { this.body = payload; return this; },
    sendFile(file) { this.sentFile = file; return this; },
  };
  return res;
}

describe('DISABLE_PANEL', () => {
  const original = config.panel.disabled;

  beforeEach(() => { config.panel.disabled = false; });
  afterEach(() => { config.panel.disabled = original; });

  it('lets requests through when the panel is enabled', () => {
    const res = makeRes();
    let called = false;
    panelDisabled({ path: '/' }, res, () => { called = true; });
    expect(called).toBe(true);
    expect(res.statusCode).toBe(200);
  });

  it('serves the maintenance page with 503 when disabled', () => {
    config.panel.disabled = true;
    const res = makeRes();
    let called = false;
    panelDisabled({ path: '/' }, res, () => { called = true; });
    expect(called).toBe(false);
    expect(res.statusCode).toBe(503);
    expect(res.sentFile).toBe('maintenance.html');
    expect(res.headers['Cache-Control']).toBe('no-store');
    expect(res.headers['Retry-After']).toBeDefined();
  });

  it('answers the API with JSON 503 when disabled', () => {
    config.panel.disabled = true;
    const res = makeRes();
    panelDisabled({ path: '/api/clips' }, res, () => {});
    expect(res.statusCode).toBe(503);
    expect(res.body).toEqual({ error: 'Service temporarily unavailable' });
    expect(res.sentFile).toBeUndefined();
  });
});
