// Authentication middleware
import { config } from '../config.js';

/**
 * Optional gate for the panel.
 *
 * By default (auth.enabled = false) the panel is public: it is meant for
 * students to watch and download their own clips. Clips cannot be deleted from
 * the panel. To take the panel offline use DISABLE_PANEL (see maintenance.js).
 */
export function requireAuth(req, res, next) {
  if (!config.auth.enabled) {
    return next();
  }

  if (req.session && req.session.authenticated) {
    return next();
  }
  res.status(401).json({ error: 'Authentication required' });
}

export function requireGuest(req, res, next) {
  // In public mode there is nothing to log into - go straight to the panel.
  if (!config.auth.enabled) {
    return res.redirect('/');
  }

  if (req.session && req.session.authenticated) {
    return res.redirect('/');
  }
  next();
}
