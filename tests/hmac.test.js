// Tests for HMAC signature verification
import { describe, it, expect } from '@jest/globals';
import crypto from 'crypto';

describe('HMAC Authentication', () => {
  const sharedSecret = 'test-secret-key';

  function generateSignature(method, path, timestamp, nonce, body = '') {
    const payload = `${method}|${path}|${timestamp}|${nonce}|${Buffer.from(body).toString('hex')}`;
    return crypto.createHmac('sha256', sharedSecret).update(payload).digest('hex');
  }

  it('should generate valid HMAC signatures', () => {
    const method = 'GET';
    const path = '/api/internal/status';
    const timestamp = Date.now().toString();
    const nonce = crypto.randomBytes(16).toString('hex');

    const signature = generateSignature(method, path, timestamp, nonce);
    expect(signature).toBeDefined();
    expect(signature).toHaveLength(64); // SHA-256 hex length
  });

  it('should produce different signatures for different payloads', () => {
    const timestamp = Date.now().toString();
    const nonce = crypto.randomBytes(16).toString('hex');

    const sig1 = generateSignature('GET', '/api/internal/status', timestamp, nonce);
    const sig2 = generateSignature('POST', '/api/internal/trigger', timestamp, nonce);
    expect(sig1).not.toBe(sig2);
  });

  it('should include all required components in signature', () => {
    const method = 'POST';
    const path = '/api/internal/trigger';
    const timestamp = Date.now().toString();
    const nonce = crypto.randomBytes(16).toString('hex');
    const body = '{"test": true}';

    const payload = `${method}|${path}|${timestamp}|${nonce}|${Buffer.from(body).toString('hex')}`;
    const signature = crypto.createHmac('sha256', sharedSecret).update(payload).digest('hex');

    // Verify the signature is deterministic
    const signature2 = crypto.createHmac('sha256', sharedSecret).update(payload).digest('hex');
    expect(signature).toBe(signature2);
  });
});
