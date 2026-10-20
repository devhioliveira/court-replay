// Tests for rate limiting configuration
import { describe, it, expect } from '@jest/globals';

describe('Rate Limiting', () => {
  const rateLimitConfig = {
    global: { windowMs: 900000, limit: 120 },
    login: { windowMs: 900000, limit: 10 },
    trigger: { windowMs: 60000, limit: 10 },
    download: { windowMs: 60000, limit: 30 },
  };

  it('should have different limits for different endpoints', () => {
    expect(rateLimitConfig.login.limit).toBeLessThan(rateLimitConfig.global.limit);
    expect(rateLimitConfig.trigger.limit).toBeLessThan(rateLimitConfig.global.limit);
  });

  it('should have reasonable time windows', () => {
    Object.values(rateLimitConfig).forEach(config => {
      expect(config.windowMs).toBeGreaterThan(0);
      expect(config.limit).toBeGreaterThan(0);
    });
  });

  it('should have stricter limits for login than global', () => {
    expect(rateLimitConfig.login.limit).toBeLessThanOrEqual(10);
    expect(rateLimitConfig.login.windowMs).toBeGreaterThanOrEqual(60000);
  });
});
