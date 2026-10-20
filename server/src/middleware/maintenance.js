// Maintenance switch - DISABLE_PANEL=true
import path from 'path';
import { fileURLToPath } from 'url';
import { config } from '../config.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const VIEWS_DIR = path.join(__dirname, '../../views');

const RETRY_AFTER_SECONDS = 300;

/**
 * When the panel is disabled, every request gets 503 "temporarily unavailable":
 * a friendly page for browsers, JSON for /api. Nothing else is served.
 *
 * The Python agent is not affected - it keeps recording and creating clips.
 */
export function panelDisabled(req, res, next) {
  if (!config.panel.disabled) {
    return next();
  }

  res.set('Cache-Control', 'no-store');
  res.set('Retry-After', String(RETRY_AFTER_SECONDS));
  res.status(503);

  if (req.path.startsWith('/api')) {
    return res.json({ error: 'Service temporarily unavailable' });
  }

  return res.sendFile('maintenance.html', { root: VIEWS_DIR });
}
